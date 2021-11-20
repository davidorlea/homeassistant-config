"""Representation of Dr. Plano Sensors."""

from datetime import datetime, timedelta
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, PERCENTAGE
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

CONF_PLACE_ID = "place_id"
CONF_TOTAL = "total"

ATTR_COURSES = "courses"
ATTR_COURSE_START = "start"
ATTR_COURSE_END = "end"
ATTR_COURSE_FREE = "free"
ATTR_COURSE_BOOKED = "booked"
ATTR_COURSE_OCCUPANCY = "occupancy"

DEFAULT_NAME = "Dr. Plano"

ICON = "mdi:weight-lifter"
ATTRIBUTION = "Data provided by Dr. Plano"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PLACE_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TOTAL, default=0): cv.positive_int,
    }
)


def setup_platform(_1, config, add_entities, _2):
    """Set up the sensor platform."""

    name = config.get(CONF_NAME)
    place_id = config.get(CONF_PLACE_ID)
    total = config.get(CONF_TOTAL)

    api = DrPlanoApi()
    add_entities([DrPlanoSensor(api, name, place_id, total)])


class DrPlanoCourse:
    """Representation of a Dr. Plano Course."""

    def __init__(self, course):
        """Initialize the Dr. Plano Course."""
        self.state = course["state"]
        self.booked_slots = course["currentCourseParticipantCount"]
        self.free_slots = (
            course["maxCourseParticipantCount"]
            - course["currentCourseParticipantCount"]
        )
        self.maximum_slots = course["maxCourseParticipantCount"]
        self.start_date = datetime.fromtimestamp(course["dateList"][0]["start"] / 1000)
        self.end_date = datetime.fromtimestamp(course["dateList"][0]["end"] / 1000)


class DrPlanoApi:
    """Representation of the Dr. Plano API."""

    @staticmethod
    def get_courses(place_id, start_date, end_date):
        """Get courses between start and end dates from the Dr. Plano API."""
        start = int(start_date.timestamp() * 1000)
        end = int(end_date.timestamp() * 1000)

        headers = {"User-Agent": "curl/7.64.1"}
        resource = (
            f"https://backend.dr-plano.com/courses_dates"
            f"?id={place_id}"
            f"&start={start}"
            f"&end={end}"
        )

        try:
            response = requests.get(resource, headers=headers, verify=True, timeout=10)
            response.raise_for_status()

            courses = []

            for course in response.json():
                courses.append(DrPlanoCourse(course))

            return sorted(courses, key=lambda course: course.start_date)

        except requests.exceptions.RequestException as ex:
            _LOGGER.error("Error fetching data: %s failed with %s", resource, ex)
            return None
        except ValueError as ex:
            _LOGGER.error("Error parsing data: %s failed with %s", resource, ex)
            return None


class DrPlanoSensor(Entity):
    """Representation of a Dr. Plano Sensor."""

    def __init__(self, api, name, place_id, total):
        """Initialize the Dr. Plano Sensor."""
        self._api = api
        self._name = name
        self._place_id = place_id
        self._total = total
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the Dr. Plano Sensor."""
        return f"{self._name} {self._place_id}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the Dr. Plano Sensor."""
        return PERCENTAGE

    @property
    def icon(self):
        """Icon to use in the frontend of the Dr. Plano Sensor."""
        return ICON

    @property
    def state(self):
        """Return the state of the Dr. Plano Sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the Dr. Plano Sensor."""
        return self._attributes

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get new data from the Dr. Plano API."""
        self._state = None
        self._attributes = {}

        now = datetime.now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = now.replace(hour=23, minute=59, second=59, microsecond=9999)

        courses = self._api.get_courses(self._place_id, day_start, day_end)
        occupancies = self.get_ordered_occupancies(courses)

        if courses and occupancies:
            self._state = round(
                self.get_time_occupancy(occupancies, now, self._total) * 100
            )
            self._attributes[ATTR_COURSES] = [
                {
                    ATTR_COURSE_START: course.start_date.isoformat(),
                    ATTR_COURSE_END: course.end_date.isoformat(),
                    ATTR_COURSE_FREE: course.free_slots,
                    ATTR_COURSE_BOOKED: course.booked_slots,
                    ATTR_COURSE_OCCUPANCY: self.get_course_occupancy(
                        occupancies, course, self._total
                    ),
                }
                for course in courses
            ]
            self._attributes[ATTR_ATTRIBUTION] = ATTRIBUTION

    @staticmethod
    def get_ordered_times(courses):
        """Calculate an ordered list of start and end timestamps of all courses."""
        times = []

        for course in courses:
            times.append(course.start_date)
            times.append(course.end_date)

        times = sorted(list(set(times)))

        return times

    @staticmethod
    def get_ordered_occupancies(courses):
        """Calculate an ordered list of occupancies for all timestamps."""
        times = DrPlanoSensor.get_ordered_times(courses)
        occupancies = []

        for time in times:
            count = 0
            total = 0

            for course in courses:
                if course.start_date <= time < course.end_date:
                    count += course.booked_slots
                    total += course.maximum_slots

            occupancies.append({"time": time, "count": count, "total": total})

            _LOGGER.debug(
                "At %s there is a count of %s and a total of %s",
                time.strftime("%H:%M"),
                count,
                total,
            )

        return occupancies

    @staticmethod
    def get_time_occupancy(occupancies, time, conf_total=0):
        """Calculate weighted occupancy for a specific time."""
        count = 0
        total = 0

        for occupancy in occupancies:
            if occupancy["time"] <= time:
                count = occupancy["count"]
                total = conf_total or occupancy["total"]

        _LOGGER.debug(
            "The time %s has a count of %s and a total of %s",
            time.strftime("%H:%M"),
            count,
            total,
        )

        return round(count / total, 2) if total else 0

    @staticmethod
    def get_course_occupancy(occupancies, course, conf_total=0):
        """Calculate weighted occupancy for a specific course."""
        count = 0
        total = 0

        for occupancy in occupancies:
            if course.start_date <= occupancy["time"] < course.end_date:
                count += occupancy["count"]
                total += conf_total or occupancy["total"]

        _LOGGER.debug(
            "The course from %s to %s has a count of %s and a total of %s",
            course.start_date.strftime("%H:%M"),
            course.end_date.strftime("%H:%M"),
            count,
            total,
        )

        return round(count / total, 2) if total else 0
