import datetime
import logging
from typing import get_args


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the Jewish Calendar services."""
