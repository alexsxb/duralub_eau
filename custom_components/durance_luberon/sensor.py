"""Capteurs de consommation d'eau Durance Lubéron."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WaterDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Créer les capteurs depuis la config entry."""
    coordinator: WaterDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        CapteurIndexEau(coordinator, entry),            # Index absolu (m³)
        CapteurConsommationJournaliere(coordinator, entry),  # Consommation jour (m³)
        CapteurConsommationMensuelle(coordinator, entry),    # Consommation mois (m³)
        CapteurDateDernierReleve(coordinator, entry),        # Date dernier relevé
    ])


# ── Classe de base ────────────────────────────────────────────────────────────

class CapteurDuranceBase(CoordinatorEntity, SensorEntity):
    """Base commune pour tous les capteurs."""

    def __init__(
        self,
        coordinator: WaterDataCoordinator,
        entry: ConfigEntry,
        sensor_key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry      = entry
        self._sensor_key = sensor_key
        self._attr_name  = name
        self._attr_unique_id = f"{entry.entry_id}_{sensor_key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Durance Lubéron Eau",
            manufacturer="Durance Lubéron",
            model="Télérelève",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.latest is not None


# ── Index absolu ──────────────────────────────────────────────────────────────

class CapteurIndexEau(CapteurDuranceBase):
    """Index absolu du compteur en m³ – croissant en continu (total_increasing)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "index_eau", "Index compteur eau")
        self._attr_device_class               = SensorDeviceClass.WATER
        self._attr_state_class                = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
        self._attr_icon                       = "mdi:water-pump"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.latest:
            return self.coordinator.latest.get("index_m3")
        return None

    @property
    def extra_state_attributes(self) -> dict:
        r = self.coordinator.latest or {}
        return {
            "index_litres":  r.get("index_litre"),
            "date":          r.get("date"),
            "numéro_série":  r.get("numserie"),
            "id_externe":    r.get("id_externe"),
        }


# ── Consommation journalière ──────────────────────────────────────────────────

class CapteurConsommationJournaliere(CapteurDuranceBase):
    """Consommation du dernier jour disponible en m³."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "consommation_jour", "Consommation eau journalière")
        self._attr_device_class               = SensorDeviceClass.WATER
        self._attr_state_class                = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
        self._attr_icon                       = "mdi:water"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.latest:
            return self.coordinator.latest.get("consommation_m3")
        return None

    @property
    def extra_state_attributes(self) -> dict:
        r       = self.coordinator.latest or {}
        history = self.coordinator.history or []

        # Moyenne sur les 7 derniers jours
        sept_jours = [
            x["consommation_m3"] for x in history[-7:]
            if x.get("consommation_m3") is not None
        ]
        moyenne_7j = round(sum(sept_jours) / len(sept_jours), 3) if sept_jours else None

        return {
            "consommation_litres":      r.get("consommation_litre"),
            "date":                     r.get("date"),
            "moyenne_7_jours_m3":       moyenne_7j,
            "nombre_relevés":           len(history),
        }


# ── Consommation mensuelle ────────────────────────────────────────────────────

class CapteurConsommationMensuelle(CapteurDuranceBase):
    """Consommation totale du mois calendaire en cours en m³."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "consommation_mois", "Consommation eau mensuelle")
        self._attr_device_class               = SensorDeviceClass.WATER
        self._attr_state_class                = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
        self._attr_icon                       = "mdi:calendar-month"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.consommation_mensuelle_m3

    @property
    def extra_state_attributes(self) -> dict:
        from datetime import date
        today    = date.today()
        mois_str = today.strftime("%Y-%m")
        donnees_mois = [
            r for r in (self.coordinator.history or [])
            if r.get("date", "").startswith(mois_str)
        ]
        return {
            "mois":              today.strftime("%B %Y"),
            "jours_avec_données": len(donnees_mois),
            "jours_écoules":     today.day,
        }


# ── Date du dernier relevé ────────────────────────────────────────────────────

class CapteurDateDernierReleve(CapteurDuranceBase):
    """Date du dernier relevé reçu."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "date_dernier_releve", "Dernier relevé eau")
        self._attr_device_class = SensorDeviceClass.DATE
        self._attr_icon         = "mdi:calendar-check"

    @property
    def native_value(self) -> str | None:
        if self.coordinator.latest:
            return self.coordinator.latest.get("date")
        return None
