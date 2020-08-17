import pika
import json

from radicale import hook
from enum import Enum


class Hook(hook.BaseHook):

    def __init__(self, configuration):
        super().__init__(configuration)
        endpoint = configuration.get("hook", "rabbitmq_endpoint")
        self.topic = configuration.get("hook", "rabbitmq_topic")
        self.encoding = configuration.get("encoding", "stock")

        self._make_connection_synced(endpoint)
        self._make_declare_queue_synced(self.topic)

    def _make_connection_synced(self, endpoint):
        parameters = pika.URLParameters(endpoint)
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()

    def _make_declare_queue_synced(self, topic):
        self.channel.queue_declare(queue=topic)

    def notify(self, content):
        if not isinstance(content, QueueItem):
            return
        self.channel.basic_publish(exchange='',
                                   routing_key=self.topic,
                                   body=content.to_json().encode(encoding=self.encoding))


class QueueItemTypes(Enum):
    UPSERT = "upsert"
    DELETE = "delete"


class QueueItem:

    def __init__(self, queue_item_type, content):
        self.type = queue_item_type.value
        self.content = content

    def to_json(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)
