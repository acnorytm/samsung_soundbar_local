"""Switch entities for the soundbar's on/off features."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    NS,
    R_ADVANCED,
    R_AUDIOPROMPT,
    R_AUTOEQ,
    R_AVA,
)
from .entity import SoundbarEntity


@dataclass(frozen=True)
class SwitchSpec:
    key: str            # unique_id suffix
    name: str
    href: str
    attr: str           # full attribute name
    boolean: bool = False  # True => bool payload, else 0/1 int


SWITCHES = [
    SwitchSpec("ava", "Active Voice Amplifier", R_AVA, f"{NS}.activeVoiceAmplifier"),
    SwitchSpec("voice_enhance", "Voice Enhancement", R_ADVANCED, f"{NS}.voiceamplifier"),
    SwitchSpec("bass_enhance", "Bass Enhancement", R_ADVANCED, f"{NS}.bassboost"),
    SwitchSpec("night_mode", "Night Mode", R_ADVANCED, f"{NS}.nightmode"),
    SwitchSpec("auto_eq", "Auto EQ", R_AUTOEQ, f"{NS}.autoeqmode"),
    SwitchSpec("audio_feedback", "Audio Feedback", R_AUDIOPROMPT, f"{NS}.audioPrompt", boolean=True),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coord = hass.data[DOMAIN][entry.entry_id]
    add([SoundbarSwitch(coord, spec) for spec in SWITCHES])


class SoundbarSwitch(SoundbarEntity, SwitchEntity):
    def __init__(self, coord, spec: SwitchSpec) -> None:
        super().__init__(coord)
        self._spec = spec
        self._attr_name = spec.name

    @property
    def unique_id(self) -> str:
        return f"{self._di}_{self._spec.key}"

    @property
    def is_on(self) -> bool | None:
        val = self.rep(self._spec.href).get(self._spec.attr)
        if val is None:
            return None
        return bool(val)

    async def _write(self, on: bool) -> None:
        payload = {self._spec.attr: on if self._spec.boolean else (1 if on else 0)}
        await self.coordinator.async_write(self._spec.href, payload)

    async def async_turn_on(self, **kwargs) -> None:
        await self._write(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._write(False)
