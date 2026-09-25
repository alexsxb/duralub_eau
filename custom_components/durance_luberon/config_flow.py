"""Config Flow – Configuration via l'interface Home Assistant."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DuranceLuberonClient, DuranceLuberonAuthError, DuranceLuberonApiError
from .const import (
    DOMAIN,
    CONF_LOGIN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL_VALIDATOR = vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL))

# Plus de champ teleindex_id – découvert automatiquement
STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOGIN):    str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): SCAN_INTERVAL_VALIDATOR,
    }
)

STEP_REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class DuranceLuberonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Assistant de configuration pour Durance Luberon."""

    VERSION = 1

    async def _async_validate(
        self, login: str, password: str
    ) -> tuple[DuranceLuberonClient | None, dict[str, str]]:
        """Tester les identifiants ; retourne le client et les erreurs éventuelles."""
        errors: dict[str, str] = {}
        client = DuranceLuberonClient(async_get_clientsession(self.hass), login, password)
        try:
            # authenticate() appelle aussi _discover_contract()
            await client.authenticate()
        except DuranceLuberonAuthError:
            errors["base"] = "invalid_auth"
        except (DuranceLuberonApiError, aiohttp.ClientError):
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Erreur inattendue lors de la connexion")
            errors["base"] = "unknown"
        return client, errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_LOGIN])
            self._abort_if_unique_id_configured()

            client, errors = await self._async_validate(
                user_input[CONF_LOGIN], user_input[CONF_PASSWORD]
            )
            if not errors:
                return self.async_create_entry(
                    title=f"Eau – {client.contract_info.get('adresse') or user_input[CONF_LOGIN]}",
                    data={
                        CONF_LOGIN:    user_input[CONF_LOGIN],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                    options={
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Démarrer la ré-authentification (mot de passe changé)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Demander le nouveau mot de passe."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            _, errors = await self._async_validate(
                entry.data[CONF_LOGIN], user_input[CONF_PASSWORD]
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            description_placeholders={"login": entry.data[CONF_LOGIN]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Retourner le flux d'options."""
        return DuranceLuberonOptionsFlow()


class DuranceLuberonOptionsFlow(OptionsFlow):
    """Options : intervalle de mise à jour."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        actuel = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=actuel): SCAN_INTERVAL_VALIDATOR,
                }
            ),
        )
