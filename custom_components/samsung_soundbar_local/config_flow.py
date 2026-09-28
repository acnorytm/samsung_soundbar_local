"""Config flow: enter host, secure port, and the OwnerPSK identity + key."""
from __future__ import annotations

from typing import Any
from uuid import UUID

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .api import SoundbarClient, SoundbarError
from .const import (
    CONF_DI,
    CONF_HOST,
    CONF_PORT,
    CONF_PSK_IDENTITY,
    CONF_PSK_KEY,
    DEFAULT_PORT,
    DOMAIN,
)


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=d.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=d.get(CONF_PORT, DEFAULT_PORT)): int,
            vol.Required(CONF_PSK_IDENTITY, default=d.get(CONF_PSK_IDENTITY, "")): str,
            vol.Required(CONF_PSK_KEY, default=d.get(CONF_PSK_KEY, "")): str,
        }
    )


class SoundbarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the local soundbar."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            # validate identity/key format
            try:
                UUID(user_input[CONF_PSK_IDENTITY])
                bytes.fromhex(user_input[CONF_PSK_KEY])
            except ValueError:
                errors["base"] = "bad_credential"

            if not errors:
                client = SoundbarClient(
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_PSK_IDENTITY],
                    user_input[CONF_PSK_KEY],
                )
                try:
                    dev = await self.hass.async_add_executor_job(client.get, "/oic/d")
                    di = dev.get("di", "")
                finally:
                    await self.hass.async_add_executor_job(client.close)

                if not di:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(di)
                    self._abort_if_unique_id_configured()
                    data = dict(user_input)
                    data[CONF_DI] = di
                    return self.async_create_entry(
                        title=dev.get("n", "Samsung Soundbar"), data=data
                    )

        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input), errors=errors
        )
