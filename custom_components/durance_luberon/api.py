"""Client API pour le portail Durance Luberon."""
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

    def __init__(self, session: aiohttp.ClientSession, login: str, password: str):
        self._session     = session
        self._login       = login
        self._password    = password
        self._jwt_token: str | None  = None
        self._cookies: dict          = {}
        # Découvert automatiquement après login
        self.teleindex_id: str | None   = None
        self.contract_info: dict        = {}

    # ── Authentification ──────────────────────────────────────────────────

    async def authenticate(self) -> None:
        """Se connecter, récupérer le JWT et découvrir le teleindex_id."""
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

            # Token depuis le corps
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
                raise DuranceLuberonAuthError("Aucun token JWT trouvé.")

            _LOGGER.debug("Authentification réussie.")

        # Découverte automatique du contrat + teleindex_id
        await self._discover_contract()

    # ── Découverte du contrat ─────────────────────────────────────────────

    async def _discover_contract(self) -> None:
        """
        Récupère le contrat via GET /contrat?include=pconso,pconso.pdessadr
        La réponse contient data[0].id  →  c'est le teleindex_id (ex. "162463").

        Structure JSON:
          data[0].id                              → teleindex_id
          data[0].attributes.numcontrat           → numéro de contrat
          included[type=POICL_Pconso].attributes  → adresse, id_externe
        """
        headers = {
            **HEADERS_BASE,
            "authorization": f'Jwt id="{self._jwt_token}"',
            "referer":       f"https://{API_HOST}/accueil",
            "cookie":        self._cookie_header(),
        }

        async with self._session.get(
            f"{API_BASE}/iclients/contrat?include=pconso,pconso.pdessadr",
            headers=headers,
            allow_redirects=False,
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise DuranceLuberonApiError(
                    f"Impossible de récupérer le contrat (HTTP {resp.status}) : {text[:200]}"
                )
            payload = await resp.json(content_type=None)

        data = payload.get("data", [])
        if not data:
            raise DuranceLuberonApiError("Aucun contrat trouvé dans la réponse.")

        contrat = data[0]

        # ── teleindex_id = data[0].id ──────────────────────────────────────
        self.teleindex_id = str(contrat["id"])
        attrs = contrat.get("attributes", {})

        # Infos complémentaires depuis included
        adresse    = ""
        id_externe = ""
        for item in payload.get("included", []):
            if item.get("type") == "POICL_Pconso":
                pconso_attrs = item.get("attributes", {})
                id_externe   = pconso_attrs.get("id_externe", "")
                adresse      = pconso_attrs.get("cpltadr", "")
            if item.get("type") == "POICL_Pdessadr":
                pa = item.get("attributes", {})
                if not adresse:
                    adresse = f"{pa.get('nomvoie','')} {pa.get('cp','')} {pa.get('ville','')}".strip()

        self.contract_info = {
            "teleindex_id":  self.teleindex_id,
            "num_contrat":   attrs.get("numcontrat", ""),
            "actif":         attrs.get("actif", True),
            "adresse":       adresse,
            "id_externe":    id_externe,
            "date_debut":    attrs.get("datedeb", ""),
        }

        _LOGGER.info(
            "Contrat découvert : id=%s  num=%s  adresse=%s",
            self.teleindex_id,
            self.contract_info["num_contrat"],
            self.contract_info["adresse"],
        )

    # ── Relevés ───────────────────────────────────────────────────────────

    async def fetch_readings(
        self,
        date_from: date | None = None,
        date_to:   date | None = None,
    ) -> list[dict]:
        """Récupérer les index de compteur pour la période donnée."""
        if not self._jwt_token or not self.teleindex_id:
            await self.authenticate()

        if date_to is None:
            date_to = date.today()
        if date_from is None:
            date_from = date_to - timedelta(days=30)

        url = (
            f"{API_BASE}/iclients/teleindex/{self.teleindex_id}"
            f"/{date_from.strftime('%Y%m%d')}"
            f"/{date_to.strftime('%Y%m%d')}"
            f"?option[completion]=boundary"
        )

        headers = {
            **HEADERS_BASE,
            "authorization": f'Jwt id="{self._jwt_token}"',
            "referer":       f"https://{API_HOST}/telereleves",
            "cookie":        self._cookie_header(),
        }

        async with self._session.get(url, headers=headers, allow_redirects=False) as resp:
            if resp.status == 401:
                _LOGGER.info("Token expiré, reconnexion…")
                self._jwt_token = None
                self.teleindex_id = None
                await self.authenticate()
                return await self.fetch_readings(date_from, date_to)

            if resp.status != 200:
                text = await resp.text()
                raise DuranceLuberonApiError(f"Teleindex HTTP {resp.status} : {text[:200]}")

            data = await resp.json(content_type=None)

        return self._parse_readings(data.get("data", []))

    # ── Parsing ───────────────────────────────────────────────────────────

    @staticmethod
    def _parse_readings(entries: list) -> list[dict]:
        """
        Filtre et transforme les entrées brutes :
          - ignore add=True  (valeurs interpolées/estimées)
          - ignore id commençant par "completion_"
          - ne garde que les horodatages 00:00:00 (relevé de minuit)
          - calcule la consommation journalière par différence des index ni
        """
        raw = []
        for entry in entries:
            entry_id = entry.get("id", "")
            if entry_id.startswith("completion_"):
                continue
            attrs = entry.get("attributes", {})
            if attrs.get("add", False):
                continue
            dateni = attrs.get("dateni", "")
            ni     = attrs.get("ni")
            if not dateni or ni is None or not dateni.endswith("00:00:00"):
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
                "date":               curr["date"],
                "index_litre":        curr["ni_litre"],
                "index_m3":           round(curr["ni_litre"] / 1000, 3),
                "consommation_litre": diff,
                "consommation_m3":    round(diff / 1000, 3),
                "numserie":           curr["numserie"],
                "id_externe":         curr["id_externe"],
            })

        return result

    # ── Helpers ───────────────────────────────────────────────────────────

    def _cookie_header(self) -> str:
        auth_val = f'Jwt id="{self._jwt_token}"'
        parts = [f"{k}={v}" for k, v in self._cookies.items()]
        parts.append(f"Authorization={quote(auth_val)}")
        return "; ".join(parts)
