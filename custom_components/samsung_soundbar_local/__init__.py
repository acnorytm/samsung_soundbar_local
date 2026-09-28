"""Samsung Soundbar (local OCF/DTLS-PSK) integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import SoundbarClient
from .const import CONF_HOST, CONF_PORT, CONF_PSK_IDENTITY, CONF_PSK_KEY, DOMAIN
from .coordinator import SoundbarCoordinator

PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SELECT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = SoundbarClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_PSK_IDENTITY],
        entry.data[CONF_PSK_KEY],
    )
    coordinator = SoundbarCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register OBSERVE push in the background so a slow/blocked subscribe can
    # never hold up setup; polling covers state until it's live.
    entry.async_create_background_task(
        hass, coordinator.async_start_observe(), "samsung_soundbar_local-observe"
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: SoundbarCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await hass.async_add_executor_job(coordinator.client.close)
    return unloaded
