# -*- coding: utf-8 -*-
#
# This file is part of Radicale Server - Calendar Server
# Copyright © 2012 Guillaume Ayoub
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
File-based rights.

The owner is implied to have all rights on their collections.

Rights are read from a file whose name is specified in the config (section
"right", key "file").

Example:

# This means user1 may read, user2 may write, user3 has full access
[/user0/calendar]
user1: r
user2: w
user3: rw

# user0 can read /user1/cal
[/user1/cal]
user0: r

# If a collection /a/b is shared and other users than the owner are supposed to
# find the collection in a propfind request, an additional line for /a has to
# be in the defintions. E.g.:

[/user0]
user1: r

"""

from radicale import config, log
from radicale.rights import owner_only
from radicale.models.redmine import Users
import os
# Manage Python2/3 different modules
# pylint: disable=F0401
try:
    from configparser import RawConfigParser as ConfigParser
except ImportError:
    from ConfigParser import RawConfigParser as ConfigParser
# pylint: enable=F0401


FILENAME = config.get("rights", "file")
STORAGE_PATH = config.get("storage", "filesystem_folder")

if FILENAME:
    log.LOGGER.debug("Reading rights from file %s" % FILENAME)
    RIGHTS = ConfigParser()
    RIGHTS.read(FILENAME)
else:
    log.LOGGER.error("No file name configured for rights type 'from_file'")
    RIGHTS = None

def create_group_dir(group):
    group_dir = os.path.join(STORAGE_PATH, 'groups', group)
    if not os.path.exists(group_dir):
        os.makedirs(group_dir)

def create_link_to_group(user, group):
    group_dir = os.path.join(STORAGE_PATH, 'groups', group)
    link_group_dir = os.path.join(STORAGE_PATH, user, group)
    if not os.path.exists(link_group_dir):
        os.symlink(group_dir, link_group_dir)
    #~ Nestor link_path = os.path.join(STORAGE_PATH, user, collection)

def group_collection(user, collection):
    path = collection.path.split('/')
    is_group_collection = False
    allowed = False
    if len(path) > 2:
        is_group_collection = True
        group = Users().get(path[1], 'lastname')
        user = Users().get(user, 'login')
        create_group_dir(group.name)
        create_link_to_group(user.name, group.name)
        for pos in user.groups():
            if group.name == pos.name:
                return is_group_collection, True
    return is_group_collection, allowed
        
def read_authorized(user, collection):
    """Check if the user is allowed to read the collection."""
    is_group_collection, allowed = group_collection(user, collection)
    if is_group_collection == True:
        return allowed
    return (
            owner_only.read_authorized(user, collection) or
            "r" in RIGHTS.get(collection.url.rstrip("/") or "/", user))

def write_authorized(user, collection):
    """Check if the user is allowed to write the collection."""
    is_group_collection, allowed = group_collection(user, collection)
    if is_group_collection == True:
        return allowed
    return (
        owner_only.write_authorized(user, collection) or
        "w" in RIGHTS.get(collection.url.rstrip("/") or "/", user))
