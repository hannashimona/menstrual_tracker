"""Constants for menstrual_tracker."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "menstrual_tracker"
ATTRIBUTION = "Cycle data calculated locally"

CONF_LAST_PERIOD = "last_period_start"
CONF_CYCLE_LENGTH = "cycle_length"
CONF_PERIOD_LENGTH = "period_length"
CONF_SHOW_FERTILITY_ON_CAL = "show_fertility_on_calendar"

DEFAULT_CYCLE_LENGTH = 28
DEFAULT_PERIOD_LENGTH = 5
