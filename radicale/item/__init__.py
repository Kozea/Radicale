# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2014 Jean-Marc Martins
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
Module for address books and calendar entries (see ``Item``).

"""

import binascii
import contextlib
import math
import os
import re
from datetime import datetime, timedelta
from hashlib import sha256
from itertools import chain
from typing import (Any, Callable, List, MutableMapping, Optional, Sequence,
                    Tuple)

import vobject

from radicale import storage  # noqa:F401
from radicale import pathutils
from radicale.item import filter as radicale_filter
from radicale.log import logger


def read_components(s: str) -> List[vobject.base.Component]:
    """Wrapper for vobject.readComponents"""
    # Workaround for bug in InfCloud
    # PHOTO is a data URI
    s = re.sub(r"^(PHOTO(?:;[^:\r\n]*)?;ENCODING=b(?:;[^:\r\n]*)?:)"
               r"data:[^;,\r\n]*;base64,", r"\1", s,
               flags=re.MULTILINE | re.IGNORECASE)
    # Workaround for bug with malformed ICS files containing control codes
    # Filter out all control codes except those we expect to find:
    #  * 0x09 Horizontal Tab
    #  * 0x0A Line Feed
    #  * 0x0D Carriage Return
    s = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', s)
    return list(vobject.readComponents(s, allowQP=True))


def predict_tag_of_parent_collection(
        vobject_items: Sequence[vobject.base.Component]) -> Optional[str]:
    """Returns the predicted tag or `None`"""
    if len(vobject_items) != 1:
        return None
    if vobject_items[0].name == "VCALENDAR":
        return "VCALENDAR"
    if vobject_items[0].name in ("VCARD", "VLIST"):
        return "VADDRESSBOOK"
    return None


def predict_tag_of_whole_collection(
        vobject_items: Sequence[vobject.base.Component],
        fallback_tag: Optional[str] = None) -> Optional[str]:
    """Returns the predicted tag or `fallback_tag`"""
    if vobject_items and vobject_items[0].name == "VCALENDAR":
        return "VCALENDAR"
    if vobject_items and vobject_items[0].name in ("VCARD", "VLIST"):
        return "VADDRESSBOOK"
    if not fallback_tag and not vobject_items:
        # Maybe an empty address book
        return "VADDRESSBOOK"
    return fallback_tag


def check_and_sanitize_items(
        vobject_items: List[vobject.base.Component],
        is_collection: bool = False, tag: str = "") -> None:
    """Check vobject items for common errors and add missing UIDs.

    Modifies the list `vobject_items`.

    ``is_collection`` indicates that vobject_item contains unrelated
    components.

    The ``tag`` of the collection.

    """
    if tag and tag not in ("VCALENDAR", "VADDRESSBOOK", "VSUBSCRIBED"):
        raise ValueError("Unsupported collection tag: %r" % tag)
    if not is_collection and len(vobject_items) != 1:
        raise ValueError("Item contains %d components" % len(vobject_items))
    if tag == "VCALENDAR":
        if len(vobject_items) > 1:
            raise RuntimeError("VCALENDAR collection contains %d "
                               "components" % len(vobject_items))
        vobject_item = vobject_items[0]
        if vobject_item.name != "VCALENDAR":
            raise ValueError("Item type %r not supported in %r "
                             "collection" % (vobject_item.name, tag))
        component_uids = set()
        for component in vobject_item.components():
            if component.name in ("VTODO", "VEVENT", "VJOURNAL"):
                component_uid = get_uid(component)
                if component_uid:
                    component_uids.add(component_uid)
        component_name = None
        object_uid = None
        object_uid_set = False
        for component in vobject_item.components():
            # https://tools.ietf.org/html/rfc4791#section-4.1
            if component.name == "VTIMEZONE":
                continue
            if component_name is None or is_collection:
                component_name = component.name
            elif component_name != component.name:
                raise ValueError("Multiple component types in object: %r, %r" %
                                 (component_name, component.name))
            if component_name not in ("VTODO", "VEVENT", "VJOURNAL"):
                continue
            component_uid = get_uid(component)
            if not object_uid_set or is_collection:
                object_uid_set = True
                object_uid = component_uid
                if not component_uid:
                    if not is_collection:
                        raise ValueError("%s component without UID in object" %
                                         component_name)
                    component_uid = find_available_uid(
                        component_uids.__contains__)
                    component_uids.add(component_uid)
                    if hasattr(component, "uid"):
                        component.uid.value = component_uid
                    else:
                        component.add("UID").value = component_uid
            elif not object_uid or not component_uid:
                raise ValueError("Multiple %s components without UID in "
                                 "object" % component_name)
            elif object_uid != component_uid:
                raise ValueError(
                    "Multiple %s components with different UIDs in object: "
                    "%r, %r" % (component_name, object_uid, component_uid))
            # Workaround for bug in Lightning (Thunderbird)
            # Rescheduling a single occurrence from a repeating event creates
            # an event with DTEND and DURATION:PT0S
            if (hasattr(component, "dtend") and
                    hasattr(component, "duration") and
                    component.duration.value == timedelta(0)):
                logger.debug("Quirks: Removing zero duration from %s in "
                             "object %r", component_name, component_uid)
                del component.duration
            # Workaround for Evolution
            # EXDATE has value DATE even if DTSTART/DTEND is DATE-TIME.
            # The RFC is vaguely formulated on the issue.
            # To resolve the issue convert EXDATE and RDATE to
            # the same type as DTDSTART
            if hasattr(component, "dtstart"):
                ref_date = component.dtstart.value
                ref_value_param = component.dtstart.params.get("VALUE")
                for dates in chain(component.contents.get("exdate", []),
                                   component.contents.get("rdate", [])):
                    if all(type(d) is type(ref_date) for d in dates.value):
                        continue
                    for i, date in enumerate(dates.value):
                        dates.value[i] = ref_date.replace(
                            date.year, date.month, date.day)
                    with contextlib.suppress(KeyError):
                        del dates.params["VALUE"]
                    if ref_value_param is not None:
                        dates.params["VALUE"] = ref_value_param
            # vobject interprets recurrence rules on demand
            try:
                component.rruleset
            except Exception as e:
                raise ValueError("Invalid recurrence rules in %s in object %r"
                                 % (component.name, component_uid)) from e
    elif tag == "VADDRESSBOOK":
        # https://tools.ietf.org/html/rfc6352#section-5.1
        object_uids = set()
        for vobject_item in vobject_items:
            if vobject_item.name == "VCARD":
                object_uid = get_uid(vobject_item)
                if object_uid:
                    object_uids.add(object_uid)
        for vobject_item in vobject_items:
            if vobject_item.name == "VLIST":
                # Custom format used by SOGo Connector to store lists of
                # contacts
                continue
            if vobject_item.name != "VCARD":
                raise ValueError("Item type %r not supported in %r "
                                 "collection" % (vobject_item.name, tag))
            object_uid = get_uid(vobject_item)
            if not object_uid:
                if not is_collection:
                    raise ValueError("%s object without UID" %
                                     vobject_item.name)
                object_uid = find_available_uid(object_uids.__contains__)
                object_uids.add(object_uid)
                if hasattr(vobject_item, "uid"):
                    vobject_item.uid.value = object_uid
                else:
                    vobject_item.add("UID").value = object_uid
    else:
        for item in vobject_items:
            raise ValueError("Item type %r not supported in %s collection" %
                             (item.name, repr(tag) if tag else "generic"))


def check_and_sanitize_props(props: MutableMapping[Any, Any]
                             ) -> MutableMapping[str, str]:
    """Check collection properties for common errors.

    Modifies the dict `props`.

    """
    for k, v in list(props.items()):  # Make copy to be able to delete items
        if not isinstance(k, str):
            raise ValueError("Key must be %r not %r: %r" % (
                str.__name__, type(k).__name__, k))
        if not isinstance(v, str):
            if v is None:
                del props[k]
                continue
            raise ValueError("Value of %r must be %r not %r: %r" % (
                k, str.__name__, type(v).__name__, v))
        if k == "tag":
            if v not in ("", "VCALENDAR", "VADDRESSBOOK", "VSUBSCRIBED"):
                raise ValueError("Unsupported collection tag: %r" % v)
    return props


def find_available_uid(exists_fn: Callable[[str], bool], suffix: str = ""
                       ) -> str:
    """Generate a pseudo-random UID"""
    # Prevent infinite loop
    for _ in range(1000):
        r = binascii.hexlify(os.urandom(16)).decode("ascii")
        name = "%s-%s-%s-%s-%s%s" % (
            r[:8], r[8:12], r[12:16], r[16:20], r[20:], suffix)
        if not exists_fn(name):
            return name
    # Something is wrong with the PRNG or `exists_fn`
    raise RuntimeError("No available random UID found")


def get_etag(text: str) -> str:
    """Etag from collection or item.

    Encoded as quoted-string (see RFC 2616).

    """
    etag = sha256()
    etag.update(text.encode())
    return '"%s"' % etag.hexdigest()


def get_uid(vobject_component: vobject.base.Component) -> str:
    """UID value of an item if defined."""
    return (vobject_component.uid.value or ""
            if hasattr(vobject_component, "uid") else "")


def get_uid_from_object(vobject_item: vobject.base.Component) -> str:
    """UID value of an calendar/addressbook object."""
    if vobject_item.name == "VCALENDAR":
        if hasattr(vobject_item, "vevent"):
            return get_uid(vobject_item.vevent)
        if hasattr(vobject_item, "vjournal"):
            return get_uid(vobject_item.vjournal)
        if hasattr(vobject_item, "vtodo"):
            return get_uid(vobject_item.vtodo)
    elif vobject_item.name == "VCARD":
        return get_uid(vobject_item)
    return ""


def find_tag(vobject_item: vobject.base.Component) -> str:
    """Find component name from ``vobject_item``."""
    if vobject_item.name == "VCALENDAR":
        for component in vobject_item.components():
            if component.name != "VTIMEZONE":
                return component.name or ""
    return ""


def find_time_range(vobject_item: vobject.base.Component, tag: str
                    ) -> Tuple[int, int]:
    """Find enclosing time range from ``vobject item``.

    ``tag`` must be set to the return value of ``find_tag``.

    Returns a tuple (``start``, ``end``) where ``start`` and ``end`` are
    POSIX timestamps.

    This is intended to be used for matching against simplified prefilters.

    """
    if not tag:
        return radicale_filter.TIMESTAMP_MIN, radicale_filter.TIMESTAMP_MAX
    start = end = None

    def range_fn(range_start: datetime, range_end: datetime,
                 is_recurrence: bool) -> bool:
        nonlocal start, end
        if start is None or range_start < start:
            start = range_start
        if end is None or end < range_end:
            end = range_end
        return False

    def infinity_fn(range_start: datetime) -> bool:
        nonlocal start, end
        if start is None or range_start < start:
            start = range_start
        end = radicale_filter.DATETIME_MAX
        return True

    radicale_filter.visit_time_ranges(vobject_item, tag, range_fn, infinity_fn)
    if start is None:
        start = radicale_filter.DATETIME_MIN
    if end is None:
        end = radicale_filter.DATETIME_MAX
    return math.floor(start.timestamp()), math.ceil(end.timestamp())


class Item:
    """Class for address book and calendar entries."""

    collection: Optional["storage.BaseCollection"]
    href: Optional[str]
    last_modified: Optional[str]

    _collection_path: str
    _text: Optional[str]
    _vobject_item: Optional[vobject.base.Component]
    _etag: Optional[str]
    _uid: Optional[str]
    _name: Optional[str]
    _component_name: Optional[str]
    _time_range: Optional[Tuple[int, int]]

    def __init__(self,
                 collection_path: Optional[str] = None,
                 collection: Optional["storage.BaseCollection"] = None,
                 vobject_item: Optional[vobject.base.Component] = None,
                 href: Optional[str] = None,
                 last_modified: Optional[str] = None,
                 text: Optional[str] = None,
                 etag: Optional[str] = None,
                 uid: Optional[str] = None,
                 name: Optional[str] = None,
                 component_name: Optional[str] = None,
                 time_range: Optional[Tuple[int, int]] = None):
        """Initialize an item.

        ``collection_path`` the path of the parent collection (optional if
        ``collection`` is set).

        ``collection`` the parent collection (optional).

        ``href`` the href of the item.

        ``last_modified`` the HTTP-datetime of when the item was modified.

        ``text`` the text representation of the item (optional if
        ``vobject_item`` is set).

        ``vobject_item`` the vobject item (optional if ``text`` is set).

        ``etag`` the etag of the item (optional). See ``get_etag``.

        ``uid`` the UID of the object (optional). See ``get_uid_from_object``.

        ``name`` the name of the item (optional). See ``vobject_item.name``.

        ``component_name`` the name of the primary component (optional).
        See ``find_tag``.

        ``time_range`` the enclosing time range. See ``find_time_range``.

        """
        if text is None and vobject_item is None:
            raise ValueError(
                "At least one of 'text' or 'vobject_item' must be set")
        if collection_path is None:
            if collection is None:
                raise ValueError("At least one of 'collection_path' or "
                                 "'collection' must be set")
            collection_path = collection.path
        assert collection_path == pathutils.strip_path(
            pathutils.sanitize_path(collection_path))
        self._collection_path = collection_path
        self.collection = collection
        self.href = href
        self.last_modified = last_modified
        self._text = text
        self._vobject_item = vobject_item
        self._etag = etag
        self._uid = uid
        self._name = name
        self._component_name = component_name
        self._time_range = time_range

    def serialize(self) -> str:
        if self._text is None:
            try:
                self._text = self.vobject_item.serialize()
            except Exception as e:
                raise RuntimeError("Failed to serialize item %r from %r: %s" %
                                   (self.href, self._collection_path,
                                    e)) from e
        return self._text

    @property
    def vobject_item(self):
        if self._vobject_item is None:
            try:
                self._vobject_item = vobject.readOne(self._text)
            except Exception as e:
                raise RuntimeError("Failed to parse item %r from %r: %s" %
                                   (self.href, self._collection_path,
                                    e)) from e
        return self._vobject_item

    @property
    def etag(self) -> str:
        """Encoded as quoted-string (see RFC 2616)."""
        if self._etag is None:
            self._etag = get_etag(self.serialize())
        return self._etag

    @property
    def uid(self) -> str:
        if self._uid is None:
            self._uid = get_uid_from_object(self.vobject_item)
        return self._uid

    @property
    def name(self) -> str:
        if self._name is None:
            self._name = self.vobject_item.name or ""
        return self._name

    @property
    def component_name(self) -> str:
        if self._component_name is None:
            self._component_name = find_tag(self.vobject_item)
        return self._component_name

    @property
    def time_range(self) -> Tuple[int, int]:
        if self._time_range is None:
            self._time_range = find_time_range(
                self.vobject_item, self.component_name)
        return self._time_range

    def prepare(self) -> None:
        """Fill cache with values."""
        orig_vobject_item = self._vobject_item
        self.serialize()
        self.etag
        self.uid
        self.name
        self.time_range
        self.component_name
        self._vobject_item = orig_vobject_item
