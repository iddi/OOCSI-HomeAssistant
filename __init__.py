"""The Oocsi for HomeAssistant integration."""
from __future__ import annotations

import logging
from typing import ClassVar

from oocsi import OOCSI as oocsiApi
from voluptuous.validators import Number


from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.dispatcher import async_dispatcher_send


from .const import DATA_OOCSI, DOMAIN, OOCSI_ENTITY

PLATFORMS = []
ACTIVATEDPLATFORMS = []
_LOGGER = logging.getLogger(__name__)


# Homeassistant starting point
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Oocsi for HomeAssistant from a config entry."""

    # Import oocsi variables
    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    # Create and save oocsi
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = oocsiApi(
        name, host, port, None, _LOGGER.info, 1
    )
    # Save oocsi connection to entity
    api = hass.data[DOMAIN][entry.entry_id]

    # Announce presence homeassistant, should be rententious soon
    api.send("heyOOCSI?", {"_RETAIN": 50000, "homeassistant": "on"})
    # Create interview storage
    if OOCSI_ENTITY not in hass.data[DOMAIN]:
        hass.data[DOMAIN][OOCSI_ENTITY] = {}
        hass.data[DOMAIN][OOCSI_ENTITY][entry.entry_id] = {}

    # Start interviewing process

    og = oocsiGateway(hass, entry, api)
    if "GATEWAY" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["GATEWAY"] = {}

    PLATFORMS = ["number", "binary_sensor", "sensor", "switch", "light"]
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    hass.data[DOMAIN]["GATEWAY"][entry.entry_id] = og
    await og.async_subscribe_heyOOCSI()

    # Finish
    return True


class oocsiGateway:
    # Creates entities out of interviews
    def __init__(self, hass, entry, api) -> None:
        self._api = api
        self._hass = hass
        self._entry = entry
        self._ent_reg = entity_registry.async_get(hass)
        self._signal_new_binary_sensor = (
            f"oocsi_new_binary_sensor_{self._entry.entry_id}"
        )
        self._signal_new_sensor = f"oocsi_new_sensor_{self._entry.entry_id}"
        self._signal_new_number = f"oocsi_new_number_{self._entry.entry_id}"
        self._signal_new_light = f"oocsi_new_light_{self._entry.entry_id}"
        self._signal_new_switch = f"oocsi_new_switch_{self._entry.entry_id}"

        self._oocsi_resource_type_to_signal_new_device = {
            "switch": self._signal_new_switch,
            "light": self._signal_new_light,
            "number": self._signal_new_number,
            "sensor": self._signal_new_sensor,
            "binary_sensor": self._signal_new_binary_sensor,
        }

        self._devices = oocsiDeviceStorage(self._hass, self._entry)

    @callback
    async def async_subscribe_heyOOCSI(self):
        self._api.subscribe("heyOOCSI!", self._handle_interview_event)

    @callback
    def _async_add_device_callback(
        self, resource_type, device=None, force: bool = False
    ):
        async_dispatcher_send(
            self._hass,
            self._oocsi_resource_type_to_signal_new_device[resource_type],
            device,  # Don't send device if None, it would override default value in listeners
        )

    @callback
    def _handle_interview_event(self, sender, recipient, event) -> None:
        # Handle interview by comparing interview entries to previous registrations
        interviews = self._devices.return_entries()
        _LOGGER.info(f"heyOOCSI! Interview received from {sender} from oocsi")
        if event.items() not in interviews.items():

            self._devices.add_interview(event)

            # add new entries
            # Check which platforms must be started for the interviewed entities
            devices = self._devices.getOocsiDevice()
            for device in devices:

                device_id = self._devices.get_device_id(device)
                self._api.subscribe(f"presence({device_id})", self.handle_disconnection)
                entities = self._devices.getOocsiDeviceEntities(device)

                for entity in entities:

                    entity_type = self._devices.getOocsiEntityType(device, entity)
                    self._async_add_device_callback(
                        entity_type,
                        entity,
                    )

    @callback
    def handle_disconnection(self, sender, recipient, event):
        # Retrieve device
        leaving_device = event["leave"]
        # Check devices with the ID
        devices = self._devices.getOocsiDevice()
        for device in devices:

            if self._devices.get_device_id(device) == leaving_device:

                # Check if they are registered
                entities = self._devices.getOocsiDeviceEntities(device)
                for entity in entities:

                    entity_type = self._devices.getOocsiEntityType(device, entity)
                    channelname = self._devices.getOocsiEntityChannel(device, entity)
                    leaving_entity = self._ent_reg.async_get_entity_id(
                        entity_type,
                        DOMAIN,
                        channelname,
                    )
                    self._api.unsubscribe(channelname)
                    self._ent_reg.async_remove(leaving_entity)

                    self._ent_reg = entity_registry.async_get(self._hass)

                    _LOGGER.info(f"Removed {entity} from oocsi {entity_type}")

                self._devices.remove_interview(device)

    @callback
    async def async_create_new_platform_entity(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api,
        entity_type_platform,
        async_add_entities,
        platform,
    ):
        """Add entities per platform."""
        # Per platform get their entries and create an entity dictionary
        entities_to_add = []
        devices = self._devices.getOocsiDevice()
        for device in devices:
            entities = self._devices.getOocsiDeviceEntities(device)
            for entity in entities:
                entity_type = self._devices.getOocsiEntityType(device, entity)
                if entity_type == platform:
                    servername = entry.data[CONF_NAME]
                    device_id = [
                        self._devices.get_device_id(device),
                        device,
                        servername,
                    ]
                    entity_info = self._devices.return_entity_info(device, entity)
                    creator = self._devices.return_creator(device)
                    oocsi_entity = oocsiEntity(
                        entity, creator, entity_info, self._api, device_id
                    )
                    entities_to_add.append(entity_type_platform(hass, oocsi_entity))
                _LOGGER.info("Added %s from %s as entity", entity, device)
            # Add entities
        async_add_entities(entities_to_add)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data[DOMAIN][OOCSI_ENTITY][entry.entry_id].clear()
    if unload_ok:
        api = hass.data[DOMAIN][entry.entry_id]
        api.send("heyOOCSI?", {"_RETAIN": 50000, "homeassistant": "off"})
        api.stop()

    return unload_ok


class oocsiDeviceStorage:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._storage = {}

    def return_entries(self):
        return self._storage

    def add_interview(self, interview):
        self._storage |= interview
        return

    def remove_interview(self, device):
        del self._storage[device]
        return

    def return_creator(self, deviceKey):
        if "creator" in self._storage[deviceKey]["properties"]:
            return self._storage[deviceKey]["properties"]["creator"]

    def return_entity_info(self, deviceKey, entityKey):
        return self._storage[deviceKey]["components"][entityKey]

    def getOocsiDevice(self):
        return self._storage.keys()

    def get_device_id(self, deviceKey):
        return self._storage[deviceKey]["properties"]["device_id"]

    def getOocsiDeviceEntities(self, deviceKey):
        return self._storage[deviceKey]["components"].keys()

    def getOocsiEntityType(self, deviceKey, entityKey):
        return self._storage[deviceKey]["components"][entityKey]["type"]

    def getOocsiEntityChannel(self, deviceKey, entityKey):
        return self._storage[deviceKey]["components"][entityKey]["channel_name"]


class oocsiEntity:
    """Simple oocsi interview unwrapper."""

    def __init__(self, entity, creator, entity_interview, api, device_id):
        self._entity_interview = entity_interview
        self._entity_name = entity
        self._api = api
        self._channel = self._entity_interview["channel_name"]
        self._creator = creator
        self._device_id = device_id[0]
        self._device_name = device_id[1]
        self._server_name = device_id[2]

        if "state" in self._entity_interview:
            self._current_state = self._entity_interview["state"]

    def oocsi_api(self) -> classmethod:
        return self._api

    @property
    def manufacturer(self) -> str:
        """Return Creator"""
        return self._creator

    @property
    def device_name(self) -> str:
        """Return the entity name."""
        return self._device_name

    @property
    def device_id(self) -> str:
        """Return the entity name."""
        return self._device_id

    @property
    def server_name(self) -> str:
        """Return the entity name."""
        return self._server_name

    @property
    def name(self) -> str:
        """Return the entity name."""
        return self._entity_name

    @property
    def channel_name(self) -> str:
        """Return the entity oocsi channel."""
        return self._channel

    @property
    def device_type(self) -> str:
        """Return the oocsi entity device class."""
        return self._entity_interview["sensor_type"]

    @property
    def entity_type(self) -> str:
        """Return the oocsi type."""
        return self._entity_interview["type"]

    @property
    def unit(self) -> str:
        """Return the sensor or input unit."""
        if "unit" in self._entity_interview:
            return self._entity_interview["unit"]

    @property
    def step(self) -> str:
        """Return the sensor or input unit."""
        if "step" in self._entity_interview:
            return self._entity_interview["step"]

    @property
    def value(self) -> str:
        """Return the default value."""
        if "value" in self._entity_interview:
            return self._entity_interview["value"]

    @property
    def state(self) -> bool:
        """Return the default state."""
        return self._current_state

    @property
    def icon(self) -> str:
        """Return the icon."""
        if "icon" in self._entity_interview:
            return self._entity_interview["icon"]

    @property
    def min_max(self) -> list[float]:
        """Return a minimal and maximum value."""
        if "min_max" in self._entity_interview:
            return self._entity_interview["min_max"]

    @property
    def brightness(self) -> str:
        """Return the brightness."""
        if "brightness" in self._entity_interview:
            return self._entity_interview["brightness"]

    @property
    def led_type(self) -> str:
        """Return the LED type"""
        if "led_type" in self._entity_interview:
            return self._entity_interview["led_type"]

    @property
    def spectrum(self) -> list[str]:
        """ "Return the supported spectrum"""
        if "spectrum" in self._entity_interview:
            return self._entity_interview["spectrum"]


class oocsiSwitchDevice:
    def __init__(self) -> None:
        pass

    def subscribe_for_updates(self, channel_update_event):
        self._api.subscribe(self._channel, channel_update_event)

    def send_state(self) -> bool:
        self._api.send(self._channel, {"state": self._current_state})
        return True

    def turn_on(self) -> bool:
        self._current_state = True
        self.send_state

    def turn_off(self) -> bool:
        self._current_state = False
        self.send_state
