"""Config Flow – Configuration via l'interface Home Assistant."""
from __future__ import annotations

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DuranceLuberonClient, DuranceLuberonAuthError, DuranceLuberonApiError
from .const import (
    DOMAIN,
    CONF_LOGIN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)

# Plus de champ teleindex_id – découvert automatiquement
STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOGIN):    str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)


class DuranceLuberonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Assistant de configuration pour Durance Lubéron."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                session = async_get_clientsession(self.hass)
                client  = DuranceLuberonClient(
                    session,
                    user_input[CONF_LOGIN],
                    user_input[CONF_PASSWORD],
                )
                # authenticate() appelle aussi _discover_contract()
                await client.authenticate()

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
                    title=f"Eau – {client.contract_info.get('adresse', user_input[CONF_LOGIN])}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )
