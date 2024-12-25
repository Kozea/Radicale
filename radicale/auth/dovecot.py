# This file is part of Radicale Server - Calendar Server
# Copyright © 2014 Giel van Schijndel
# Copyright © 2019 (GalaxyMaster)
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

import base64
import itertools
import os
import socket
from contextlib import closing

from radicale import auth
from radicale.log import logger


class Auth(auth.BaseAuth):
    def __init__(self, configuration):
        super().__init__(configuration)
        self.socket = configuration.get("auth", "dovecot_socket")
        self.timeout = 5
        self.request_id_gen = itertools.count(1)

    def _login(self, login, password):
        """Validate credentials.

        Check if the ``login``/``password`` pair is valid according to Dovecot.

        This implementation communicates with a Dovecot server through the
        Dovecot Authentication Protocol v1.1.

        https://dovecot.org/doc/auth-protocol.txt

        """

        logger.info("Authentication request (dovecot): '{}'".format(login))
        if not login or not password:
            return ""

        with closing(socket.socket(
                socket.AF_UNIX,
                socket.SOCK_STREAM)
        ) as sock:
            try:
                sock.settimeout(self.timeout)
                sock.connect(self.socket)

                buf = bytes()
                supported_mechs = []
                done = False
                seen_part = [0, 0, 0]
                # Upon the initial connection we only care about the
                # handshake, which is usually just around 100 bytes long,
                # e.g.
                #
                # VERSION	1	2
                # MECH	PLAIN	plaintext
                # SPID	22901
                # CUID	1
                # COOKIE	2dbe4116a30fb4b8a8719f4448420af7
                # DONE
                #
                # Hence, we try to read just once with a buffer big
                # enough to hold all of it.
                buf = sock.recv(1024)
                while b'\n' in buf and not done:
                    line, buf = buf.split(b'\n', 1)
                    parts = line.split(b'\t')
                    first, parts = parts[0], parts[1:]

                    if first == b'VERSION':
                        if seen_part[0]:
                            logger.warning(
                                    "Server presented multiple VERSION "
                                    "tokens, ignoring"
                            )
                            continue
                        version = parts
                        logger.debug("Dovecot server version: '{}'".format(
                            (b'.'.join(version)).decode()
                        ))
                        if int(version[0]) != 1:
                            logger.fatal(
                                    "Only Dovecot 1.x versions are supported!"
                            )
                            return ""
                        seen_part[0] += 1
                    elif first == b'MECH':
                        supported_mechs.append(parts[0])
                        seen_part[1] += 1
                    elif first == b'DONE':
                        seen_part[2] += 1
                        if not (seen_part[0] and seen_part[1]):
                            logger.fatal(
                                    "An unexpected end of the server "
                                    "handshake received!"
                            )
                            return ""
                        done = True

                if not done:
                    logger.fatal("Encountered a broken server handshake!")
                    return ""

                logger.debug(
                        "Supported auth methods: '{}'"
                        .format((b"', '".join(supported_mechs)).decode())
                )
                if b'PLAIN' not in supported_mechs:
                    logger.info(
                            "Authentication method 'PLAIN' is not supported, "
                            "but is required!"
                    )
                    return ""

                # Handshake
                logger.debug("Sending auth handshake")
                sock.send(b'VERSION\t1\t1\n')
                sock.send(b'CPID\t%u\n' % os.getpid())

                request_id = next(self.request_id_gen)
                logger.debug(
                        "Authenticating with request id: '{}'"
                        .format(request_id)
                )
                sock.send(
                        b'AUTH\t%u\tPLAIN\tservice=radicale\tresp=%b\n' %
                        (
                            request_id, base64.b64encode(
                                    b'\0%b\0%b' %
                                    (login.encode(), password.encode())
                            )
                        )
                )

                logger.debug("Processing auth response")
                buf = sock.recv(1024)
                line = buf.split(b'\n', 1)[0]
                parts = line.split(b'\t')[:2]
                resp, reply_id, params = (
                        parts[0], int(parts[1]),
                        dict(part.split('=', 1) for part in parts[2:])
                )

                logger.debug(
                        "Auth response: result='{}', id='{}', parameters={}"
                        .format(resp.decode(), reply_id, params)
                )
                if request_id != reply_id:
                    logger.fatal(
                            "Unexpected reply ID {} received (expected {})"
                            .format(
                                    reply_id, request_id
                            )
                    )
                    return ""

                if resp == b'OK':
                    return login

            except socket.error as e:
                logger.fatal(
                        "Failed to communicate with Dovecot socket %r: %s" %
                        (self.socket, e)
                )

        return ""
