# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud <unrud@outlook.com>
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
Authentication management.

Default is htpasswd authentication.

Apache's htpasswd command (httpd.apache.org/docs/programs/htpasswd.html)
manages a file for storing user credentials. It can encrypt passwords using
different methods, e.g. BCRYPT, MD5-APR1 (a version of MD5 modified for
Apache), SHA1, or by using the system's CRYPT routine. The CRYPT and SHA1
encryption methods implemented by htpasswd are considered as insecure. MD5-APR1
provides medium security as of 2015. Only BCRYPT can be considered secure by
current standards.

MD5-APR1-encrypted credentials can be written by all versions of htpasswd (it
is the default, in fact), whereas BCRYPT requires htpasswd 2.4.x or newer.

The `is_authenticated(user, password)` function provided by this module
verifies the user-given credentials by parsing the htpasswd credential file
pointed to by the ``htpasswd_filename`` configuration value while assuming
the password encryption method specified via the ``htpasswd_encryption``
configuration value.

The following htpasswd password encrpytion methods are supported by Radicale
out-of-the-box:

    - plain-text (created by htpasswd -p...) -- INSECURE
    - CRYPT      (created by htpasswd -d...) -- INSECURE
    - SHA1       (created by htpasswd -s...) -- INSECURE

When passlib (https://pypi.python.org/pypi/passlib) is importable, the
following significantly more secure schemes are parsable by Radicale:

    - MD5-APR1   (htpasswd -m...) -- htpasswd's default method
    - BCRYPT     (htpasswd -B...) -- Requires htpasswd 2.4.x

"""

from importlib import import_module

from radicale.log import logger

INTERNAL_TYPES = ("none", "remote_user", "http_x_remote_user", "htpasswd")


def load(configuration):
    """Load the authentication manager chosen in configuration."""
    auth_type = configuration.get("auth", "type")
    if auth_type in INTERNAL_TYPES:
        module = "radicale.auth.%s" % auth_type
    else:
        module = auth_type
    try:
        class_ = import_module(module).Auth
    except Exception as e:
        raise RuntimeError("Failed to load authentication module %r: %s" %
                           (module, e)) from e
    logger.info("Authentication type is %r", auth_type)
    return class_(configuration)


class BaseAuth:
    def __init__(self, configuration):
        self.configuration = configuration

    def get_external_login(self, environ):
        """Optionally provide the login and password externally.

        ``environ`` a dict with the WSGI environment

        If ``()`` is returned, Radicale handles HTTP authentication.
        Otherwise, returns a tuple ``(login, password)``. For anonymous users
        ``login`` must be ``""``.

        """
        return ()

    def login(self, login, password):
        """Check credentials and map login to internal user

        ``login`` the login name

        ``password`` the password

        Returns the user name or ``""`` for invalid credentials.

        """

        raise NotImplementedError
