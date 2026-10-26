"""Coordinator pentru întreruperi."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthError, CannotConnect, OutageStatus, ReteleElectriceClient
from .const import CONF_POD, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class OutageCoordinator(DataUpdateCoordinator[OutageStatus]):
    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: ReteleElectriceClient
    ) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.client = client
        self.pod: str = entry.data[CONF_POD]
        self._logged_in = False

    async def _async_update_data(self) -> OutageStatus:
        try:
            if not self._logged_in:
                await self.client.login()
                self._logged_in = True
            try:
                status = await self.client.get_outages(self.pod)
            except AuthError:
                # sesiune expirată: un singur re-login, apoi reîncercăm
                _LOGGER.debug("Sesiune expirată, re-login")
                await self.client.login()
                status = await self.client.get_outages(self.pod)
        except AuthError as err:
            self._logged_in = False
            raise ConfigEntryAuthFailed(str(err)) from err
        except CannotConnect as err:
            self._logged_in = False
            raise UpdateFailed(f"Portal indisponibil: {err}") from err

        if not status.ok:
            raise UpdateFailed("Portalul a răspuns cu esito != OK")
        _LOGGER.debug(
            "Întreruperi %s: active=%s flag=%s", self.pod, status.active, status.check_flag
        )
        return status
