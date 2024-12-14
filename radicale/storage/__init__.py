# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2022 Unrud <unrud@outlook.com>
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

"""
The storage module that stores calendars and address books.

Take a look at the class ``BaseCollection`` if you want to implement your own.

"""

import json
import xml.etree.ElementTree as ET
from hashlib import sha256
from typing import (Callable, ContextManager, Iterable, Iterator, Mapping,
                    Optional, Sequence, Set, Tuple, Union, overload)

import vobject

from radicale import config
from radicale import item as radicale_item
from radicale import types, utils
from radicale.item import filter as radicale_filter
from radicale.log import logger

INTERNAL_TYPES: Sequence[str] = ("multifilesystem", "multifilesystem_nolock",)

# NOTE: change only if cache structure is modified to avoid cache invalidation on update
CACHE_VERSION_RADICALE = "3.3.1"

CACHE_VERSION: bytes = ("%s=%s;%s=%s;" % ("radicale", CACHE_VERSION_RADICALE, "vobject", utils.package_version("vobject"))).encode()


def load(configuration: "config.Configuration") -> "BaseStorage":
    """Load the storage module chosen in configuration."""
    logger.debug("storage cache version: %r", str(CACHE_VERSION))
    return utils.load_plugin(INTERNAL_TYPES, "storage", "Storage", BaseStorage,
                             configuration)


class ComponentExistsError(ValueError):

    def __init__(self, path: str) -> None:
        message = "Component already exists: %r" % path
        super().__init__(message)


class ComponentNotFoundError(ValueError):

    def __init__(self, path: str) -> None:
        message = "Component doesn't exist: %r" % path
        super().__init__(message)


class BaseCollection:

    @property
    def path(self) -> str:
        """The sanitized path of the collection without leading or
        trailing ``/``."""
        raise NotImplementedError

    @property
    def owner(self) -> str:
        """The owner of the collection."""
        return self.path.split("/", maxsplit=1)[0]

    @property
    def is_principal(self) -> bool:
        """Collection is a principal."""
        return bool(self.path) and "/" not in self.path

    @property
    def etag(self) -> str:
        """Encoded as quoted-string (see RFC 2616)."""
        etag = sha256()
        for item in self.get_all():
            assert item.href
            etag.update((item.href + "/" + item.etag).encode())
        etag.update(json.dumps(self.get_meta(), sort_keys=True).encode())
        return '"%s"' % etag.hexdigest()

    @property
    def tag(self) -> str:
        """The tag of the collection."""
        return self.get_meta("tag") or ""

    def sync(self, old_token: str = "") -> Tuple[str, Iterable[str]]:
        """Get the current sync token and changed items for synchronization.

        ``old_token`` an old sync token which is used as the base of the
        delta update. If sync token is empty, all items are returned.
        ValueError is raised for invalid or old tokens.

        WARNING: This simple default implementation treats all sync-token as
                 invalid.

        """
        def hrefs_iter() -> Iterator[str]:
            for item in self.get_all():
                assert item.href
                yield item.href
        token = "http://radicale.org/ns/sync/%s" % self.etag.strip("\"")
        if old_token:
            raise ValueError("Sync token are not supported")
        return token, hrefs_iter()

    def get_multi(self, hrefs: Iterable[str]
                  ) -> Iterable[Tuple[str, Optional["radicale_item.Item"]]]:
        """Fetch multiple items.

        It's not required to return the requested items in the correct order.
        Duplicated hrefs can be ignored.

        Returns tuples with the href and the item or None if the item doesn't
        exist.

        """
        raise NotImplementedError

    def get_all(self) -> Iterable["radicale_item.Item"]:
        """Fetch all items."""
        raise NotImplementedError

    def get_filtered(self, filters: Iterable[ET.Element]
                     ) -> Iterable[Tuple["radicale_item.Item", bool]]:
        """Fetch all items with optional filtering.

        This can largely improve performance of reports depending on
        the filters and this implementation.

        Returns tuples in the form ``(item, filters_matched)``.
        ``filters_matched`` is a bool that indicates if ``filters`` are fully
        matched.

        """
        if not self.tag:
            return
        tag, start, end, simple = radicale_filter.simplify_prefilters(
            filters, self.tag)
        for item in self.get_all():
            if tag is not None and tag != item.component_name:
                continue
            istart, iend = item.time_range
            if istart >= end or iend <= start:
                continue
            yield item, simple and (start <= istart or iend <= end)

    def has_uid(self, uid: str) -> bool:
        """Check if a UID exists in the collection."""
        for item in self.get_all():
            if item.uid == uid:
                return True
        return False

    def upload(self, href: str, item: "radicale_item.Item") -> (
            "radicale_item.Item"):
        """Upload a new or replace an existing item."""
        raise NotImplementedError

    def delete(self, href: Optional[str] = None) -> None:
        """Delete an item.

        When ``href`` is ``None``, delete the collection.

        """
        raise NotImplementedError

    @overload
    def get_meta(self, key: None = None) -> Mapping[str, str]: ...

    @overload
    def get_meta(self, key: str) -> Optional[str]: ...

    def get_meta(self, key: Optional[str] = None
                 ) -> Union[Mapping[str, str], Optional[str]]:
        """Get metadata value for collection.

        Return the value of the property ``key``. If ``key`` is ``None`` return
        a dict with all properties

        """
        raise NotImplementedError

    def set_meta(self, props: Mapping[str, str]) -> None:
        """Set metadata values for collection.

        ``props`` a dict with values for properties.

        """
        raise NotImplementedError

    @property
    def last_modified(self) -> str:
        """Get the HTTP-datetime of when the collection was modified."""
        raise NotImplementedError

    def serialize(self) -> str:
        """Get the unicode string representing the whole collection."""
        if self.tag == "VCALENDAR":
            in_vcalendar = False
            vtimezones = ""
            included_tzids: Set[str] = set()
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
                                if tzid is not None:
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
        if self.tag == "VADDRESSBOOK":
            return "".join((item.serialize() for item in self.get_all()))
        return ""


class BaseStorage:

    def __init__(self, configuration: "config.Configuration") -> None:
        """Initialize BaseStorage.

        ``configuration`` see ``radicale.config`` module.
        The ``configuration`` must not change during the lifetime of
        this object, it is kept as an internal reference.

        """
        self.configuration = configuration

    def discover(
            self, path: str, depth: str = "0",
            child_context_manager: Optional[
            Callable[[str, Optional[str]], ContextManager[None]]] = None,
            user_groups: Set[str] = set([])) -> Iterable["types.CollectionOrItem"]:
        """Discover a list of collections under the given ``path``.

        ``path`` is sanitized.

        If ``depth`` is "0", only the actual object under ``path`` is
        returned.

        If ``depth`` is anything but "0", it is considered as "1" and direct
        children are included in the result.

        The root collection "/" must always exist.

        """
        raise NotImplementedError

    def move(self, item: "radicale_item.Item", to_collection: BaseCollection,
             to_href: str) -> None:
        """Move an object.

        ``item`` is the item to move.

        ``to_collection`` is the target collection.

        ``to_href`` is the target name in ``to_collection``. An item with the
        same name might already exist.

        """
        raise NotImplementedError

    def create_collection(
            self, href: str,
            items: Optional[Iterable["radicale_item.Item"]] = None,
            props: Optional[Mapping[str, str]] = None) -> BaseCollection:
        """Create a collection.

        ``href`` is the sanitized path.

        If the collection already exists and neither ``collection`` nor
        ``props`` are set, this method shouldn't do anything. Otherwise the
        existing collection must be replaced.

        ``collection`` is a list of vobject components.

        ``props`` are metadata values for the collection.

        ``props["tag"]`` is the type of collection (VCALENDAR or VADDRESSBOOK).
        If the key ``tag`` is missing, ``items`` is ignored.

        """
        raise NotImplementedError

    @types.contextmanager
    def acquire_lock(self, mode: str, user: str = "") -> Iterator[None]:
        """Set a context manager to lock the whole storage.

        ``mode`` must either be "r" for shared access or "w" for exclusive
        access.

        ``user`` is the name of the logged in user or empty.

        """
        raise NotImplementedError

    def verify(self) -> bool:
        """Check the storage for errors."""
        raise NotImplementedError
