"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Oocsi sensor platform."""
    oocsiGateway = hass.data[DOMAIN]["GATEWAY"][config_entry.entry_id]

    @callback
    async def async_add_switch(info) -> None:

        api = hass.data[DOMAIN][config_entry.entry_id]
        platform = "switch"
        await oocsiGateway.async_create_new_platform_entity(
            hass, config_entry, api, BasicSwitch, async_add_entities, platform
        )

        config_entry.async_on_unload(
            async_dispatcher_connect(
                hass,
                oocsiGateway._signal_new_switch,
                async_add_switch,
            )
        )


class BasicSwitch(SwitchEntity):
    """Basic oocsi switch."""

    def __init__(self, hass, entityProperty):
        """Set basic oocsi switch parameters."""
        self._property = entityProperty
        self._hass = hass

        self._oocsi = self._property.oocsi_api()
        self._attr_unique_id = self._property.channel_name
        self._oocsichannel = self._property.channel_name
        self._channel_state = self._propety.state
        # self._attr_device_info = {
        #     "name": entity_name,
        #     "manufacturer": entityProperty["creator"],
        #     "via_device_id": device,
        # }

    async def async_added_to_hass(self) -> None:
        """Add oocsi event listener."""

        @callback
        def channel_update_event(sender, recipient, event):
            """Update state on oocsi update."""
            self._channel_state = event["state"]
            self.async_write_ha_state()

        self._oocsi.subscribe(self._property.channel_name, channel_update_event)

    @property
    def name(self):
        """Return name."""
        return self._property.name

    @property
    def device_info(self):
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._property.device_id)
            },
            "name": self._property.device_name,
            "manufacturer": self._property.manufacturer,
            "model": "DIY OOCSI Device",
            "sw_version": None,
            "via_device": (DOMAIN, self._property.server_name),
        }

    @property
    def icon(self) -> str:
        if self._property.icon is None:
            return "mdi:toggle"
        else:
            return f"mdi:{self._property.icon}"

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._channel_state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._oocsi.send(self._property.channel_name, {"state": True})
        self._channel_state = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._oocsi.send(self._property.channel_name, {"state": False})
        self._channel_state = False
