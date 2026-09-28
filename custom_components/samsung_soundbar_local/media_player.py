"""Media player: power, volume, mute, source, sound mode, transport."""
from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    NS,
    R_AUDIO,
    R_MODE,
    R_PLAYBACK,
    R_POWER,
    R_SOUNDMODE,
    VOLUME_MAX,
)
from .entity import SoundbarEntity

# Friendly labels for the hardware input modes.
SOURCE_LABELS = {
    "optical": "Optical",
    "hdmi1": "HDMI 1",
    "hdmi2": "HDMI 2",
    "bt": "Bluetooth",
    "wifiidle": "Wi-Fi",
}
SOURCE_REVERSE = {v: k for k, v in SOURCE_LABELS.items()}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    add([SoundbarMediaPlayer(hass.data[DOMAIN][entry.entry_id])])


class SoundbarMediaPlayer(SoundbarEntity, MediaPlayerEntity):
    _attr_name = None  # main entity uses the device name
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
    )

    @property
    def unique_id(self) -> str:
        return f"{self._di}_media_player"

    @property
    def state(self) -> MediaPlayerState:
        if not self.rep(R_POWER).get("value", False):
            return MediaPlayerState.OFF
        modes = self.rep(R_PLAYBACK).get("modes") or []
        if "play" in modes:
            return MediaPlayerState.PLAYING
        if "pause" in modes:
            return MediaPlayerState.PAUSED
        return MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        v = self.rep(R_AUDIO).get("volume")
        return None if v is None else v / VOLUME_MAX

    @property
    def is_volume_muted(self) -> bool | None:
        return self.rep(R_AUDIO).get("mute")

    @property
    def source(self) -> str | None:
        m = self.rep(R_MODE).get("mode")
        return SOURCE_LABELS.get(m, m)

    @property
    def source_list(self) -> list[str]:
        return [SOURCE_LABELS.get(m, m) for m in self.rep(R_MODE).get("supportedModes", [])]

    @property
    def sound_mode(self) -> str | None:
        return self.rep(R_SOUNDMODE).get(f"{NS}.soundmode")

    @property
    def sound_mode_list(self) -> list[str]:
        return self.rep(R_SOUNDMODE).get(f"{NS}.supportedSoundmode", [])

    # -- commands --------------------------------------------------------
    async def async_turn_on(self) -> None:
        await self.coordinator.async_write(R_POWER, {"value": True})

    async def async_turn_off(self) -> None:
        await self.coordinator.async_write(R_POWER, {"value": False})

    async def async_set_volume_level(self, volume: float) -> None:
        await self.coordinator.async_write(R_AUDIO, {"volume": round(volume * VOLUME_MAX)})

    async def async_volume_up(self) -> None:
        cur = self.rep(R_AUDIO).get("volume", 0)
        await self.coordinator.async_write(R_AUDIO, {"volume": min(VOLUME_MAX, cur + 1)})

    async def async_volume_down(self) -> None:
        cur = self.rep(R_AUDIO).get("volume", 0)
        await self.coordinator.async_write(R_AUDIO, {"volume": max(0, cur - 1)})

    async def async_mute_volume(self, mute: bool) -> None:
        await self.coordinator.async_write(R_AUDIO, {"mute": mute})

    async def async_select_source(self, source: str) -> None:
        raw = SOURCE_REVERSE.get(source, source)
        await self.coordinator.async_write(R_MODE, {"mode": raw})

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        await self.coordinator.async_write(R_SOUNDMODE, {f"{NS}.soundmode": sound_mode})

    async def async_media_play(self) -> None:
        await self.coordinator.async_write(R_PLAYBACK, {"modes": ["play"]})

    async def async_media_pause(self) -> None:
        await self.coordinator.async_write(R_PLAYBACK, {"modes": ["pause"]})

    async def async_media_stop(self) -> None:
        await self.coordinator.async_write(R_PLAYBACK, {"modes": ["stop"]})
