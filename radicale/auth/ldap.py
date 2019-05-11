# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud<unrud@outlook.com>
# Copyright © 2019 Marco Fleckinger<marco.fleckinger@gmail.com>
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

import re

from radicale import auth


class Auth(auth.BaseAuth):
    def __init__(self, configuration):
        super().__init__(configuration)

        try:
            import ldap3
        except ImportError as e:
            raise RuntimeError(
               "LDAP authentication requires the ldap3 module") from e

        self.ldap3 = ldap3
        self.server_uri = configuration.get("auth", "ldap_server_uri")
        self.bind_dn_pattern = configuration.get("auth", "ldap_bind_dn")

    def login(self, login, password):
        """
            Validate credentials.
            Simply try to sign in into ldap server with given
            credentials using dn from configuration
        """

        def substitute(match_object):
            """
                substitutes:
                 * %d by the domain part
                 * %n by the local part
                 * %u by the whole given user name
            """
            patterns = {
                'd': '.+?@(.+)',
                'n': '(.+?)@.+',
                'u': '(.+)'
            }
            key = match_object.group(1)
            if key not in patterns:
                raise RuntimeError("'%s' is an unknown variable" % key)
            pattern = patterns[key]
            m = re.match(pattern, login)
            if m is None:
                return ''
            return m.group(1)

        # First get the distinguished name to connect with to the server
        bind_dn = re.sub('%([a-z])', substitute, self.bind_dn_pattern)
        # Try to connect to the LDAP server by using
        #   * the distinguished name
        #   * the given password
        try:
            server = self.ldap3.Server(self.server_uri)
            conn = self.ldap3.Connection(server, bind_dn, password=password)
            if conn.bind():
                return login
        except self.ldap3.core.exceptions.LDAPSocketOpenError:
            raise RuntimeError("unable to reach ldap server")
        except Exception:
            pass
        return ""
