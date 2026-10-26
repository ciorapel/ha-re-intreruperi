"""Binary sensor: există o întrerupere?"""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ReteleConfigEntry
from .coordinator import OutageCoordinator
from .sensor import device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ReteleConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([OutageBinarySensor(entry.runtime_data)])


class OutageBinarySensor(CoordinatorEntity[OutageCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "outage_active"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: OutageCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.pod}_outage_active"
        self._attr_device_info = device_info(coordinator.pod)

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.active
