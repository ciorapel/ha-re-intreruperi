"""Senzor text: starea întreruperii."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ReteleConfigEntry
from .const import DOMAIN
from .coordinator import OutageCoordinator


def device_info(pod: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, pod)},
        name=f"Rețele Electrice {pod}",
        manufacturer="Rețele Electrice România",
        entry_type=DeviceEntryType.SERVICE,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ReteleConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([OutageSensor(entry.runtime_data)])


class OutageSensor(CoordinatorEntity[OutageCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "outage_status"
    _attr_icon = "mdi:flash-alert"

    def __init__(self, coordinator: OutageCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.pod}_outage_status"
        self._attr_device_info = device_info(coordinator.pod)

    @property
    def native_value(self) -> str | None:
        active = self.coordinator.data.active
        if active is None:
            return None
        return "Întrerupere activă" if active else "Fără întreruperi"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data
        return {
            "pod": d.pod,
            "mesaj": d.message,
            "checkInterruzione": d.check_flag,  # util pentru a calibra euristica
        }
