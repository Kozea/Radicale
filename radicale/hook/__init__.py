import json
from enum import Enum

from radicale import utils

INTERNAL_TYPES = ("none", "rabbitmq")


def load(configuration):
    """Load the storage module chosen in configuration."""
    return utils.load_plugin(
        INTERNAL_TYPES, "hook", "Hook", configuration)


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
    UPSERT = "upsert"
    DELETE = "delete"


class HookNotificationItem:

    def __init__(self, notification_item_type, content):
        self.type = notification_item_type.value
        self.content = content

    def to_json(self):
        return json.dumps(
            self,
            default=lambda o: o.__dict__,
            sort_keys=True,
            indent=4
        )
