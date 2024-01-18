""" Platform for generating and exposing a MUD file. """
import voluptuous as vol
import logging
from pprint import pformat

import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.components.button import ButtonEntity
from homeassistant.components.sensor import SensorEntity

from .mud_aggregator import MUDAggregator
from . import constants


# Validation of the user's configuration
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(constants.INTERFACE_KEY): cv.string,
    vol.Optional(constants.DEPLOY_KEY): cv.string
})

_LOGGER = logging.getLogger("mud_aggregator_button")

def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """ Set up the MUD Aggregator platform. """
    _LOGGER.info(pformat(config))

    if CONF_NAME not in config.keys():
        params = {CONF_NAME: "Home Assistant MUD Aggregator"}
    else:
        params = {CONF_NAME: config[CONF_NAME]}

    if constants.INTERFACE_KEY not in config.keys():
        params[constants.INTERFACE_KEY] = "eth0"
    else:
        params[constants.INTERFACE_KEY] = config[constants.INTERFACE_KEY]

    if constants.DEPLOY_KEY not in config.keys():
        params[constants.DEPLOY_KEY] = constants.DEPLOY_CORE
    else:
        params[constants.DEPLOY_KEY] = config[constants.DEPLOY_KEY]

    add_entities([MUDAggregatorButton(params)])
    return True


class MUDAggregatorButton(ButtonEntity):
    """ This button can recreate and expose the MUD file. """

    def __init__(self, params):
        self._name = params[CONF_NAME]
        _LOGGER.info('Creating %s', self._name)
        self._unique_id = "PoliTo.e-Lite.LM."+"MUD-Aggregator"
        _LOGGER.debug("Unique ID: <%s>", self._unique_id)
        self._interface = params[constants.INTERFACE_KEY]
        _LOGGER.info('Interface to use <%s>', self._interface)

        self._mud_gen = MUDAggregator(params[constants.DEPLOY_KEY])
        self._mud_gen.generate_mud_file()
        self._mud_gen.expose_mud_file(self._interface)

    @property
    def name(self):
        """Name of the entity."""
        return self._name

    @property
    def unique_id(self) -> str | None:
        return self._unique_id

    def press(self) -> None:
        if not self.hass:
            _LOGGER.warning("Variable <hass> is not accessible now!")
            self._mud_gen.generate_mud_file()
        else:
            integration_list = self.hass.data["integrations"]
            self._mud_gen.generate_mud_file(integration_list)

        self._mud_gen.expose_mud_file(self._interface)

    def update(self) -> None:
        """ Update method recreate the MUD periodically. """
        # To call this method is necessary to change the integration type. Button seems to do not support it.
        _LOGGER.info("Automatically updating the MUD file!")
        self.press()

