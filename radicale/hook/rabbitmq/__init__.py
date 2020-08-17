import pika

from radicale import hook
from radicale.hook import HookNotificationItem


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

    def notify(self, notification_item):
        if isinstance(notification_item, HookNotificationItem):
            self.channel.basic_publish(
                exchange='',
                routing_key=self.topic,
                body=notification_item.to_json().encode(encoding=self.encoding))
