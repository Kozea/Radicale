# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2014 Giel van Schijndel
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

"""
Dovecot Authentication Protocol v1.1

"""

import base64
import itertools
import os
import sys
import socket

from contextlib import closing
from .. import config, log

DOVECOT_SOCKET = config.get("auth", "dovecot_socket")

request_id_gen = itertools.count(1)

def is_authenticated(user, password):
    """Check if ``user``/``password`` couple is valid according to Dovecot.

    This implementation communicates with a Dovecot server through the
    Dovecot Authentication Protocol v1.1.

    http://wiki2.dovecot.org/Design/AuthProtocol
    """

    if not user or not password:
        return False

    with closing(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)) as sock:
        try:
            sock.settimeout(5)

            sock.connect(DOVECOT_SOCKET)

            # Handshake
            sock.send("VERSION\t1\t1\n")
            sock.send("CPID\t{pid}\n".format(pid=os.getpid()))

            buf = bytes()
            supported_mechs = []
            done = False
            while not done:
                buf += sock.recv(8192)
                while bytes('\n') in buf and not done:
                    line, buf = buf.split('\n', 1)
                    parts = line.split('\t')
                    first, parts = parts[0], parts[1:]

                    if first == 'VERSION':
                        version = parts
                        if int(version[0]) != 1:
                            log.LOGGER.error("Dovecot server version is not 1.x. it is %s", '.'.join(version))
                            return False
                    elif first == "MECH":
                        supported_mechs.append(parts[0])
                    elif first == "DONE":
                        done = True

            if "PLAIN" not in supported_mechs:
                log.LOGGER.error("Dovecot doesn't appear to support PLAIN authentication, we need it. Only %s are supported", ', '.join(supported_mechs))
                return False

            request_id = next(request_id_gen)
            sock.send("AUTH\t{request_id}\tPLAIN\tservice={arg0}\t{params}\n".format(
                        request_id=request_id,
                        arg0=sys.argv[0],
                        params='resp={}'.format(base64.b64encode("\0{}\0{}".format(user, password))),
                    ))

            buf = sock.recv(8192)
            line = buf.split('\n', 1)[0]
            parts = line.split('\t')[:2]
            resp, reply_id, params = parts[0], int(parts[1]), dict(part.split('=', 1) for part in parts[2:])

            if request_id != reply_id:
                log.LOGGER.error("Unexpected reply ID %d (request was %d)", reply_id, request_id)
                return False

            return resp == 'OK'
        except socket.error as e:
            log.LOGGER.exception("Unable to communicate with Dovecot auth socket: %s", e)
            return False
