"""Config Flow – Configuration via l'interface Home Assistant."""
from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DuranceLuberonClient, DuranceLuberonAuthError, DuranceLuberonApiError
from .const import (
    DOMAIN,
    CONF_LOGIN,
    CONF_PASSWORD,
    CONF_TELEINDEX_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOGIN):        str,
        vol.Required(CONF_PASSWORD):     str,
        vol.Required(CONF_TELEINDEX_ID): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)


async def _valider_identifiants(hass: HomeAssistant, data: dict) -> None:
    """Tester la connexion – lève une exception en cas d'échec."""
    session = async_get_clientsession(hass)
    client  = DuranceLuberonClient(
        session,
        data[CONF_LOGIN],
        data[CONF_PASSWORD],
        data[CONF_TELEINDEX_ID],
    )
    await client.authenticate()


class DuranceLuberonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Assistant de configuration pour Durance Lubéron."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _valider_identifiants(self.hass, user_input)
            except DuranceLuberonAuthError:
                errors["base"] = "invalid_auth"
            except DuranceLuberonApiError:
                errors["base"] = "cannot_connect"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_LOGIN])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Eau ({user_input[CONF_LOGIN]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )
