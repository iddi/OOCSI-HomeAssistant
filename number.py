"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect


from .const import DOMAIN


async def async_setup_entry(
    hass, config_entry, async_add_entities, discovery_info=None
):
    """Set up the Oocsi number platform."""

    oocsiGateway = hass.data[DOMAIN]["GATEWAY"][config_entry.entry_id]

    @callback
    async def async_add_number(info) -> None:
        api = hass.data[DOMAIN][config_entry.entry_id]
        platform = "number"

        await oocsiGateway.async_create_new_platform_entity(
            hass, BasicNumber, async_add_entities, platform
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            oocsiGateway._signal_new_number,
            async_add_number,
        )
    )


class BasicNumber(NumberEntity):
    """Basic oocsi number input."""

    def __init__(self, hass, entityProperty):
        """Set basic oocsi number input parameters."""
        self._property = entityProperty
        self._hass = hass
        self._oocsi = self._property.oocsi_api()

        self._attr_unique_id = self._property.channel_name
        self._attr_max_value = self._property.min_max[1]
        self._attr_min_value = self._property.min_max[0]
        self._attr_step = self._property.step
        self._channel_value = self._property.value
        self._attr_unit_of_measurement = self._property.unit

        if "logo" in entityProperty:
            self._icon = entityProperty["logo"]
        else:
            self._icon = "mdi:dialpad"

    async def async_added_to_hass(self) -> None:
        """Add oocsi event listener."""

        @callback
        def channel_update_event(sender, recipient, event):
            """Execute Oocsi state change."""
            self._channel_value = event["value"]
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
        """Return icon."""
        if self._property.icon is None:
            return "mdi:calculator"
        else:
            return f"mdi:{self._property.icon}"

    @property
    def value(self):
        """Return value."""
        return self._channel_value

    async def async_set_value(self, value: float):
        """Set and send the value."""
        self._channel_value = value
        self._oocsi.send(self._property.channel_name, {"value": self._channel_value})
