# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud <unrud@outlook.com>
# Copyright © 2024-2024 Peter Bieringer <pb@bieringer.de>
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

import ssl
from importlib import import_module, metadata
from typing import Callable, Sequence, Type, TypeVar, Union

from radicale import config
from radicale.log import logger

_T_co = TypeVar("_T_co", covariant=True)

RADICALE_MODULES: Sequence[str] = ("radicale", "vobject", "passlib", "defusedxml")


def load_plugin(internal_types: Sequence[str], module_name: str,
                class_name: str, base_class: Type[_T_co],
                configuration: "config.Configuration") -> _T_co:
    type_: Union[str, Callable] = configuration.get(module_name, "type")
    if callable(type_):
        logger.info("%s type is %r", module_name, type_)
        return type_(configuration)
    if type_ in internal_types:
        module = "radicale.%s.%s" % (module_name, type_)
    else:
        module = type_
    try:
        class_ = getattr(import_module(module), class_name)
    except Exception as e:
        raise RuntimeError("Failed to load %s module %r: %s" %
                           (module_name, module, e)) from e
    logger.info("%s type is %r", module_name, module)
    return class_(configuration)


def package_version(name):
    return metadata.version(name)


def packages_version():
    versions = []
    for pkg in RADICALE_MODULES:
        versions.append("%s=%s" % (pkg, package_version(pkg)))
    return " ".join(versions)


def ssl_context_options_by_protocol(protocol: str, ssl_context_options):
    logger.debug("SSL protocol string: '%s' and current SSL context options: '0x%x'", protocol, ssl_context_options)
    # disable any protocol by default
    logger.debug("SSL context options, disable ALL by default")
    ssl_context_options |= ssl.OP_NO_SSLv2
    ssl_context_options |= ssl.OP_NO_SSLv3
    ssl_context_options |= ssl.OP_NO_TLSv1
    ssl_context_options |= ssl.OP_NO_TLSv1_1
    ssl_context_options |= ssl.OP_NO_TLSv1_2
    ssl_context_options |= ssl.OP_NO_TLSv1_3
    logger.debug("SSL cleared SSL context options: '0x%x'", ssl_context_options)
    for entry in protocol.split():
        entry = entry.strip('+') # remove trailing '+'
        if entry == "ALL":
            logger.debug("SSL context options, enable ALL (some maybe not supported by underlying OpenSSL, SSLv2 not enabled at all)")
            ssl_context_options &= ~ssl.OP_NO_SSLv3
            ssl_context_options &= ~ssl.OP_NO_TLSv1
            ssl_context_options &= ~ssl.OP_NO_TLSv1_1
            ssl_context_options &= ~ssl.OP_NO_TLSv1_2
            ssl_context_options &= ~ssl.OP_NO_TLSv1_3
        elif entry == "SSLv2":
            logger.warning("SSL context options, ignore SSLv2 (totally insecure)")
        elif entry == "SSLv3":
            ssl_context_options &= ~ssl.OP_NO_SSLv3
            logger.debug("SSL context options, enable SSLv3 (maybe not supported by underlying OpenSSL)")
        elif entry == "TLSv1":
            ssl_context_options &= ~ssl.OP_NO_TLSv1
            logger.debug("SSL context options, enable TLSv1 (maybe not supported by underlying OpenSSL)")
        elif entry == "TLSv1.1":
            logger.debug("SSL context options, enable TLSv1.1 (maybe not supported by underlying OpenSSL)")
            ssl_context_options &= ~ssl.OP_NO_TLSv1_1
        elif entry == "TLSv1.2":
            logger.debug("SSL context options, enable TLSv1.2")
            ssl_context_options &= ~ssl.OP_NO_TLSv1_2
        elif entry == "TLSv1.3":
            logger.debug("SSL context options, enable TLSv1.3")
            ssl_context_options &= ~ssl.OP_NO_TLSv1_3
        elif entry == "-ALL":
            logger.debug("SSL context options, disable ALL")
            ssl_context_options |= ssl.OP_NO_SSLv2
            ssl_context_options |= ssl.OP_NO_SSLv3
            ssl_context_options |= ssl.OP_NO_TLSv1
            ssl_context_options |= ssl.OP_NO_TLSv1_1
            ssl_context_options |= ssl.OP_NO_TLSv1_2
            ssl_context_options |= ssl.OP_NO_TLSv1_3
        elif entry == "-SSLv2":
            ssl_context_options |= ssl.OP_NO_SSLv2
            logger.debug("SSL context options, disable SSLv2")
        elif entry == "-SSLv3":
            ssl_context_options |= ssl.OP_NO_SSLv3
            logger.debug("SSL context options, disable SSLv3")
        elif entry == "-TLSv1":
            logger.debug("SSL context options, disable TLSv1")
            ssl_context_options |= ssl.OP_NO_TLSv1
        elif entry == "-TLSv1.1":
            logger.debug("SSL context options, disable TLSv1.1")
            ssl_context_options |= ssl.OP_NO_TLSv1_1
        elif entry == "-TLSv1.2":
            logger.debug("SSL context options, disable TLSv1.2")
            ssl_context_options |= ssl.OP_NO_TLSv1_2
        elif entry == "-TLSv1.3":
            logger.debug("SSL context options, disable TLSv1.3")
            ssl_context_options |= ssl.OP_NO_TLSv1_3
        else:
            raise RuntimeError("SSL protocol config contains unsupported entry '%s'" % (entry))

    logger.debug("SSL resulting context options: '0x%x'", ssl_context_options)
    return ssl_context_options


def ssl_context_minimum_version_by_options(ssl_context_options):
    logger.debug("SSL calculate minimum version by context options: '0x%x'", ssl_context_options)
    ssl_context_minimum_version = ssl.TLSVersion.SSLv3 # default
    if ((ssl_context_options & ssl.OP_NO_SSLv3) and (ssl_context_minimum_version == ssl.TLSVersion.SSLv3)):
        ssl_context_minimum_version = ssl.TLSVersion.TLSv1
    if ((ssl_context_options & ssl.OP_NO_TLSv1) and (ssl_context_minimum_version == ssl.TLSVersion.TLSv1)):
        ssl_context_minimum_version = ssl.TLSVersion.TLSv1_1
    if ((ssl_context_options & ssl.OP_NO_TLSv1_1) and (ssl_context_minimum_version == ssl.TLSVersion.TLSv1_1)):
        ssl_context_minimum_version = ssl.TLSVersion.TLSv1_2
    if ((ssl_context_options & ssl.OP_NO_TLSv1_2) and (ssl_context_minimum_version == ssl.TLSVersion.TLSv1_2)):
        ssl_context_minimum_version = ssl.TLSVersion.TLSv1_3
    if ((ssl_context_options & ssl.OP_NO_TLSv1_3) and (ssl_context_minimum_version == ssl.TLSVersion.TLSv1_3)):
        ssl_context_minimum_version = 0 # all disabled

    logger.debug("SSL context options: '0x%x' results in minimum version: %s", ssl_context_options, ssl_context_minimum_version)
    return ssl_context_minimum_version


def ssl_context_maximum_version_by_options(ssl_context_options):
    logger.debug("SSL calculate maximum version by context options: '0x%x'", ssl_context_options)
    ssl_context_maximum_version = ssl.TLSVersion.TLSv1_3 # default
    if ((ssl_context_options & ssl.OP_NO_TLSv1_3) and (ssl_context_maximum_version == ssl.TLSVersion.TLSv1_3)):
        ssl_context_maximum_version = ssl.TLSVersion.TLSv1_2
    if ((ssl_context_options & ssl.OP_NO_TLSv1_2) and (ssl_context_maximum_version == ssl.TLSVersion.TLSv1_2)):
        ssl_context_maximum_version = ssl.TLSVersion.TLSv1_1
    if ((ssl_context_options & ssl.OP_NO_TLSv1_1) and (ssl_context_maximum_version == ssl.TLSVersion.TLSv1_1)):
        ssl_context_maximum_version = ssl.TLSVersion.TLSv1
    if ((ssl_context_options & ssl.OP_NO_TLSv1) and (ssl_context_maximum_version == ssl.TLSVersion.TLSv1)):
        ssl_context_maximum_version = ssl.TLSVersion.SSLv3
    if ((ssl_context_options & ssl.OP_NO_SSLv3) and (ssl_context_maximum_version == ssl.TLSVersion.SSLv3)):
        ssl_context_maximum_version = 0

    logger.debug("SSL context options: '0x%x' results in maximum version: %s", ssl_context_options, ssl_context_maximum_version)
    return ssl_context_maximum_version


def ssl_get_protocols(context):
    protocols = []
    if not (context.options & ssl.OP_NO_SSLv3):
        if (context.minimum_version < ssl.TLSVersion.TLSv1):
            protocols.append("SSLv3")
    if not (context.options & ssl.OP_NO_TLSv1):
        if (context.minimum_version < ssl.TLSVersion.TLSv1_1) and (context.maximum_version >= ssl.TLSVersion.TLSv1):
            protocols.append("TLSv1")
    if not (context.options & ssl.OP_NO_TLSv1_1):
        if (context.minimum_version < ssl.TLSVersion.TLSv1_2) and (context.maximum_version >= ssl.TLSVersion.TLSv1_1):
            protocols.append("TLSv1.1")
    if not (context.options & ssl.OP_NO_TLSv1_2):
        if (context.minimum_version <= ssl.TLSVersion.TLSv1_2) and (context.maximum_version >= ssl.TLSVersion.TLSv1_2):
            protocols.append("TLSv1.2")
    if not (context.options & ssl.OP_NO_TLSv1_3):
        if (context.minimum_version <= ssl.TLSVersion.TLSv1_3) and (context.maximum_version >= ssl.TLSVersion.TLSv1_3):
            protocols.append("TLSv1.3")
    return protocols
