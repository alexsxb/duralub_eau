"""Client API pour le portail Durance Lubéron."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from urllib.parse import quote, unquote

import aiohttp

from .const import API_BASE, API_HOST, API_ID

_LOGGER = logging.getLogger(__name__)

HEADERS_BASE = {
    "accept":        "application/vnd.api+json",
    "content-type":  "application/vnd.api+json",
    "api-id":        API_ID,
    "cache-control": "no-cache",
    "pragma":        "no-cache",
    "expires":       "0",
    "origin":        f"https://{API_HOST}",
    "user-agent":    "Mozilla/5.0 (HomeAssistant) AppleWebKit/537.36",
}


class DuranceLuberonApiError(Exception):
    """Erreur générale de l'API."""


class DuranceLuberonAuthError(DuranceLuberonApiError):
    """Erreur d'authentification."""


class DuranceLuberonClient:
    """Client HTTP asynchrone pour le portail."""

    def __init__(self, session: aiohttp.ClientSession, login: str, password: str, teleindex_id: str):
        self._session      = session
        self._login        = login
        self._password     = password
        self._teleindex_id = teleindex_id
        self._jwt_token: str | None = None
        self._cookies: dict = {}

    # ── Authentification ──────────────────────────────────────────────────

    async def authenticate(self) -> None:
        """Se connecter et récupérer le token JWT."""
        payload = {
            "data": {
                "type": "POICL_Signin",
                "id": "",
                "attributes": {
                    "login":    self._login,
                    "password": self._password,
                    "remember": True,
                },
            }
        }
        headers = {
            **HEADERS_BASE,
            "authorization": "JWT",
            "referer": f"https://{API_HOST}/public/connexion",
        }

        async with self._session.post(
            f"{API_BASE}/iclients/signin",
            json=payload,
            headers=headers,
            allow_redirects=False,
        ) as resp:
            for name, cookie in resp.cookies.items():
                self._cookies[name] = cookie.value

            if resp.status not in (200, 201):
                text = await resp.text()
                raise DuranceLuberonAuthError(
                    f"Échec de connexion (HTTP {resp.status}) : {text[:200]}"
                )

            data = await resp.json(content_type=None)

            # Token depuis le corps de la réponse
            try:
                attrs = data["data"]["attributes"]
                for key in ("token", "jwt", "access_token", "accessToken"):
                    if token := attrs.get(key):
                        self._jwt_token = token
                        break
            except (KeyError, TypeError):
                pass

            # Repli : cookie Authorization
            if not self._jwt_token:
                auth_cookie = self._cookies.get("Authorization", "")
                if auth_cookie:
                    decoded = unquote(auth_cookie)
                    self._jwt_token = (
                        decoded
                        .replace('Jwt id="', "")
                        .replace('JWT id="', "")
                        .rstrip('"')
                        .strip()
                    )

            if not self._jwt_token:
                raise DuranceLuberonAuthError("Aucun token JWT trouvé dans la réponse de connexion.")

            _LOGGER.debug("Authentification réussie.")

    # ── Relevés ───────────────────────────────────────────────────────────

    async def fetch_readings(
        self,
        date_from: date | None = None,
        date_to:   date | None = None,
    ) -> list[dict]:
        """
        Récupérer les index de compteur.
        Retourne une liste triée par date avec la consommation journalière.
        """
        if not self._jwt_token:
            await self.authenticate()

        if date_to is None:
            date_to = date.today()
        if date_from is None:
            date_from = date_to - timedelta(days=30)

        url = (
            f"{API_BASE}/iclients/teleindex/{self._teleindex_id}"
            f"/{date_from.strftime('%Y%m%d')}"
            f"/{date_to.strftime('%Y%m%d')}"
            f"?option[completion]=boundary"
        )

        auth_header = f'Jwt id="{self._jwt_token}"'
        cookie_str  = "; ".join(
            [f"{k}={v}" for k, v in self._cookies.items()]
            + [f"Authorization={quote(auth_header)}"]
        )

        headers = {
            **HEADERS_BASE,
            "authorization": auth_header,
            "referer":       f"https://{API_HOST}/telereleves",
            "cookie":        cookie_str,
        }

        async with self._session.get(url, headers=headers, allow_redirects=False) as resp:
            if resp.status == 401:
                _LOGGER.info("Token expiré, reconnexion en cours…")
                self._jwt_token = None
                await self.authenticate()
                return await self.fetch_readings(date_from, date_to)

            if resp.status != 200:
                text = await resp.text()
                raise DuranceLuberonApiError(
                    f"Teleindex HTTP {resp.status} : {text[:200]}"
                )

            data = await resp.json(content_type=None)

        entries = data.get("data", [])
        return self._parse_readings(entries)

    # ── Analyse ───────────────────────────────────────────────────────────

    @staticmethod
    def _parse_readings(entries: list) -> list[dict]:
        """
        Ne conserver que les vrais relevés journaliers (add=False, horodatage 00:00:00).
        Calcule la consommation journalière par différence des index ni.
        """
        raw = []
        for entry in entries:
            attrs = entry.get("attributes", {})
            if attrs.get("add", False):
                continue
            dateni = attrs.get("dateni", "")
            ni     = attrs.get("ni")
            if not dateni or ni is None:
                continue
            if not dateni.endswith("00:00:00"):
                continue
            raw.append({
                "date":       dateni[:10],
                "ni_litre":   ni,
                "numserie":   attrs.get("numserie", ""),
                "id_externe": attrs.get("id_externe", ""),
            })

        raw.sort(key=lambda x: x["date"])

        result = []
        for i in range(1, len(raw)):
            prev = raw[i - 1]
            curr = raw[i]
            diff = curr["ni_litre"] - prev["ni_litre"]
            result.append({
                "date":                curr["date"],
                "index_litre":         curr["ni_litre"],
                "index_m3":            round(curr["ni_litre"] / 1000, 3),
                "consommation_litre":  diff,
                "consommation_m3":     round(diff / 1000, 3),
                "numserie":            curr["numserie"],
                "id_externe":          curr["id_externe"],
            })

        return result
