"""DataUpdateCoordinator pour Durance Luberon."""
from __future__ import annotations

import logging
from datetime import date, timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DuranceLuberonClient, DuranceLuberonApiError, DuranceLuberonAuthError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class WaterDataCoordinator(DataUpdateCoordinator):
    """Coordonne la récupération des données depuis le portail."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: DuranceLuberonClient,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.client = client
        self.latest: dict | None = None
        self.history: list[dict] = []
        self.consommation_mensuelle_m3: float = 0.0

    async def _async_update_data(self) -> dict:
        """Récupérer et préparer les données depuis le portail."""
        try:
            today      = date.today()
            debut_mois = today.replace(day=1)
            fetch_from = min(debut_mois, today - timedelta(days=30))

            releves = await self.client.fetch_readings(
                date_from=fetch_from,
                date_to=today,
            )
        except DuranceLuberonAuthError as err:
            raise UpdateFailed(f"Erreur d'authentification : {err}") from err
        except DuranceLuberonApiError as err:
            raise UpdateFailed(f"Erreur API : {err}") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Erreur de connexion : {err}") from err

        if not releves:
            return self.data or {}

        self.history = releves
        self.latest  = releves[-1]

        mois_str = today.strftime("%Y-%m")
        self.consommation_mensuelle_m3 = round(
            sum(r["consommation_m3"] for r in releves if r["date"].startswith(mois_str)),
            3,
        )

        _LOGGER.debug(
            "Données mises à jour : %d jours, dernier relevé %s = %.3f m³ (contrat %s)",
            len(releves),
            self.latest["date"],
            self.latest["index_m3"],
            self.client.teleindex_id,
        )

        return {
            "latest":            self.latest,
            "history":           self.history,
            "consommation_mois": self.consommation_mensuelle_m3,
            "contract_info":     self.client.contract_info,
        }
