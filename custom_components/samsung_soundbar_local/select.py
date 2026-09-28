"""Select entity for the EQ preset."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NS, R_EQ
from .entity import SoundbarEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    add([EqPresetSelect(hass.data[DOMAIN][entry.entry_id])])


class EqPresetSelect(SoundbarEntity, SelectEntity):
    _attr_name = "EQ Preset"

    @property
    def unique_id(self) -> str:
        return f"{self._di}_eq_preset"

    @property
    def options(self) -> list[str]:
        return self.rep(R_EQ).get(f"{NS}.supportedList", [])

    @property
    def current_option(self) -> str | None:
        return self.rep(R_EQ).get(f"{NS}.EQname")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_write(
            R_EQ, {f"{NS}.EQname": option, f"{NS}.action": "setEQmode"}
        )
