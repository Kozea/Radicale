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

Rights are read from a file whose name is specified in the config 
(section "right", key "file").

The file's format is per line:

collectionpath ":" principal " " rights {", " principal " " rights}*

collectionpath is the path part of the collection's url

principal is a user name (no whitespace allowed)
rights is a string w/o whitespace that contains "r" for reading rights, 
"w" for writing rights and a combination of these for all rights.

Empty lines are ignored. Lines starting with "#" (hash sign) are comments.

Example:

# This means user1 may read, user2 may write, user3 has full access
/user0/calendar : user1 r, user2 w, user3 rw
# user0 can read /user1/cal
/user1/cal : user0 r 

If a collection /a/b is shared and other users than the owner are 
supposed to find the collection in a propfind request, an additional
line for /a has to be in the defintions. E.g.:

/user0/cal: user

"""

from radicale import config, log
from radicale.rights import owner_only


READ_AUTHORIZED = None
WRITE_AUTHORIZED = None


class ParsingError(BaseException):
    """Raised if the file cannot be parsed"""


def read_authorized(user, collection):
    """Check if the user is allowed to read the collection."""
    if owner_only.read_authorized(user, collection):
        return True
    
    curl = _normalize_trail_slash(collection.url)

    return _dict_knows(READ_AUTHORIZED, curl, user)



def write_authorized(user, collection):
    """Check if the user is allowed to write the collection."""
    if owner_only.read_authorized(user, collection):
        return True

    curl = _normalize_trail_slash(collection.url)

    return _dict_knows(WRITE_AUTHORIZED, curl, user)



def _dict_knows(adict, url, user):
    return adict.has_key(url) and adict.get(url).count(user) != 0



def _load():
    read = {}
    write = {}
    file_name = config.get("rights", "file")
    if file_name == "None":
        log.LOGGER.error("No file name configured for rights type 'from_file'")
        return
    
    log.LOGGER.debug("Reading rights from file %s" % file_name)

    lines = open(file_name, "r").readlines()
    
    for line in lines:
        _process(line, read, write)

    global READ_AUTHORIZED, WRITE_AUTHORIZED
    READ_AUTHORIZED = read
    WRITE_AUTHORIZED = write



def _process(line, read, write):
    line = line.strip()   
    if line == "":
        """Empty line"""
        return
    
    if line.startswith("#"):
        """Comment"""
        return
        
    collection, sep, rights_part = line.partition(":")
    
    rights_part = rights_part.strip()

    if rights_part == "":
        return

    collection = collection.strip()
    
    if collection == "":
        raise ParsingError
    
    collection = _normalize_trail_slash(collection)
    
    rights = rights_part.split(",")
    for right in rights:
        user, sep, right_defs = right.strip().partition(" ")
        
        if user == "" or right_defs == "":
            raise ParsingError
        
        user = user.strip()
        right_defs = right_defs.strip()
        
        for right_def in list(right_defs):
            
            if right_def == 'r':
                _append(read, collection, user)
            elif right_def == 'w':
                _append(write, collection, user)
            else:
                raise ParsingError


        
def _append(rdict, key, value):
    if rdict.has_key(key):
        rlist = rdict[key]
        rlist.append(value)
    else:
        rlist = [value]
        rdict[key] = rlist
        
        

def _normalize_trail_slash(s):
    """Removes a maybe existing trailing slash"""
    if s != "/" and s.endswith("/"):
        s, sep, empty = s.rpartition("/")
    return s


_load()
