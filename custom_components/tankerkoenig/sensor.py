"""Representation of Tankerkönig Sensors."""

from datetime import timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorDeviceClass
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_API_KEY,
    CONF_NAME,
    CURRENCY_EURO,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

FUEL_TYPES = {"diesel", "e5", "e10"}

CONF_FUEL_TYPE = "fuel_type"
CONF_RADIUS = "radius"

DEFAULT_NAME = "Tankerkoenig"
DEFAULT_RADIUS = 1.5

ATTR_BRAND = "brand"
ATTR_ADDRESS = "address"
ATTR_STATUS = "status"

ICON = "mdi:gas-station"
ATTRIBUTION = "Data provided by Tankerkönig"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_FUEL_TYPE): vol.All(cv.string, vol.In(FUEL_TYPES)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): cv.Number,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    api_key = config.get(CONF_API_KEY)
    fuel_type = config.get(CONF_FUEL_TYPE)
    name = config.get(CONF_NAME)
    radius = config.get(CONF_RADIUS)

    latitude = hass.config.latitude
    longitude = hass.config.longitude

    api = TankerkoenigApi(api_key)
    add_entities(
        [TankerkoenigSensor(api, name, latitude, longitude, radius, fuel_type)]
    )


class TankerkoenigApi:
    """Representation of the Tankerkönig API."""

    def __init__(self, api_key):
        """Initialize the Tankerkönig API."""
        self._api_key = api_key

    def get_stations(self, latitude, longitude, radius, fuel_type):
        """Get stations matching a perimeter and fuel type from the Tankerkönig API."""
        resource = (
            f"https://creativecommons.tankerkoenig.de/json/list.php"
            f"?apikey={self._api_key}"
            f"&lat={latitude}"
            f"&lng={longitude}"
            f"&rad={radius}"
            f"&type={fuel_type}"
            f"&sort=price"
        )
        try:
            response = requests.get(resource, verify=True, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as ex:
            _LOGGER.error("Error fetching data: %s failed with %s", resource, ex)
            return None
        except ValueError as ex:
            _LOGGER.error("Error parsing data: %s failed with %s", resource, ex)
            return None


class TankerkoenigSensor(Entity):
    """Representation of a Tankerkönig Sensor."""

    def __init__(self, api, name, latitude, longitude, radius, fuel_type):
        """Initialize the Tankerkönig Sensor."""
        self._api = api
        self._name = name
        self._latitude = latitude
        self._longitude = longitude
        self._radius = radius
        self._fuel_type = fuel_type
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the Tankerkönig Sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the Tankerkönig Sensor."""
        return SensorDeviceClass.MONETARY

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the Tankerkönig Sensor."""
        return CURRENCY_EURO

    @property
    def icon(self):
        """Icon to use in the frontend of the Tankerkönig Sensor."""
        return ICON

    @property
    def state(self):
        """Return the state of the Tankerkönig Sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the Tankerkönig Sensor."""
        return self._attributes

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the Tankerkönig Sensor."""
        self._state = None
        self._attributes = {}

        result = self._api.get_stations(
            self._latitude, self._longitude, self._radius, self._fuel_type
        )
        stations = None

        if result:
            try:
                stations = result["stations"]
            except KeyError as ex:
                _LOGGER.error(
                    "Erroneous result found when expecting list of stations: %s", ex
                )
        else:
            _LOGGER.error("Empty result found when expecting list of stations")

        if stations:
            self._state = stations[0]["price"]
            self._attributes[ATTR_BRAND] = stations[0]["brand"].title()
            self._attributes[ATTR_ADDRESS] = (
                stations[0]["street"].title() + stations[0]["houseNumber"]
            )
            self._attributes[ATTR_STATUS] = (
                "open" if stations[0]["isOpen"] else "closed"
            )
            self._attributes[ATTR_LATITUDE] = stations[0]["lat"]
            self._attributes[ATTR_LONGITUDE] = stations[0]["lng"]
            self._attributes[ATTR_ATTRIBUTION] = ATTRIBUTION
