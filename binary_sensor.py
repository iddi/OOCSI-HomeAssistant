"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass, config_entry, async_add_entities, discovery_info=None
):
    """Set up the Oocsi sensor platform."""
    oocsiGateway = hass.data[DOMAIN]["GATEWAY"][config_entry.entry_id]

    @callback
    async def async_add_binary_sensor(info) -> None:
        api = hass.data[DOMAIN][config_entry.entry_id]
        platform = "binary_sensor"

        await oocsiGateway.async_create_new_platform_entity(
            hass, config_entry, api, BasicSensor, async_add_entities, platform
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            oocsiGateway._signal_new_binary_sensor,
            async_add_binary_sensor,
        )
    )


class BasicSensor(BinarySensorEntity):
    """Basic oocsi binary sensor."""

    def __init__(self, hass, entityProperty):
        self._property = entityProperty
        """Set basic oocsi binary sensor parameters."""

        self._hass = hass
        self._name = self._property.name
        self._oocsi = self._property.oocsi_api()
        self._device_class = self._property.type
        self._attr_unique_id = self._property.channel_name
        self._channel_state = self._property.state

    async def async_added_to_hass(self) -> None:
        """Add oocsi event listener."""

        @callback
        def channel_update_event(sender, recipient, event):
            """Execute oocsi state change."""
            self._channel_state = event["state"]
            self.async_write_ha_state()

        # self._oocsi.subscribe(self._property.channel_name, channel_update_event)
        self._property.subscribe(channel_update_event)

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
    def device_class(self):
        """Return the device class."""
        return self._property.device_type

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self._property.logo is not None:
            return self._property.logo
        else:
            return "mdi:electric-switch"

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._property.state

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        self._oocsi.send(self._property.channel_name, {"state": True})
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        self._oocsi.send(self._property.channel_name, {"state": False})
        self.async_write_ha_state()
