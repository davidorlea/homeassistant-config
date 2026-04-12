"""Representation of ASEAG Next Bus Sensors."""

import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorDeviceClass
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util.dt import utc_from_timestamp, utcnow

_LOGGER = logging.getLogger(__name__)

MODES = {"single", "list"}

CONF_MODE = "mode"
CONF_STOP_ID = "stop_id"
CONF_TRACK = "track"

ATTR_DELAY = "delay"
ATTR_DEPARTURE = "departure"
ATTR_DESTINATION = "destination"
ATTR_LINE = "line"
ATTR_PREDICTIONS = "predictions"

DEFAULT_MODE = "single"
DEFAULT_NAME = "ASEAG Next Bus"

ICON = "mdi:bus"
ATTRIBUTION = "Data provided by ASEAG"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STOP_ID): cv.string,
        vol.Required(CONF_TRACK): cv.string,
        vol.Optional(CONF_MODE, default=DEFAULT_MODE): vol.All(
            cv.string, vol.In(MODES)
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(_1, config, add_entities, _2):
    """Set up the sensor platform."""

    stop_id = config.get(CONF_STOP_ID)
    track = config.get(CONF_TRACK)
    mode = config.get(CONF_MODE)
    name = config.get(CONF_NAME)

    api = AseagApi()
    add_entities([AseagNextBusSensor(api, name, mode, stop_id, track)])


class AseagApi:
    """Representation of the ASEAG API."""

    @staticmethod
    def get_predictions(stop_id):
        """Get predictions matching a stop from the ASEAG API."""
        headers = {"User-Agent": "curl/7.64.1"}
        resource = f"https://mova.aseag.de/mbroker/rest/areainformation/{stop_id}"
        try:
            response = requests.get(resource, headers=headers, verify=True, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as ex:
            _LOGGER.error("Error fetching data: %s failed with %s", resource, ex)
            return None
        except ValueError as ex:
            _LOGGER.error("Error parsing data: %s failed with %s", resource, ex)
            return None


class AseagNextBusSensor(Entity):
    """Representation of a ASEAG Next Bus Sensor."""

    def __init__(self, api, name, mode, stop_id, track):
        """Initialize the ASEAG Next Bus Sensor."""
        self._api = api
        self._name = name
        self._mode = mode
        self._stop_id = stop_id
        self._track = track
        self._predictions = []
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the ASEAG Next Bus Sensor."""
        return f"{self._name} {self._stop_id} {self._track}"

    @property
    def device_class(self):
        """Return the device class of the ASEAG Next Bus Sensor."""
        if self._mode == "single":
            return SensorDeviceClass.TIMESTAMP

    @property
    def icon(self):
        """Icon to use in the frontend of the ASEAG Next Bus Sensor."""
        return ICON

    @property
    def state(self):
        """Return the state of the ASEAG Next Bus Sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the ASEAG Next Bus Sensor."""
        return self._attributes

    def update(self):
        """Fetch new state data for the ASEAG Next Bus Sensor."""
        self._state = None
        self._attributes = {}

        now = utcnow()
        result = self._api.get_predictions(self._stop_id)
        predictions = []

        if result:
            try:
                predictions = [
                    d["stopPrediction"] for d in result["departures"]["departures"]
                ]
            except KeyError as ex:
                _LOGGER.error(
                    "Erroneous result found when expecting list of predictions: %s", ex
                )
        else:
            _LOGGER.error("Empty result found when expecting list of predictions")

        for p in self._predictions:
            if not any(p["tripId"] in subl.values() for subl in predictions):
                predictions.append(p)

        predictions = [p for p in predictions if p["track"] == self._track]
        predictions = [p for p in predictions if self.__get_prediction_time(p) >= now]

        self._predictions = sorted(
            predictions, key=lambda p: self.__get_prediction_time(p)
        )

        if self._predictions and self._mode == "list":
            self._state = len(self._predictions)
            self._attributes[ATTR_PREDICTIONS] = [
                {
                    ATTR_DEPARTURE: self.__get_prediction_time(p).isoformat(),
                    ATTR_DELAY: self.__get_prediction_delay(p),
                    ATTR_LINE: p["lineName"],
                    ATTR_DESTINATION: p["destinationText"],
                }
                for p in self._predictions
            ]
            self._attributes[ATTR_ATTRIBUTION] = ATTRIBUTION

        if self._predictions and self._mode == "single":
            self._state = self.__get_prediction_time(self._predictions[0]).isoformat()
            self._attributes[ATTR_DELAY] = self.__get_prediction_delay(
                self._predictions[0]
            )
            self._attributes[ATTR_LINE] = self._predictions[0]["lineName"]
            self._attributes[ATTR_DESTINATION] = self._predictions[0]["destinationText"]
            self._attributes[ATTR_ATTRIBUTION] = ATTRIBUTION

    @staticmethod
    def __get_prediction_time(prediction):
        """Return prediction time derived from planned and actual time."""
        if prediction["plannedTime"]:
            return utc_from_timestamp(
                int((prediction["actualTime"] or prediction["plannedTime"]) / 1000)
            )

    @staticmethod
    def __get_prediction_delay(prediction):
        """Return prediction delay derived from planned and actual time."""
        if prediction["actualTime"] and prediction["plannedTime"]:
            return int((prediction["actualTime"] - prediction["plannedTime"]) / 1000)
