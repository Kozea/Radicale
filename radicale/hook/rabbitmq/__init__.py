import pika
from pika.exceptions import ChannelWrongStateError, StreamLostError

from radicale import hook
from radicale.hook import HookNotificationItem
from radicale.log import logger


class Hook(hook.BaseHook):

    def __init__(self, configuration):
        super().__init__(configuration)
        self._endpoint = configuration.get("hook", "rabbitmq_endpoint")
        self._topic = configuration.get("hook", "rabbitmq_topic")
        self._queue_type = configuration.get("hook", "rabbitmq_queue_type")
        self._encoding = configuration.get("encoding", "stock")

        self._make_connection_synced()
        self._make_declare_queue_synced()

    def _make_connection_synced(self):
        parameters = pika.URLParameters(self._endpoint)
        connection = pika.BlockingConnection(parameters)
        self._channel = connection.channel()

    def _make_declare_queue_synced(self):
        self._channel.queue_declare(queue=self._topic, durable=True, arguments={"x-queue-type": self._queue_type})

    def notify(self, notification_item):
        if isinstance(notification_item, HookNotificationItem):
            self._notify(notification_item, True)

    def _notify(self, notification_item, recall):
        try:
            self._channel.basic_publish(
                exchange='',
                routing_key=self._topic,
                body=notification_item.to_json().encode(
                    encoding=self._encoding
                )
            )
        except Exception as e:
            if (isinstance(e, ChannelWrongStateError) or
                    isinstance(e, StreamLostError)) and recall:
                self._make_connection_synced()
                self._notify(notification_item, False)
                return
            logger.error("An exception occurred during "
                         "publishing hook notification item: %s",
                         e, exc_info=True)
