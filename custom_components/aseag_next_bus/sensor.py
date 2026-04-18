"""Representation of ASEAG Next Bus Sensors."""

from datetime import datetime
import logging
from typing import Any, cast

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorDeviceClass
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.dt import utc_from_timestamp, utcnow
import requests
import voluptuous as vol

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


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    stop_id: str = config[CONF_STOP_ID]
    track: str = config[CONF_TRACK]
    mode: str = config[CONF_MODE]
    name: str = config[CONF_NAME]

    api = AseagApi()
    add_entities([AseagNextBusSensor(api, name, mode, stop_id, track)])


class AseagApi:
    """Representation of the ASEAG API."""

    @staticmethod
    def get_predictions(stop_id: str) -> dict[str, Any] | None:
        """Get predictions matching a stop from the ASEAG API."""
        headers = {"User-Agent": "curl/7.64.1"}
        resource = f"https://mova.aseag.de/mbroker/rest/areainformation/{stop_id}"
        try:
            response = requests.get(
                resource, headers=headers, verify=True, timeout=(5, 10)
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json())
        except requests.exceptions.JSONDecodeError as ex:
            _LOGGER.error("Error parsing data: %s failed with %s", resource, ex)
            return None
        except requests.exceptions.HTTPError as ex:
            if ex.response.status_code >= 500:
                _LOGGER.debug("Error fetching data: %s failed with %s", resource, ex)
            else:
                _LOGGER.error("Error fetching data: %s failed with %s", resource, ex)
            return None
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as ex:
            _LOGGER.debug("Error fetching data: %s failed with %s", resource, ex)
            return None
        except requests.exceptions.RequestException as ex:
            _LOGGER.error("Error fetching data: %s failed with %s", resource, ex)
            return None


class AseagNextBusSensor(Entity):
    """Representation of a ASEAG Next Bus Sensor."""

    def __init__(
        self, api: AseagApi, name: str, mode: str, stop_id: str, track: str
    ) -> None:
        """Initialize the ASEAG Next Bus Sensor."""
        self._api: AseagApi = api
        self._name: str = name
        self._mode: str = mode
        self._stop_id: str = stop_id
        self._track: str = track
        self._predictions: list[dict[str, Any]] = []
        self._state: str | int | None = None
        self._attributes: dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Return the name of the ASEAG Next Bus Sensor."""
        return f"{self._name} {self._stop_id} {self._track}"

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class of the ASEAG Next Bus Sensor."""
        if self._mode == "single":
            return SensorDeviceClass.TIMESTAMP
        return None

    @property
    def icon(self) -> str:
        """Icon to use in the frontend of the ASEAG Next Bus Sensor."""
        return ICON

    @property
    def state(self) -> str | int | None:
        """Return the state of the ASEAG Next Bus Sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the ASEAG Next Bus Sensor."""
        return self._attributes

    def update(self) -> None:
        """Fetch new state data for the ASEAG Next Bus Sensor."""
        self._state = None
        self._attributes = {}

        now: datetime = utcnow()
        result: dict[str, Any] | None = self._api.get_predictions(self._stop_id)
        predictions: list[Any] = []

        if result:
            try:
                predictions = [
                    d["stopPrediction"] for d in result["departures"]["departures"]
                ]
            except (KeyError, TypeError) as ex:
                _LOGGER.error(
                    "Erroneous result found: %s failed with %s",
                    result,
                    ex,
                )

        for p in self._predictions:
            if not any(p["tripId"] in subl.values() for subl in predictions):
                predictions.append(p)

        predictions = [p for p in predictions if p["track"] == self._track]
        predictions = [p for p in predictions if p["cancelled"] is False]
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
    def __get_prediction_time(prediction: dict[str, Any]) -> datetime:
        """Return prediction time derived from planned and actual time."""
        if "actualTime" in prediction:
            return utc_from_timestamp(int(prediction["actualTime"] / 1000))
        return utc_from_timestamp(int(prediction["plannedTime"] / 1000))

    @staticmethod
    def __get_prediction_delay(prediction: dict[str, Any]) -> int | None:
        """Return prediction delay derived from planned and actual time."""
        if "actualTime" in prediction and "plannedTime" in prediction:
            return int((prediction["actualTime"] - prediction["plannedTime"]) / 1000)
        return None
