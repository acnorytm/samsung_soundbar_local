"""Button: run the Auto EQ (SpaceFit) room/subwoofer calibration.

Pressing it POSTs the write-only `tuneaction` action to the autoeq resource
(value 0 = START, from the SmartThings networkaudio plugin). The soundbar
plays a sequence of test tones during calibration and sets `autoeqmode = 1`
when it finishes, which the Auto EQ switch then reflects.
"""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NS, R_AUTOEQ
from .entity import SoundbarEntity

# AutoEQTuneAction enum (from the networkaudio plugin): START=0, CANCEL_REQUEST=1,
# RESUME=2, CANCEL_CONFIRMED=3.
TUNE_ACTION_START = 0


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    add([AutoEqButton(hass.data[DOMAIN][entry.entry_id])])


class AutoEqButton(SoundbarEntity, ButtonEntity):
    _attr_name = "Run Auto EQ"
    _attr_icon = "mdi:tune-vertical"

    @property
    def unique_id(self) -> str:
        return f"{self._di}_run_autoeq"

    async def async_press(self) -> None:
        await self.coordinator.async_write(
            R_AUTOEQ, {f"{NS}.tuneaction": TUNE_ACTION_START}
        )
