# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2020-2024 Tuna Celik <tuna@jakpark.com>
# Copyright © 2025-2025 Peter Bieringer <pb@bieringer.de>
#
# This library is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Radicale.  If not, see <http://www.gnu.org/licenses/>.

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
        self._dryrun = configuration.get("hook", "dryrun")
        logger.info("Hook 'rabbitmq': endpoint=%r topic=%r queue_type=%r dryrun=%s", self._endpoint, self._topic, self._queue_type, self._dryrun)

        self._make_connection_synced()
        self._make_declare_queue_synced()

    def _make_connection_synced(self):
        parameters = pika.URLParameters(self._endpoint)
        if self._dryrun is True:
            logger.warning("Hook 'rabbitmq': DRY-RUN _make_connection_synced / parameters=%r", parameters)
            return
        logger.debug("Hook 'rabbitmq': _make_connection_synced / parameters=%r", parameters)
        connection = pika.BlockingConnection(parameters)
        self._channel = connection.channel()

    def _make_declare_queue_synced(self):
        if self._dryrun is True:
            logger.warning("Hook 'rabbitmq': DRY-RUN _make_declare_queue_synced")
            return
        logger.debug("Hook 'rabbitmq': _make_declare_queue_synced")
        self._channel.queue_declare(queue=self._topic, durable=True, arguments={"x-queue-type": self._queue_type})

    def notify(self, notification_item):
        if isinstance(notification_item, HookNotificationItem):
            self._notify(notification_item, True)

    def _notify(self, notification_item, recall):
        if self._dryrun is True:
            logger.warning("Hook 'rabbitmq': DRY-RUN _notify / notification_item: %r", vars(notification_item))
            return
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
