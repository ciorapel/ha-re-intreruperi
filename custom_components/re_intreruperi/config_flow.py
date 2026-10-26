"""Config flow: email, parolă, POD, interval."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback

from .api import AuthError, CannotConnect, ReteleElectriceClient
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_POD,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


async def _validate(hass: HomeAssistant, email: str, password: str, pod: str) -> None:
    # sesiune proprie, închisă la final (nu închidem sesiunea partajată a lui HA)
    session = aiohttp.ClientSession(
        cookie_jar=aiohttp.CookieJar(unsafe=True),
        headers={"User-Agent": USER_AGENT},
    )
    try:
        client = ReteleElectriceClient(session, email, password)
        await client.login()
        status = await client.get_outages(pod)
        if not status.ok:
            raise CannotConnect("esito != OK (POD greșit?)")
    finally:
        await session.close()


class ReteleConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            pod = user_input[CONF_POD].strip().upper()
            await self.async_set_unique_id(pod)
            self._abort_if_unique_id_configured()
            try:
                await _validate(
                    self.hass, user_input[CONF_EMAIL], user_input[CONF_PASSWORD], pod
                )
            except AuthError as err:
                _LOGGER.warning("Validare eșuată (autentificare): %s", err)
                errors["base"] = "invalid_auth"
            except CannotConnect as err:
                _LOGGER.warning("Validare eșuată (conexiune): %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Eroare neașteptată la validare")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Întreruperi {pod}",
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_POD: pod,
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_POD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                await _validate(
                    self.hass,
                    entry.data[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                    entry.data[CONF_POD],
                )
            except AuthError as err:
                _LOGGER.warning("Reautentificare eșuată: %s", err)
                errors["base"] = "invalid_auth"
            except CannotConnect as err:
                _LOGGER.warning("Reautentificare eșuată (conexiune): %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return ReteleOptionsFlow()


class ReteleOptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                    )
                }
            ),
        )
