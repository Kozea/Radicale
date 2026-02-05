# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud <unrud@outlook.com>
# Copyright © 2024-2026 Peter Bieringer <pb@bieringer.de>
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

import datetime
import os
import ssl
import sys
import textwrap
from hashlib import sha256
from importlib import import_module, metadata
from string import ascii_letters, digits, punctuation
from typing import Callable, Sequence, Tuple, Type, TypeVar, Union

from packaging.version import Version

from radicale import config
from radicale.log import logger

if sys.platform != "win32":
    import grp
    import pwd

_T_co = TypeVar("_T_co", covariant=True)

RADICALE_MODULES: Sequence[str] = ("radicale", "vobject", "passlib", "defusedxml",
                                   "bcrypt",
                                   "argon2-cffi",
                                   "pika",
                                   "ldap",
                                   "ldap3",
                                   "pam")


# IPv4 (host, port) and IPv6 (host, port, flowinfo, scopeid)
ADDRESS_TYPE = Union[Tuple[Union[str, bytes, bytearray], int],
                     Tuple[str, int, int, int]]


# Max/Min YEAR in datetime in unixtime
DATETIME_MAX_UNIXTIME: int = (datetime.MAXYEAR - 1970) * 365 * 24 * 60 * 60
DATETIME_MIN_UNIXTIME: int = (datetime.MINYEAR - 1970) * 365 * 24 * 60 * 60


# Number units
UNIT_g: int = (1000 * 1000 * 1000)
UNIT_m: int = (1000 * 1000)
UNIT_k: int = (1000)
UNIT_G: int = (1024 * 1024 * 1024)
UNIT_M: int = (1024 * 1024)
UNIT_K: int = (1024)


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
    if name == "passlib":
        # passlib(libpass) requires special handling as module name is unchanged, but metadata has new name
        import passlib
        return passlib.__version__
    return metadata.version(name)


def vobject_supports_vcard4() -> bool:
    """Check if vobject supports vCard 4.0 (requires version >= 1.0.0)."""
    try:
        version = package_version("vobject")
        parts = version.split(".")
        major = int(parts[0])
        return major >= 1
    except Exception:
        return False


def passlib_libpass_supports_bcrypt() -> Tuple[bool, str]:
    """Check if passlib(libpass) version supports bcrypt version."""
    info = ""
    try:
        version_bcrypt = package_version("bcrypt")
        version_bcrypt_check = "5.0.0"
        version_passlib = package_version("passlib")
        version_passlib_check = "1.9.3"
        if Version(version_bcrypt) >= Version(version_bcrypt_check):
            # bcrypt >= 5.0.0 has issues with passlib(libpass) < 1.9.3
            if Version(version_passlib) < Version(version_passlib_check):
                info = "bcrypt module version %r >= %r and passlib(libpass) module version %r < %r found => incompatible, downgrade bcrypt or upgrade passlib(libpass)" % (version_bcrypt, version_bcrypt_check, version_passlib, version_passlib_check)
                return (False, info)
            else:
                info = "bcrypt module version %r >= %r and passlib(libpass) module version %r >= %r found => ok" % (version_bcrypt, version_bcrypt_check, version_passlib, version_passlib_check)
                return (True, info)
        else:
            info = "bcrypt module version %r < %r and passlib(libpass) module version %r found => ok" % (version_bcrypt, version_bcrypt_check, version_passlib)
            return (True, info)
    except Exception:
        info = "bcrypt module version or passlib(libpass) module version %r not found => problem"
        return (False, info)


def packages_version():
    versions = []
    versions.append("python=%s.%s.%s" % (sys.version_info[0], sys.version_info[1], sys.version_info[2]))
    for pkg in RADICALE_MODULES:
        try:
            versions.append("%s=%s" % (pkg, package_version(pkg)))
        except Exception:
            try:
                versions.append("%s=%s" % (pkg, package_version("python-" + pkg)))
            except Exception:
                versions.append("%s=%s" % (pkg, "n/a"))
    return " ".join(versions)


def format_address(address: ADDRESS_TYPE) -> str:
    host, port, *_ = address
    if not isinstance(host, str):
        raise NotImplementedError("Unsupported address format: %r" %
                                  (address,))
    if host.find(":") == -1:
        return "%s:%d" % (host, port)
    else:
        return "[%s]:%d" % (host, port)


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
        entry = entry.strip('+')  # remove trailing '+'
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
    ssl_context_minimum_version = ssl.TLSVersion.SSLv3  # default
    if ((ssl_context_options & ssl.OP_NO_SSLv3) and (ssl_context_minimum_version == ssl.TLSVersion.SSLv3)):
        ssl_context_minimum_version = ssl.TLSVersion.TLSv1
    if ((ssl_context_options & ssl.OP_NO_TLSv1) and (ssl_context_minimum_version == ssl.TLSVersion.TLSv1)):
        ssl_context_minimum_version = ssl.TLSVersion.TLSv1_1
    if ((ssl_context_options & ssl.OP_NO_TLSv1_1) and (ssl_context_minimum_version == ssl.TLSVersion.TLSv1_1)):
        ssl_context_minimum_version = ssl.TLSVersion.TLSv1_2
    if ((ssl_context_options & ssl.OP_NO_TLSv1_2) and (ssl_context_minimum_version == ssl.TLSVersion.TLSv1_2)):
        ssl_context_minimum_version = ssl.TLSVersion.TLSv1_3
    if ((ssl_context_options & ssl.OP_NO_TLSv1_3) and (ssl_context_minimum_version == ssl.TLSVersion.TLSv1_3)):
        ssl_context_minimum_version = 0  # all disabled

    logger.debug("SSL context options: '0x%x' results in minimum version: %s", ssl_context_options, ssl_context_minimum_version)
    return ssl_context_minimum_version


def ssl_context_maximum_version_by_options(ssl_context_options):
    logger.debug("SSL calculate maximum version by context options: '0x%x'", ssl_context_options)
    ssl_context_maximum_version = ssl.TLSVersion.TLSv1_3  # default
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


def unknown_if_empty(value):
    if value == "":
        return "UNKNOWN"
    else:
        return value


def user_groups_as_string():
    if sys.platform != "win32":
        euid = os.geteuid()
        try:
            username = pwd.getpwuid(euid)[0]
            user = "%s(%d)" % (unknown_if_empty(username), euid)
        except Exception:
            # name of user not found
            user = "UNKNOWN(%d)" % euid

        egid = os.getegid()
        groups = []
        try:
            gids = os.getgrouplist(username, egid)
            for gid in gids:
                try:
                    gi = grp.getgrgid(gid)
                    groups.append("%s(%d)" % (unknown_if_empty(gi.gr_name), gid))
                except Exception:
                    groups.append("UNKNOWN(%d)" % gid)
        except Exception:
            try:
                groups.append("%s(%d)" % (grp.getgrnam(egid)[0], egid))
            except Exception:
                # workaround to get groupid by name
                groups_all = grp.getgrall()
                found = False
                for entry in groups_all:
                    if entry[2] == egid:
                        groups.append("%s(%d)" % (unknown_if_empty(entry[0]), egid))
                        found = True
                        break
                if not found:
                    groups.append("UNKNOWN(%d)" % egid)

        s = "user=%s groups=%s" % (user, ','.join(groups))
    else:
        username = os.getlogin()
        s = "user=%s" % (username)
    return s


def format_ut(unixtime: int) -> str:
    if sys.platform == "win32":
        # TODO check how to support this better
        return str(unixtime)
    if unixtime <= DATETIME_MIN_UNIXTIME:
        r = str(unixtime) + "(<=MIN:" + str(DATETIME_MIN_UNIXTIME) + ")"
    elif unixtime >= DATETIME_MAX_UNIXTIME:
        r = str(unixtime) + "(>=MAX:" + str(DATETIME_MAX_UNIXTIME) + ")"
    else:
        if sys.version_info < (3, 11):
            dt = datetime.datetime.utcfromtimestamp(unixtime)
        else:
            dt = datetime.datetime.fromtimestamp(unixtime, datetime.UTC)
        r = str(unixtime) + "(" + dt.strftime('%Y-%m-%dT%H:%M:%SZ') + ")"
    return r


def format_unit(value: float, binary: bool = False) -> str:
    if binary:
        if value > UNIT_G:
            value = value / UNIT_G
            unit = "G"
        elif value > UNIT_M:
            value = value / UNIT_M
            unit = "M"
        elif value > UNIT_K:
            value = value / UNIT_K
            unit = "K"
        else:
            unit = ""
    else:
        if value > UNIT_g:
            value = value / UNIT_g
            unit = "g"
        elif value > UNIT_m:
            value = value / UNIT_m
            unit = "m"
        elif value > UNIT_k:
            value = value / UNIT_k
            unit = "k"
        else:
            unit = ""
    return ("%.1f %s" % (value, unit))


def limit_str(content: str, limit: int) -> str:
    length = len(content)
    if limit > 0 and length >= limit:
        return content[:limit] + ("...(shortened because original length %d > limit %d)" % (length, limit))
    else:
        return content


def textwrap_str(content: str, limit: int = 2000) -> str:
    # TODO: add support for config option and prefix
    return textwrap.indent(limit_str(content, limit), " ", lambda line: True)


def dataToHex(data, count):
    result = ''
    for item in range(count):
        if ((item > 0) and ((item % 8) == 0)):
            result += ' '
        if (item < len(data)):
            result += '%02x' % data[item] + ' '
        else:
            result += '   '
    return result


def dataToAscii(data, count):
    result = ''
    for item in range(count):
        if (item < len(data)):
            char = chr(data[item])
            if char in ascii_letters or \
               char in digits or \
               char in punctuation or \
               char == ' ':
                result += char
            else:
                result += '.'
    return result


def dataToSpecial(data, count):
    result = ''
    for item in range(count):
        if (item < len(data)):
            char = chr(data[item])
            if char == '\r':
                result += 'C'
            elif char == '\n':
                result += 'L'
            elif (ord(char) & 0xf8) == 0xf0:  # assuming UTF-8
                result += '4'
            elif (ord(char) & 0xf0) == 0xf0:  # assuming UTF-8
                result += '3'
            elif (ord(char) & 0xe0) == 0xe0:  # assuming UTF-8
                result += '2'
            else:
                result += '.'
    return result


def hexdump_str(content: str, limit: int = 2000) -> str:
    result = "Hexdump of string: index  <bytes> | <ASCII> | <CTRL: C=CR L=LF 2/3/4=UTF-8-length> |\n"
    index = 0
    size = 16
    bytestring = content.encode("utf-8")  # assuming UTF-8
    length = len(bytestring)

    while (index < length) and (index < limit):
        data = bytestring[index:index+size]
        hex = dataToHex(data, size)
        ascii = dataToAscii(data, size)
        special = dataToSpecial(data, size)
        result += '%08x  ' % index
        result += hex
        result += '|'
        result += '%-16s' % ascii
        result += '|'
        result += '%-16s' % special
        result += '|'
        result += '\n'
        index += size

    return result


def hexdump_line(line: str, limit: int = 200) -> str:
    result = ""
    length_str = len(line)
    bytestring = line.encode("utf-8")  # assuming UTF-8
    length = len(bytestring)
    size = length
    if (size > limit):
        size = limit

    hex = dataToHex(bytestring, size)
    ascii = dataToAscii(bytestring, size)
    special = dataToSpecial(bytestring, size)
    result += '%3d/%3d' % (length_str, length)
    result += ': '
    result += hex
    result += '|'
    result += ascii
    result += '|'
    result += special
    result += '|'
    result += '\n'

    return result


def hexdump_lines(lines: str, limit: int = 200) -> str:
    result = "Hexdump of lines: nr  chars/bytes: <bytes> | <ASCII> | <CTRL: C=CR L=LF 2/3/4=UTF-8-length> |\n"
    counter = 0
    for line in lines.splitlines(True):
        result += '% 4d  ' % counter
        result += hexdump_line(line)
        counter += 1

    return result


def sha256_str(content: str) -> str:
    _hash = sha256()
    _hash.update(content.encode("utf-8"))  # assuming UTF-8
    return _hash.hexdigest()


def sha256_bytes(content: bytes) -> str:
    _hash = sha256()
    _hash.update(content)
    return _hash.hexdigest()
