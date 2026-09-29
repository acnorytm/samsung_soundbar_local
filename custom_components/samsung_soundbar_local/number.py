"""Number entities: woofer, audio sync, tone (bass/treble), channel levels."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CHANNELS,
    DOMAIN,
    NS,
    R_AUDIOSYNC,
    R_CHANNEL,
    R_TONE,
    R_WOOFER,
)
from .entity import SoundbarEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coord = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = [
        WooferNumber(coord),
        AudioSyncNumber(coord),
        ToneNumber(coord, "bass", "Bass"),
        ToneNumber(coord, "treble", "Treble"),
    ]
    entities += [ChannelLevelNumber(coord, spk, label) for spk, label in CHANNELS]
    add(entities)


class _BaseNumber(SoundbarEntity, NumberEntity):
    _attr_mode = NumberMode.SLIDER
    _attr_native_step = 1


class WooferNumber(_BaseNumber):
    _attr_name = "Woofer"
    _attr_native_min_value = -12
    _attr_native_max_value = 6

    @property
    def unique_id(self) -> str:
        return f"{self._di}_woofer"

    @property
    def native_value(self) -> float | None:
        return self.rep(R_WOOFER).get(f"{NS}.woofer")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write(R_WOOFER, {f"{NS}.woofer": int(value)})


class AudioSyncNumber(_BaseNumber):
    _attr_name = "Audio Sync"
    _attr_native_min_value = 0
    _attr_native_max_value = 300
    _attr_native_step = 10
    _attr_native_unit_of_measurement = "ms"

    @property
    def unique_id(self) -> str:
        return f"{self._di}_audiosync"

    @property
    def native_value(self) -> float | None:
        return self.rep(R_AUDIOSYNC).get(f"{NS}.audiosync")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write(R_AUDIOSYNC, {f"{NS}.audiosync": int(value)})


class ToneNumber(_BaseNumber):
    _attr_native_min_value = -6
    _attr_native_max_value = 6

    def __init__(self, coord, key: str, label: str) -> None:
        super().__init__(coord)
        self._key = key
        self._attr_name = f"Tone {label}"

    @property
    def unique_id(self) -> str:
        return f"{self._di}_tone_{self._key}"

    @property
    def native_value(self) -> float | None:
        return self.rep(R_TONE).get(f"{NS}.{self._key}")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write(R_TONE, {f"{NS}.{self._key}": int(value)})


class ChannelLevelNumber(_BaseNumber):
    _attr_native_min_value = -6
    _attr_native_max_value = 6

    def __init__(self, coord, spk: str, label: str) -> None:
        super().__init__(coord)
        self._spk = spk
        self._attr_name = f"Channel {label}"

    @property
    def unique_id(self) -> str:
        return f"{self._di}_channel_{self._spk}"

    def _entry(self) -> dict | None:
        for item in self.rep(R_CHANNEL).get(f"{NS}.channelVolume", []):
            if item.get("name") == self._spk:
                return item
        return None

    @property
    def available(self) -> bool:
        e = self._entry()
        return super().available and e is not None and e.get("status", -1) != -1

    @property
    def native_value(self) -> float | None:
        e = self._entry()
        return None if e is None else e.get("value")

    async def async_set_native_value(self, value: float) -> None:
        # The soundbar only applies a channelVolume write sent as a SINGLE
        # entry carrying name + value + status. Posting the whole array (or an
        # entry without status) returns 2.04 but is silently ignored.
        status = (self._entry() or {}).get("status", 1)
        await self.coordinator.async_write(
            R_CHANNEL,
            {f"{NS}.channelVolume": [{"name": self._spk, "value": int(value), "status": status}]},
        )
