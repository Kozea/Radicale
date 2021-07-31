# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2019 Unrud <unrud@outlook.com>
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
Entry point for external WSGI servers (like uWSGI or Gunicorn).

Configuration files can be specified in the environment variable
``RADICALE_CONFIG``.

"""

import os
import threading
from typing import Iterable, Optional, cast

import pkg_resources

from radicale import config, log, types
from radicale.app import Application
from radicale.log import logger

VERSION: str = pkg_resources.get_distribution("radicale").version

_application_instance: Optional[Application] = None
_application_config_path: Optional[str] = None
_application_lock = threading.Lock()


def _get_application_instance(config_path: str, wsgi_errors: types.ErrorStream
                              ) -> Application:
    global _application_instance, _application_config_path
    with _application_lock:
        if _application_instance is None:
            log.setup()
            with log.register_stream(wsgi_errors):
                _application_config_path = config_path
                configuration = config.load(config.parse_compound_paths(
                    config.DEFAULT_CONFIG_PATH,
                    config_path))
                log.set_level(cast(str, configuration.get("logging", "level")))
                # Log configuration after logger is configured
                for source, miss in configuration.sources():
                    logger.info("%s %s", "Skipped missing" if miss
                                else "Loaded", source)
                _application_instance = Application(configuration)
    if _application_config_path != config_path:
        raise ValueError("RADICALE_CONFIG must not change: %r != %r" %
                         (config_path, _application_config_path))
    return _application_instance


def application(environ: types.WSGIEnviron,
                start_response: types.WSGIStartResponse) -> Iterable[bytes]:
    """Entry point for external WSGI servers."""
    config_path = environ.get("RADICALE_CONFIG",
                              os.environ.get("RADICALE_CONFIG"))
    app = _get_application_instance(config_path, environ["wsgi.errors"])
    return app(environ, start_response)
