"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Oocsi sensor platform."""
    oocsiGateway = hass.data[DOMAIN]["GATEWAY"][config_entry.entry_id]

    @callback
    async def async_add_sensor(info) -> None:
        api = hass.data[DOMAIN][config_entry.entry_id]
        platform = "sensor"

        await oocsiGateway.async_create_new_platform_entity(
            hass, config_entry, api, BasicSensor, async_add_entities, platform
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            oocsiGateway._signal_new_sensor,
            async_add_sensor,
        )
    )


class BasicSensor(SensorEntity):
    """Basic oocsi sensor."""

    def __init__(self, hass, entityProperty):
        """Set basic oocsi sensor parameters."""
        self._property = entityProperty
        self._hass = hass
        self._oocsi = self._property.oocsi_api()
        self._attr_unique_id = self._property.channel_name
        self._channel_value = self._property.value

    async def async_added_to_hass(self) -> None:
        """Add oocsi event listener."""

        @callback
        def channel_update_event(sender, recipient, event):
            """Execute Oocsi state change."""
            self._channel_value = event["value"]
            self.async_write_ha_state()

        self._oocsi.subscribe(self._property.channel_name, channel_update_event)

    @property
    def device_class(self) -> str:
        """Return the unit of measurement."""
        return self._property.device_type

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._property.unit

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
            return "mdi:flask"
        else:
            return f"mdi:{self._property.icon}"

    @property
    def state(self):
        """Return true if the switch is on."""
        return self._channel_value
