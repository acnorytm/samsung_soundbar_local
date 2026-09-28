"""Shared base entity and device info."""
from __future__ import annotations

try:  # HA >= 2025.x exposes DeviceInfo as its own module
    from homeassistant.helpers.device_info import DeviceInfo
except ImportError:  # older cores export it from helpers.entity
    from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SoundbarCoordinator


class SoundbarEntity(CoordinatorEntity[SoundbarCoordinator]):
    """Base for all soundbar entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SoundbarCoordinator) -> None:
        super().__init__(coordinator)
        di = coordinator.entry.data.get("di") or coordinator.entry.entry_id
        self._di = di
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, di)},
            manufacturer="Samsung Electronics",
            model="HW-Q900A",
            name="Samsung Soundbar Q900A",
        )

    def rep(self, href: str) -> dict:
        """Latest representation for a resource, or empty dict."""
        return (self.coordinator.data or {}).get(href, {})
