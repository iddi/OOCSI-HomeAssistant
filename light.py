"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_WHITE,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    COLOR_MODE_RGBWW,
    COLOR_MODE_WHITE,
    SUPPORT_EFFECT,
    LightEntity,
    brightness_supported,
)
from homeassistant.core import callback
import homeassistant.util.color as color_util
from homeassistant.helpers.dispatcher import async_dispatcher_connect

# from . import async_create_new_platform_entity
from .const import DOMAIN


# Handle platform
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Oocsi light platform."""

    oocsiGateway = hass.data[DOMAIN]["GATEWAY"][config_entry.entry_id]

    @callback
    async def async_add_light(info) -> None:
        api = hass.data[DOMAIN][config_entry.entry_id]
        platform = "light"

        await oocsiGateway.async_create_new_platform_entity(
            hass, config_entry, api, BasicLight, async_add_entities, platform
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            oocsiGateway._signal_new_light,
            async_add_light,
        )
    )


class BasicLight(LightEntity):
    """variable oocsi lamp object."""

    # Import & configure entity
    def __init__(self, hass, entityProperty):
        """Set up all relevant variables."""
        # Basic variables
        self._property = entityProperty
        self._hass = hass
        self._oocsi = self._property.oocsi_api()
        self._name = self._property.name

        # self._attr_device_info = {
        #     "name": entity_name,
        #     # "manufacturer": entityProperty["creator"],
        #     "via_device_id": device,
        # }

        # Set properties

        self._attr_unique_id = self._property.channel_name
        self._channel_state = self._property.state

        # self._supportedFeature = entityProperty["type"]

        self._brightness = self._property.brightness
        # self._led_type = entityProperty["led_type"]
        # self._spectrum = entityProperty["spectrum"]

        self._color_temp: int | None = None
        self._color_mode: str | None = None
        self._supported_features = 0
        self._supported_color_modes: set[str]
        self._rgb: tuple[int, int, int] | None = None
        self._rgbw: tuple[int, int, int, int] | None = None
        self._rgbww: tuple[int, int, int, int, int] | None = None
        self._supported_color_modes: set[str] | None = None

        # if entityProperty.get("effect"):
        #     self._attr_supported_features |= SUPPORT_EFFECT
        #     self._effect: str | None = None
        #     self._effect_list = entityProperty["effect"]

    async def _color_setup(self):
        """Pick the right config for the specified lamp."""
        self._supported_color_modes = set()
        led_type = self._property.led_type
        if led_type in ["RGB", "RGBW", "RGBWW"]:

            spectrum = self._property.spectrum

            if "WHITE" in spectrum:
                self._supported_color_modes.add(COLOR_MODE_WHITE)

            if "CCT" in spectrum:
                self._supported_color_modes.add(COLOR_MODE_COLOR_TEMP)

            if "RGB" in spectrum:
                if led_type == "RGBWW":
                    self._supported_color_modes.add(COLOR_MODE_RGBWW)
                    self._color_mode = COLOR_MODE_RGBWW

                if led_type == "RGBW":
                    self._supported_color_modes.add(COLOR_MODE_RGBW)
                    self._color_mode = COLOR_MODE_RGBW

                if led_type == "RGB":
                    self._supported_color_modes.add(COLOR_MODE_RGB)
                    self._color_mode = COLOR_MODE_RGB

        if led_type == "WHITE":
            self._supported_color_modes.add(COLOR_MODE_WHITE)

        if led_type == "CCT":
            self._attr_max_mireds = self._property.min_max[1]
            self._attr_min_mireds = self._property.min_max[0]
            self._supported_color_modes.add(COLOR_MODE_COLOR_TEMP)

        if led_type == "DIMMABLE":
            self._supported_color_modes.add(COLOR_MODE_BRIGHTNESS)

        if led_type == "ONOFF":
            self._supported_color_modes.add(COLOR_MODE_ONOFF)

    async def async_added_to_hass(self) -> None:
        """Create oocsi listener."""
        await self._color_setup()

        @callback
        def channel_update_event(sender, recipient, event, **kwargs: Any):
            """Handle oocsi event."""
            supported_color_modes = self._supported_color_modes or set()
            self._channel_state = event["state"]
            if COLOR_MODE_RGB in supported_color_modes:
                self._rgb = event["colorrgb"]
            if COLOR_MODE_RGBW in supported_color_modes:
                self._rgbw = event["colorrgbw"]
            if COLOR_MODE_RGBWW in supported_color_modes:
                self._rgbww = event["colorrgbww"]
            if brightness_supported(supported_color_modes):
                self._brightness = event["brightness"]
            if COLOR_MODE_COLOR_TEMP in supported_color_modes:
                self._color_temp = event["color_temp"]
            if COLOR_MODE_WHITE in supported_color_modes:
                self._brightness = event["white"]

            self.async_write_ha_state()

        self._oocsi.subscribe(self._property.channel_name, channel_update_event)

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        return self._color_mode

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature in mired."""
        return self._color_temp

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value."""

        if self._rgb is None:
            return None
        rgb_color = self._rgb
        return (rgb_color[0], rgb_color[1], rgb_color[2])

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgb color value."""

        if self._rgbw is None:
            return None
        rgbw_color = self._rgbw
        return (rgbw_color[0], rgbw_color[1], rgbw_color[2], rgbw_color[3])

    @property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the rgb color value."""

        if self._rgbww is None:
            return None
        rgbww_color = self._rgbww
        return (
            rgbww_color[0],
            rgbww_color[1],
            rgbww_color[2],
            rgbww_color[3],
            rgbww_color[4],
        )

    @property
    def supported_color_modes(self) -> set[str] | None:
        """Flag supported color modes."""
        return self._supported_color_modes

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

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
            return "mdi:lightbulb"
        else:
            return f"mdi:{self._property.icon}"

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._effect

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self._effect_list

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._channel_state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        lightsettings = {}
        self._channel_state = True
        lightsettings["state"] = True
        supported_color_modes = self._supported_color_modes or set()

        if ATTR_RGB_COLOR in kwargs and COLOR_MODE_RGB in supported_color_modes:
            self._color_mode = COLOR_MODE_RGB
            self._rgb = kwargs.get(ATTR_RGB_COLOR)
            self._oocsi.send(self._property.channel_name, {"colorrgb": self._rgb})
            lightsettings["colorrgb"] = self._rgb
            lightsettings["brightness"] = self._brightness

        if ATTR_RGBW_COLOR in kwargs and COLOR_MODE_RGBW in supported_color_modes:
            self._color_mode = COLOR_MODE_RGBW
            self._rgbw = kwargs.get(ATTR_RGBW_COLOR)
            lightsettings["colorrgbw"] = self._rgbw
            lightsettings["brightness"] = self._brightness

        if ATTR_RGBWW_COLOR in kwargs and COLOR_MODE_RGBWW in supported_color_modes:
            self._color_mode = COLOR_MODE_RGBWW
            self._rgbww = kwargs.get(ATTR_RGBWW_COLOR)
            lightsettings["colorrgbww"] = self._rgbww
            lightsettings["brightness"] = self._brightness

        if ATTR_BRIGHTNESS in kwargs and brightness_supported(supported_color_modes):
            self._brightness = kwargs.get(ATTR_BRIGHTNESS)
            lightsettings["brightness"] = self._brightness

        if ATTR_WHITE in kwargs and COLOR_MODE_WHITE in supported_color_modes:
            self._color_mode = COLOR_MODE_WHITE
            self._brightness = kwargs.get(ATTR_WHITE)
            lightsettings["brightnessWhite"] = self._brightness
        if ATTR_COLOR_TEMP in kwargs and COLOR_MODE_COLOR_TEMP in supported_color_modes:
            self._color_mode = COLOR_MODE_COLOR_TEMP
            self._color_temp = kwargs[ATTR_COLOR_TEMP]

            if self._property.led_type in ["RGB", "RGBW"]:
                ct_in_rgb = color_util.color_temperature_to_rgb(kwargs[ATTR_COLOR_TEMP])
                lightsettings["colorTempInRGB"] = ct_in_rgb

            elif self._property.led_type in ["CCT", "RGBWW"]:
                lightsettings["colorTemp"] = self._color_temp

        if ATTR_EFFECT in kwargs:
            self._effect = kwargs[ATTR_EFFECT]
            lightsettings["effect"] = self._effect

        self._oocsi.send(self._property.channel_name, lightsettings)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._oocsi.send(self._property.channel_name, {"state": False})
        self._channel_state = False
