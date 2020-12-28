# This file is part of Radicale Server - Calendar Server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2017 Guillaume Ayoub
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
The storage module that stores calendars and address books.

Take a look at the class ``BaseCollection`` if you want to implement your own.

"""

import contextlib
import json
from hashlib import sha256

import pkg_resources
import vobject

from radicale import utils
from radicale.item import filter as radicale_filter

INTERNAL_TYPES = ("multifilesystem",)

CACHE_DEPS = ("radicale", "vobject", "python-dateutil",)
CACHE_VERSION = (";".join(pkg_resources.get_distribution(pkg).version
                          for pkg in CACHE_DEPS) + ";").encode()


def load(configuration):
    """Load the storage module chosen in configuration."""
    return utils.load_plugin(
        INTERNAL_TYPES, "storage", "Storage", configuration)


class ComponentExistsError(ValueError):
    def __init__(self, path):
        message = "Component already exists: %r" % path
        super().__init__(message)


class ComponentNotFoundError(ValueError):
    def __init__(self, path):
        message = "Component doesn't exist: %r" % path
        super().__init__(message)


class BaseCollection:

    @property
    def path(self):
        """The sanitized path of the collection without leading or
        trailing ``/``."""
        raise NotImplementedError

    @property
    def owner(self):
        """The owner of the collection."""
        return self.path.split("/", maxsplit=1)[0]

    @property
    def is_principal(self):
        """Collection is a principal."""
        return bool(self.path) and "/" not in self.path

    @property
    def etag(self):
        """Encoded as quoted-string (see RFC 2616)."""
        etag = sha256()
        for item in self.get_all():
            etag.update((item.href + "/" + item.etag).encode())
        etag.update(json.dumps(self.get_meta(), sort_keys=True).encode())
        return '"%s"' % etag.hexdigest()

    def sync(self, old_token=None):
        """Get the current sync token and changed items for synchronization.

        ``old_token`` an old sync token which is used as the base of the
        delta update. If sync token is missing, all items are returned.
        ValueError is raised for invalid or old tokens.

        WARNING: This simple default implementation treats all sync-token as
                 invalid.

        """
        token = "http://radicale.org/ns/sync/%s" % self.etag.strip("\"")
        if old_token:
            raise ValueError("Sync token are not supported")
        return token, (item.href for item in self.get_all())

    def get_multi(self, hrefs):
        """Fetch multiple items.

        It's not required to return the requested items in the correct order.
        Duplicated hrefs can be ignored.

        Returns tuples with the href and the item or None if the item doesn't
        exist.

        """
        raise NotImplementedError

    def get_all(self):
        """Fetch all items."""
        raise NotImplementedError

    def get_filtered(self, filters):
        """Fetch all items with optional filtering.

        This can largely improve performance of reports depending on
        the filters and this implementation.

        Returns tuples in the form ``(item, filters_matched)``.
        ``filters_matched`` is a bool that indicates if ``filters`` are fully
        matched.

        """
        tag, start, end, simple = radicale_filter.simplify_prefilters(
            filters, collection_tag=self.get_meta("tag"))
        for item in self.get_all():
            if tag:
                if tag != item.component_name:
                    continue
                istart, iend = item.time_range
                if istart >= end or iend <= start:
                    continue
                item_simple = simple and (start <= istart or iend <= end)
            else:
                item_simple = simple
            yield item, item_simple

    def has_uid(self, uid):
        """Check if a UID exists in the collection."""
        for item in self.get_all():
            if item.uid == uid:
                return True
        return False

    def upload(self, href, item):
        """Upload a new or replace an existing item."""
        raise NotImplementedError

    def delete(self, href=None):
        """Delete an item.

        When ``href`` is ``None``, delete the collection.

        """
        raise NotImplementedError

    def get_meta(self, key=None):
        """Get metadata value for collection.

        Return the value of the property ``key``. If ``key`` is ``None`` return
        a dict with all properties

        """
        raise NotImplementedError

    def set_meta(self, props):
        """Set metadata values for collection.

        ``props`` a dict with values for properties.

        """
        raise NotImplementedError

    @property
    def last_modified(self):
        """Get the HTTP-datetime of when the collection was modified."""
        raise NotImplementedError

    def serialize(self):
        """Get the unicode string representing the whole collection."""
        if self.get_meta("tag") == "VCALENDAR":
            in_vcalendar = False
            vtimezones = ""
            included_tzids = set()
            vtimezone = []
            tzid = None
            components = ""
            # Concatenate all child elements of VCALENDAR from all items
            # together, while preventing duplicated VTIMEZONE entries.
            # VTIMEZONEs are only distinguished by their TZID, if different
            # timezones share the same TZID this produces erroneous output.
            # VObject fails at this too.
            for item in self.get_all():
                depth = 0
                for line in item.serialize().split("\r\n"):
                    if line.startswith("BEGIN:"):
                        depth += 1
                    if depth == 1 and line == "BEGIN:VCALENDAR":
                        in_vcalendar = True
                    elif in_vcalendar:
                        if depth == 1 and line.startswith("END:"):
                            in_vcalendar = False
                        if depth == 2 and line == "BEGIN:VTIMEZONE":
                            vtimezone.append(line + "\r\n")
                        elif vtimezone:
                            vtimezone.append(line + "\r\n")
                            if depth == 2 and line.startswith("TZID:"):
                                tzid = line[len("TZID:"):]
                            elif depth == 2 and line.startswith("END:"):
                                if tzid is None or tzid not in included_tzids:
                                    vtimezones += "".join(vtimezone)
                                    included_tzids.add(tzid)
                                vtimezone.clear()
                                tzid = None
                        elif depth >= 2:
                            components += line + "\r\n"
                    if line.startswith("END:"):
                        depth -= 1
            template = vobject.iCalendar()
            displayname = self.get_meta("D:displayname")
            if displayname:
                template.add("X-WR-CALNAME")
                template.x_wr_calname.value_param = "TEXT"
                template.x_wr_calname.value = displayname
            description = self.get_meta("C:calendar-description")
            if description:
                template.add("X-WR-CALDESC")
                template.x_wr_caldesc.value_param = "TEXT"
                template.x_wr_caldesc.value = description
            template = template.serialize()
            template_insert_pos = template.find("\r\nEND:VCALENDAR\r\n") + 2
            assert template_insert_pos != -1
            return (template[:template_insert_pos] +
                    vtimezones + components +
                    template[template_insert_pos:])
        if self.get_meta("tag") == "VADDRESSBOOK":
            return "".join((item.serialize() for item in self.get_all()))
        return ""


class BaseStorage:
    def __init__(self, configuration):
        """Initialize BaseStorage.

        ``configuration`` see ``radicale.config`` module.
        The ``configuration`` must not change during the lifetime of
        this object, it is kept as an internal reference.

        """
        self.configuration = configuration

    def discover(self, path, depth="0"):
        """Discover a list of collections under the given ``path``.

        ``path`` is sanitized.

        If ``depth`` is "0", only the actual object under ``path`` is
        returned.

        If ``depth`` is anything but "0", it is considered as "1" and direct
        children are included in the result.

        The root collection "/" must always exist.

        """
        raise NotImplementedError

    def move(self, item, to_collection, to_href):
        """Move an object.

        ``item`` is the item to move.

        ``to_collection`` is the target collection.

        ``to_href`` is the target name in ``to_collection``. An item with the
        same name might already exist.

        """
        raise NotImplementedError

    def create_collection(self, href, items=None, props=None):
        """Create a collection.

        ``href`` is the sanitized path.

        If the collection already exists and neither ``collection`` nor
        ``props`` are set, this method shouldn't do anything. Otherwise the
        existing collection must be replaced.

        ``collection`` is a list of vobject components.

        ``props`` are metadata values for the collection.

        ``props["tag"]`` is the type of collection (VCALENDAR or
        VADDRESSBOOK). If the key ``tag`` is missing, it is guessed from the
        collection.

        """
        raise NotImplementedError

    @contextlib.contextmanager
    def acquire_lock(self, mode, user=None):
        """Set a context manager to lock the whole storage.

        ``mode`` must either be "r" for shared access or "w" for exclusive
        access.

        ``user`` is the name of the logged in user or empty.

        """
        raise NotImplementedError

    def verify(self):
        """Check the storage for errors."""
        raise NotImplementedError
