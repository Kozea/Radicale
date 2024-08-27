import json
from enum import Enum
from typing import Sequence

from radicale import pathutils, utils
from radicale.log import logger

INTERNAL_TYPES: Sequence[str] = ("none", "rabbitmq")


def load(configuration):
    """Load the storage module chosen in configuration."""
    try:
        return utils.load_plugin(
            INTERNAL_TYPES, "hook", "Hook", BaseHook, configuration)
    except Exception as e:
        logger.warning(e)
        logger.warning("Hook \"%s\" failed to load, falling back to \"none\"." % configuration.get("hook", "type"))
        configuration = configuration.copy()
        configuration.update({"hook": {"type": "none"}}, "hook", privileged=True)
        return utils.load_plugin(
            INTERNAL_TYPES, "hook", "Hook", BaseHook, configuration)


class BaseHook:
    def __init__(self, configuration):
        """Initialize BaseHook.

        ``configuration`` see ``radicale.config`` module.
        The ``configuration`` must not change during the lifetime of
        this object, it is kept as an internal reference.

        """
        self.configuration = configuration

    def notify(self, notification_item):
        """Upload a new or replace an existing item."""
        raise NotImplementedError


class HookNotificationItemTypes(Enum):
    CPATCH = "cpatch"
    UPSERT = "upsert"
    DELETE = "delete"


def _cleanup(path):
    sane_path = pathutils.strip_path(path)
    attributes = sane_path.split("/") if sane_path else []

    if len(attributes) < 2:
        return ""
    return attributes[0] + "/" + attributes[1]


class HookNotificationItem:

    def __init__(self, notification_item_type, path, content):
        self.type = notification_item_type.value
        self.point = _cleanup(path)
        self.content = content

    def to_json(self):
        return json.dumps(
            self,
            default=lambda o: o.__dict__,
            sort_keys=True,
            indent=4
        )
