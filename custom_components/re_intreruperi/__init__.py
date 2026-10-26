"""Rețele Electrice - Întreruperi de curent."""
from __future__ import annotations

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import ReteleElectriceClient
from .const import CONF_EMAIL, CONF_PASSWORD, USER_AGENT
from .coordinator import OutageCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

type ReteleConfigEntry = ConfigEntry[OutageCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ReteleConfigEntry) -> bool:
    session = async_create_clientsession(
        hass,
        cookie_jar=aiohttp.CookieJar(unsafe=True),
        headers={"User-Agent": USER_AGENT},
    )
    client = ReteleElectriceClient(
        session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
    )
    coordinator = OutageCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: ReteleConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ReteleConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
