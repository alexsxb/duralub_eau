"""Intégration Durance Luberon pour Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DuranceLuberonClient
from .const import CONF_LOGIN, CONF_PASSWORD, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .coordinator import WaterDataCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]

type DuranceLuberonConfigEntry = ConfigEntry[WaterDataCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: DuranceLuberonConfigEntry) -> bool:
    """Configurer l'intégration depuis une config entry."""
    session = async_get_clientsession(hass)

    # Plus de teleindex_id en config – le client le découvre tout seul
    client = DuranceLuberonClient(
        session,
        entry.data[CONF_LOGIN],
        entry.data[CONF_PASSWORD],
    )

    # L'intervalle se règle via les options ; repli sur l'ancienne valeur en data
    intervalle = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    coordinator = WaterDataCoordinator(
        hass,
        entry,
        client,
        update_interval=timedelta(minutes=intervalle),
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DuranceLuberonConfigEntry) -> bool:
    """Décharger l'intégration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: DuranceLuberonConfigEntry) -> None:
    """Recharger l'intégration après modification des options."""
    await hass.config_entries.async_reload(entry.entry_id)
