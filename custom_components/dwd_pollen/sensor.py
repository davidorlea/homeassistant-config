"""Representation of DWD Pollen Sensor."""

from datetime import datetime, timedelta
import logging
from typing import Any, cast

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, PERCENTAGE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
import requests
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=60)

POLLEN_TYPES = {
    "alder",
    "ambrosia",
    "ash",
    "birch",
    "grass",
    "hazel",
    "mugwort",
    "rye",
    "tree",
}

CONF_PARTREGION_ID = "partregion_id"
CONF_POLLEN_TYPES = "pollen_types"

ATTR_DESCRIPTION = "description"
ATTR_LAST_UPDATE = "last_update"
ATTR_NEXT_UPDATE = "next_update"
ATTR_PARTREGION_NAME = "partregion_name"
ATTR_REGION_NAME = "region_name"

DEFAULT_NAME = "DWD Pollen"
DEFAULT_POLLEN_TYPES = [
    "alder",
    "ambrosia",
    "ash",
    "birch",
    "grass",
    "hazel",
    "mugwort",
    "rye",
]

ICON = "mdi:flower"
ATTRIBUTION = "Data provided by Deutscher Wetterdienst"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PARTREGION_ID): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_POLLEN_TYPES, default=DEFAULT_POLLEN_TYPES): vol.All(
            cv.ensure_list, [vol.In(POLLEN_TYPES)]
        ),
    }
)


def setup_platform(
    _hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    _discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    name: str = config[CONF_NAME]
    partregion_id: int = config[CONF_PARTREGION_ID]
    pollen_types: list[str] = config[CONF_POLLEN_TYPES]

    api = DwdPollenApi()
    for pollen_type in pollen_types:
        add_entities([DwdPollenSensor(api, name, partregion_id, pollen_type)])


class DwdPollenApi:
    """Representation of the DWD Pollen API."""

    @staticmethod
    def get_exposure() -> dict[str, Any] | None:
        """Get pollen exposure from the DWD Pollen API."""
        resource = (
            "https://opendata.dwd.de/climate_environment/health/alerts/s31fg.json"
        )
        try:
            response = requests.get(resource, verify=True, timeout=(5, 10))
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


class DwdPollenSensor(Entity):
    """Representation of a DWD Pollen Sensor."""

    def __init__(
        self,
        api: DwdPollenApi,
        name: str,
        partregion_id: int,
        pollen_type: str,
    ) -> None:
        """Initialize the DWD Pollen Sensor."""
        self._api: DwdPollenApi = api
        self._name: str = name
        self._partregion_id: int = partregion_id
        self._pollen_type: str = pollen_type
        self._state: int | None = None
        self._attributes: dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Return the name of the DWD Pollen Sensor."""
        return f"{self._name} {self._partregion_id} {self._pollen_type}"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of the DWD Pollen Sensor."""
        return PERCENTAGE

    @property
    def icon(self) -> str:
        """Icon to use in the frontend of the DWD Pollen Sensor."""
        return ICON

    @property
    def state(self) -> int | None:
        """Return the state of the DWD Pollen Sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the DWD Pollen Sensor."""
        return self._attributes

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Fetch new state data for the DWD Pollen Sensor."""
        self._state = None
        self._attributes = {}

        result: dict[str, Any] | None = self._api.get_exposure()
        exposure: dict[str, Any] = {}

        if result:
            try:
                today = datetime.today()
                yesterday = today - timedelta(days=1)
                before_yesterday = yesterday - timedelta(days=1)

                last_update = datetime.strptime(
                    result["last_update"], "%Y-%m-%d %H:%M Uhr"
                )
                next_update = datetime.strptime(
                    result["next_update"], "%Y-%m-%d %H:%M Uhr"
                )

                partregion = self.__find_partregion(
                    result["content"], self._partregion_id
                )

                if last_update.date() == today.date():
                    exposure["level"] = self.__calculate_level(
                        partregion["Pollen"], self._pollen_type, "today"
                    )
                elif last_update.date() == yesterday.date():
                    exposure["level"] = self.__calculate_level(
                        partregion["Pollen"], self._pollen_type, "tomorrow"
                    )
                elif last_update.date() == before_yesterday.date():
                    exposure["level"] = self.__calculate_level(
                        partregion["Pollen"], self._pollen_type, "dayafter_to"
                    )
                else:
                    exposure["level"] = -1

                exposure["last_update"] = last_update
                exposure["next_update"] = next_update
                exposure["region_name"] = partregion["region_name"]
                exposure["partregion_name"] = partregion["partregion_name"]
            except (KeyError, TypeError) as ex:
                _LOGGER.error(
                    "Erroneous result found: %s failed with %s",
                    result,
                    ex,
                )

        if exposure:
            if exposure["level"] >= 0:
                self._state = round(exposure["level"] / 6 * 100)
            self._attributes[ATTR_DESCRIPTION] = self.__get_description(
                exposure["level"]
            )
            self._attributes[ATTR_LAST_UPDATE] = exposure["last_update"]
            self._attributes[ATTR_NEXT_UPDATE] = exposure["next_update"]
            self._attributes[ATTR_REGION_NAME] = exposure["region_name"]
            self._attributes[ATTR_PARTREGION_NAME] = exposure["partregion_name"]
            self._attributes[ATTR_ATTRIBUTION] = ATTRIBUTION

    @staticmethod
    def __find_partregion(
        partregion_list: list[dict[str, Any]], partregion_id: int
    ) -> dict[str, Any]:
        """Extract partregion from list if all partregions."""
        for partregion in partregion_list:
            if partregion["partregion_id"] == partregion_id:
                return partregion
        return {}

    @staticmethod
    def __calculate_level(
        pollen_list: dict[str, Any], pollen_category: str, day: str
    ) -> int:
        """Calculate exposure level of a pollen category for a certain day."""
        pollen_mapping = {
            "alder": ["Erle"],
            "ambrosia": ["Ambrosia"],
            "ash": ["Esche"],
            "birch": ["Birke"],
            "grass": ["Graeser"],
            "hazel": ["Hasel"],
            "mugwort": ["Beifuss"],
            "rye": ["Roggen"],
            "tree": ["Beifuss", "Birke", "Erle", "Esche", "Hasel", "Roggen"],
        }
        level_mapping = {
            "0": 0,
            "0-1": 1,
            "1": 2,
            "1-2": 3,
            "2": 4,
            "2-3": 5,
            "3": 6,
        }
        pollen_levels = []

        for pollen_type in pollen_mapping.get(pollen_category, []):
            pollen_levels.append(level_mapping.get(pollen_list[pollen_type][day], -1))

        return max(pollen_levels, default=-1)

    @staticmethod
    def __get_description(level: int) -> str:
        """Get short description of an exposure level."""
        description_mapping = {
            0: "no level of exposure",
            1: "no to low level of exposure",
            2: "low level of exposure",
            3: "low to medium level of exposure",
            4: "medium level of exposure",
            5: "medium to high level exposure",
            6: "high level of exposure",
        }
        return description_mapping.get(level, "unknown level of exposure")
