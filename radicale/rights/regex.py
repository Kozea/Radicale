# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2013 Guillaume Ayoub
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
Regex-based rights.

You can define an secondary rights management method. If not, it will use
"owner_only", which implies the owners have all rights on their collections.
Secondary rights management method is specified in the config (section
"right", key "regex_secondary").

Regexes are read from a file whose name is specified in the config (section
"right", key "regex_file").

Test string for regex is "user|collection" per default, because "|" is
not allowed in an URL. You may set this string per rule, using Python's
ConfigParser interpolation: %(user)s and %(collection)s
In fact you may also set user/collection to a fixed value per rule. But you 
should consider using a secondary rights management method (e.g. "from_file").


Section names are only used for naming the rule.
Leading or Ending "/"s are trimmed from collection names.

Example:

# This means all users starting with "admin" may read any collection
[admin]
regex: ^admin.*\|.+?$
permission: r

# This means all users may read and write any collection starting with public.
# We do so by just not testing against the user string.
[public]
glue: %(collection)s
regex: ^public(/.+)?$
permission: rw

# A little more complex:
# Give read access to users from a domain for all collections of all the users:
[domain-wide-access]
regex:  ^.+@(.+)\|.+@\1(/.+)?$
permission: r


"""

import os.path
import re

from radicale import config, log, rights
# Manage Python2/3 different modules
# pylint: disable=F0401
try:
    from configparser import (
        ConfigParser as ConfigParser, NoSectionError, NoOptionError)
except ImportError:
    from ConfigParser import (
        ConfigParser as ConfigParser, NoSectionError, NoOptionError)
# pylint: enable=F0401


FILENAME = (
    os.path.expanduser(config.get("rights", "regex_file")) or
    log.LOGGER.error("No file name configured for rights type 'regex'"))
    
    
def _read_regex(user, collection):
    """Load regex from file."""
    regex = ConfigParser({'user': user, 'collection': collection})
    if not regex.read(FILENAME):
        log.LOGGER.error(
            "File '%s' not found for rights management type 'regex'" % FILENAME)
    return regex
    
def _read_from_sections(user, collection, perm):
    """Get regex sections."""    
    regex = _read_regex(user, collection)
    try:  
        for section in regex.sections():
            if _matches_section(user, collection, section):
                if perm in regex.get(section, "permission"):
                    return True
    except (NoSectionError, NoOptionError):
        return False
    return False
    
def _matches_section(user, collection, section):
    """Regex section against user and collection"""
    log.LOGGER.debug("Reading regex from file %s" % FILENAME)
    regex = _read_regex(user, collection)
    log.LOGGER.debug("Match against section '%s'" % section)

    try:
        test = regex.get(section, 'glue')
    except (NoOptionError):
        test = user+'|'+collection;
    
    try: 
        match = re.match(regex.get(section, 'regex'), test)
        if match:
            return True;
        log.LOGGER.debug("Test-String '%s' does not match against '%s' from section '%s'" % \
            (test, regex.get(section, 'regex'), section))
    except (NoSectionError, NoOptionError):
        return False
    return False
    
    

def _get_secondary():
    """Get secondary rights management method"""
    try:  
        secondary = config.get("rights", "regex_secondary")
        if not secondary or secondary == None:
            secondary = 'owner_only'
        
        root_module = __import__(
            "rights.%s" % secondary, globals=globals(), level=2)
        module = getattr(root_module, secondary)
        return module
    except (ImportError, NoSectionError, NoOptionError):
        return None
    

def read_authorized(user, collection):
    """Check if the user is allowed to read the collection."""
    if user is None:
        return False
    elif _get_secondary() != None and _get_secondary().read_authorized(user, collection):
        return True
    else:
        return _read_from_sections(
            user, collection.url.rstrip("/") or "/", "r")


def write_authorized(user, collection):
    """Check if the user is allowed to write the collection."""
    if user is None:
        return False
    elif _get_secondary() != None and _get_secondary().write_authorized(user, collection):
        return True
    else:
        return _read_from_sections(
            user, collection.url.rstrip("/") or "/", "w")
