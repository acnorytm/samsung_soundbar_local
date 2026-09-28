"""Coordinator: one shared connection, OBSERVE push + slow poll fallback."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SoundbarClient, SoundbarError
from .const import OBSERVE_HREFS, POLL_HREFS, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SoundbarCoordinator(DataUpdateCoordinator[dict]):
    """Caches each resource's latest representation.

    Updates arrive two ways: OBSERVE notifications push changes instantly, and
    a slow poll runs as a keepalive that also re-reads anything that isn't
    observable and forces a reconnect (which re-subscribes) if the session died.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: SoundbarClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="samsung_soundbar_local",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.entry = entry
        self.client = client
        self._observing = False
        client.set_notification_handler(self._on_notification)

    # -- OBSERVE push ----------------------------------------------------
    def _on_notification(self, href: str, rep: dict) -> None:
        """Called on the library reader thread; marshal onto the event loop."""
        self.hass.loop.call_soon_threadsafe(self._apply_push, href, rep)

    @callback
    def _apply_push(self, href: str, rep: dict) -> None:
        data = dict(self.data or {})
        data[href] = rep
        self.async_set_updated_data(data)

    # -- poll (seed + keepalive/fallback) --------------------------------
    async def _async_update_data(self) -> dict:
        # Bound the poll so a blocked socket can never wedge setup at
        # "Initialising" — a timeout surfaces as a retry, not a hang.
        try:
            async with asyncio.timeout(45):
                data = await self.hass.async_add_executor_job(self._poll_all)
        except (SoundbarError, TimeoutError) as err:
            raise UpdateFailed(str(err) or "timed out") from err
        return data

    async def async_start_observe(self) -> None:
        """Register OBSERVE relations after setup, off the critical path.

        Runs as a background task so a slow or blocked subscribe can never
        delay the config entry from finishing setup. Reconnects re-subscribe
        on their own, so this only needs to run once.
        """
        if self._observing:
            return
        self._observing = True
        try:
            await self.hass.async_add_executor_job(self.client.observe, OBSERVE_HREFS)
        except Exception as err:  # noqa: BLE001 - never fail setup over push
            _LOGGER.warning("OBSERVE setup failed; falling back to polling: %s", err)

    def _poll_all(self) -> dict:
        data: dict[str, dict] = dict(self.data or {})
        for href in POLL_HREFS:
            try:
                data[href] = self.client.get(href)
            except SoundbarError as err:
                _LOGGER.debug("poll %s failed: %s", href, err)
        if not data:
            raise SoundbarError("no resources answered")
        return data

    async def async_write(self, href: str, payload: dict) -> None:
        """POST then refresh so state reflects the change immediately.

        OBSERVE usually delivers the change on its own, but an explicit refresh
        removes any lag for resources whose relation didn't register.
        """
        await self.hass.async_add_executor_job(self.client.post, href, payload)
        await self.async_request_refresh()
