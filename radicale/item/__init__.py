# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2022 Unrud <unrud@outlook.com>
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

"""
Module for address books and calendar entries (see ``Item``).

"""

import binascii
import contextlib
import datetime
import math
import os
import re
from hashlib import sha256
from itertools import chain
from typing import (Any, Callable, List, MutableMapping, Optional, Sequence,
                    Tuple, Union)

import vobject

import radicale.item as radicale_item
from radicale import storage  # noqa:F401
from radicale import pathutils, sharing, utils
from radicale.item import filter as radicale_filter
from radicale.log import logger

# Product ID for auto-conversion
PRODID_CONVERTED = u"-//Radicale//NONSGML " + utils.package_version("radicale") + "//EN (auto-converted)"
PRODID_SUFFIX = " (auto-converted by Radicale " + utils.package_version("radicale") + ")"
UID_SUFFIX = "-auto-converted-by-Radicale"

VCF_TO_ICS_SUPPORTED_PLACEHOLDERS: list = ["fn", "n:f", "n:g", "n:a", "age", "nickname", "year", "month", "day"]

# List of BDAY years acting as flag for "no year specified"
VCF_TO_ICS_BDAY_NO_YEAR: list = ["1604"]


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
    # Workaround delete all empty lines to avoid vobject parsing errors
    s = re.sub(r'(?m)^[ \t]*\r?\n', '', s)
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
                    component.duration.value == datetime.timedelta(0)):
                logger.debug("Quirks: Removing zero duration from %s in "
                             "object %r", component_name, component_uid)
                del component.duration
            # Workaround for Evolution
            # EXDATE has value DATE even if DTSTART/DTEND is DATE-TIME.
            # The RFC is vaguely formulated on the issue.
            # To resolve the issue convert EXDATE and RDATE to
            # the same type as DTSTART
            if hasattr(component, "dtstart"):
                ref_date = component.dtstart.value
                ref_value_param = component.dtstart.params.get("VALUE")
                for dates in chain(component.contents.get("exdate", []),
                                   component.contents.get("rdate", [])):
                    for i, date in enumerate(dates.value):
                        if type(ref_date) is datetime.datetime and type(date) is datetime.datetime:
                            if hasattr(ref_date, 'tzinfo') and ref_date.tzinfo is not None:
                                logger.trace("ITEM/check_and_sanitize_item: dtstart has tzinfo: '%s'", ref_date)
                                if hasattr(date, 'tzinfo') and date.tzinfo is None:
                                    # Ensure that datetime.datetime object has timezone set if dtstart has
                                    dates.value[i] = dates.value[i].replace(tzinfo=ref_date.tzinfo)
                                    logger.trace("ITEM/check_and_sanitize_item: overtake missing tzinfo from dtstart: '%s' -> '%s'", date, dates.value[i])
                            elif (hasattr(ref_date, 'tzinfo') and ref_date.tzinfo is None) or not hasattr(ref_date, 'tzinfo'):
                                logger.trace("ITEM/check_and_sanitize_item: dtstart has no tzinfo: '%s'", ref_date)
                                if hasattr(date, 'tzinfo') and date.tzinfo is not None:
                                    # Ensure that datetime.datetime object has no timezone set if dtstart has none
                                    dates.value[i] = dates.value[i].replace(tzinfo=None)
                                    logger.trace("ITEM/check_and_sanitize_item: remove existing tzinfo (dtstart has none): '%s' -> '%s'", date, dates.value[i])
                    if all(type(d) is type(ref_date) for d in dates.value):
                        continue
                    if dates.params.get("VALUE") == ["PERIOD"]:
                        if not utils.vobject_supports_period():
                            raise ValueError("PERIOD not supported by used vobject=%s in object %r" % (utils.package_version("vobject"), component_uid))
                        # period     = period-explicit / period-start
                        # period-explicit = date-time "/" date-time
                        # period-start = date-time "/" dur-value
                        for i, date in enumerate(dates.value):
                            if not isinstance(date, tuple):
                                raise ValueError("invalid PERIOD (not a tuple) in object %r" % component_uid)
                            if len(date) != 2:
                                raise ValueError("invalid PERIOD (not 2 elements) in object %r" % component_uid)
                            if type(date[0]) is datetime.datetime and type(date[1]) is datetime.datetime:
                                if (date[0] > date[1]):
                                    raise ValueError("invalid PERIOD (end before start) in object %r" % component_uid)
                                # skip explicit tzinfo check for now, no buggy client known
                                logger.trace("ITEM/check_and_sanitize_item: PERIOD/start-stop found: '%s'", date)
                            elif type(date[0]) is datetime.datetime and type(date[1]) is datetime.timedelta:
                                logger.trace("ITEM/check_and_sanitize_item: PERIOD/start-duration found: '%s'", date)
                            else:
                                raise ValueError("invalid PERIOD (element types not matching) in object %r" % component_uid)
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

    def range_fn(range_start: datetime.datetime, range_end: datetime.datetime,
                 is_recurrence: bool) -> bool:
        nonlocal start, end
        if start is None or range_start < start:
            start = range_start
        if end is None or end < range_end:
            end = range_end
        return False

    def infinity_fn(range_start: datetime.datetime) -> bool:
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


def verify(file: str, encoding: str):
    logger.info("Verifying item: %s", file)
    with open(file, "rb") as f:
        content_raw = f.read()
    content = content_raw.decode(encoding)
    logger.info("Verifying item: %s has sha256sum %r", file, utils.sha256_bytes(content_raw))
    try:
        vobject_items = read_components(content)  # noqa: F841
    except Exception as e:
        logger.error("Verifying item: %s problem: %s", file, e)
        logger.warning("Item content:\n%s", utils.textwrap_str(content))
        logger.info("Item content (hexdump):\n%s", utils.hexdump_str(content))
        logger.info("Item content (hexdump/lines):\n%s", utils.hexdump_lines(content))
        return False
    else:
        logger.info("Verifying item(vobject/read_components): %s successful", file)

    try:
        tag = radicale_item.predict_tag_of_whole_collection(vobject_items)
        if tag is not None:
            radicale_item.check_and_sanitize_items(vobject_items, tag=tag)
        else:
            raise ValueError("collection tag cannot be predicted")
    except Exception as e:
        logger.error("Verifying item: %s problem: %s", file, e)
        logger.warning("Item content:\n%s", utils.textwrap_str(content))
        return False
    else:
        logger.info("Verifying item(radicale/check_and_sanitze): %s successful", file)

    vobject_item, = vobject_items

    try:
        item = radicale_item.Item(collection_path="verify", vobject_item=vobject_item)
    except Exception as e:
        logger.error("Verifying item: %s problem: %s", file, e)
        logger.warning("Item content:\n%s", utils.textwrap_str(content))
        return False
    else:
        logger.info("Verifying item(radicale/Item): %s successful", file)

    try:
        item.prepare()
    except Exception as e:
        logger.error("Verifying item: %s problem: %s", file, e)
        logger.warning("Item content:\n%s", utils.textwrap_str(content))
        return False
    else:
        logger.info("Verifying item(radicale/prepare): %s successful", file)

    return True


def replace_placeholders(text: str, placeholder_mapping: dict) -> str:
    logger.trace("item/convert_vcf_to_ics: resolve placeholders: %r", text)

    for placeholder in placeholder_mapping:
        text = text.replace(placeholder, placeholder_mapping[placeholder])

    logger.trace("item/convert_vcf_to_ics: resolve [..|..] in  : %r", text)

    # resolve [..|..] recursive
    pattern = re.compile('(.*)(\\[)([^|]+)\\|([^\\]]*)(\\])(.*)')
    while True:
        match = pattern.match(text)
        if not match:
            # nothing more todo
            break
        else:
            logger.trace("item/convert_vcf_to_ics: resolve match       : %r", match[0])
            # check for still unresolved placeholders
            unresolved = False
            for placeholder in VCF_TO_ICS_SUPPORTED_PLACEHOLDERS:
                if "!" + placeholder + "!" in match[3]:
                    unresolved = True
                    break
            if unresolved:
                # not resolved variable
                if '|' in match[4]:
                    # further recursion required
                    text = match[1] + match[2] + match[4] + match[5] + match[6]
                    logger.trace("item/convert_vcf_to_ics: resolve continue    : %r", text)
                else:
                    text = match[1] + match[4] + match[6]
                    logger.trace("item/convert_vcf_to_ics: resolve final result: %r", text)
                    break
            else:
                # resolved variable
                text = match[1] + match[3] + match[6]
                logger.trace("item/convert_vcf_to_ics: resolve [..|..] match/replace(resolved) result: %r", text)
    return text


def trigger_to_timedelta(trigger) -> Union[datetime.timedelta, None]:
    # workaround as vobject is not supporting direct set of value
    # limited implementatino of reverse function of timedeltaToString in vobject/icalendar.py
    pattern = re.compile('([+-])?([0-9]+)([WDHM])$')
    match = pattern.match(trigger)
    if not match:
        logger.error("item/convert_vcf_to_ics: trigger time value not valid: %r", trigger)
        return None

    sign = 1
    if match[1] == "-":
        sign = -1

    value = int(match[2]) * sign

    td: Union[datetime.timedelta, None] = None

    if match[3] == "D":
        td = datetime.timedelta(days=value)
    elif match[3] == "M":
        td = datetime.timedelta(minutes=value)
    elif match[3] == "H":
        td = datetime.timedelta(hours=value)
    elif match[3] == "W":
        td = datetime.timedelta(weeks=value)

    return td


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
                raise RuntimeError("Failed to serialize item %r with UID %r from %r: %s" %
                                   (self.href, self.uid, self._collection_path,
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

    def convert_vcf_to_ics(self, ShareActions: dict = {}) -> Union["Item", None]:
        logger.trace("item/convert_vcf_to_ics: ShareActions: %r", ShareActions)
        logger.trace("item/convert_vcf_to_ics: convert VCF to ICS (href): %r", self.href)
        logger.trace("item/convert_vcf_to_ics: convert VCF to ICS (vobject): %r", self.vobject_item)
        if self.vobject_item.name != "VCARD":
            logger.trace("item/convert_vcf_to_ics: item is not a VCARD (skip): %r", self.href)
            return None
        else:
            logger.trace("item/convert_vcf_to_ics: item is a VCARD (ok): %r", self.href)
        if not hasattr(self.vobject_item, "bday"):
            logger.trace("item/convert_vcf_to_ics: miss bday (skip): %r", self.href)
            return None
        else:
            pass

        bday = self.vobject_item.bday
        logger.trace("item/convert_vcf_to_ics: has bday (ok): %r -> %r", self.href, bday.value)

        pattern = re.compile('^([0-9]{4})-?([0-9]{2})-?([0-9]{2})$')
        match = pattern.match(bday.value)
        if not match:
            logger.trace("item/convert_vcf_to_ics: has unsupported bday: %r -> %r", self.href, bday.value)
            return None
        else:
            pass

        vcard_has_year = True  # default
        vcard_age_exceed_max = False  # default

        if str(match[1]) in VCF_TO_ICS_BDAY_NO_YEAR:
            logger.trace("item/convert_vcf_to_ics: has 'no year' bday: %r -> %r", self.href, bday.value)
            vcard_has_year = False

        placeholder_mapping: dict = {}

        bdayS = match[1] + match[2] + match[3]
        bdayY = int(match[1])
        bdayM = int(match[2])
        bdayD = int(match[3])

        placeholder_mapping['{year}'] = match[1]
        placeholder_mapping['{month}'] = match[2]
        placeholder_mapping['{day}'] = match[3]

        if not vcard_has_year:
            placeholder_mapping['{year}'] = "????"

        # create ICS
        if hasattr(self.vobject_item, "fn"):
            name = self.vobject_item.fn.value
        elif hasattr(self.vobject_item, "n"):
            name = self.vobject_item.n.value.family + " " + self.vobject_item.n.value.given
        elif hasattr(self.vobject_item, "nickname"):
            name = self.vobject_item.nickname.value
        else:
            logger.trace("item/convert_vcf_to_ics: has bday but neither FN or N or NICKNAME (skip): %r", self.href)
            return None

        if hasattr(self.vobject_item, "nickname") and self.vobject_item.nickname.value != "":
            placeholder_mapping['{nickname}'] = self.vobject_item.nickname.value
        else:
            placeholder_mapping['{nickname}'] = '!nickname!'

        if hasattr(self.vobject_item, "fn") and self.vobject_item.fn.value != "":
            placeholder_mapping['{fn}'] = self.vobject_item.fn.value
        else:
            placeholder_mapping['{nickname}'] = '!fn!'

        # rfc6350#6.2 FamilyName;GivenName;AdditionalNames;HonorificPrefixes;HonorificSuffixes
        if hasattr(self.vobject_item, "n") and self.vobject_item.n.value.family != "":
            placeholder_mapping['{n:f}'] = self.vobject_item.n.value.family
        else:
            placeholder_mapping['{n:f}'] = '!n:f!'

        if hasattr(self.vobject_item, "n") and self.vobject_item.n.value.given != "":
            placeholder_mapping['{n:g}'] = self.vobject_item.n.value.given
        else:
            placeholder_mapping['{n:g}'] = '!n:g!'

        if hasattr(self.vobject_item, "n") and self.vobject_item.n.value.additional != "":
            placeholder_mapping['{n:a}'] = self.vobject_item.n.value.additional
        else:
            placeholder_mapping['{n:a}'] = '!n:a!'

        # create VCALENDAR
        item_ics = vobject.newFromBehavior('vcalendar')

        # set PRODID
        if hasattr(self.vobject_item, "prodid"):
            item_ics.add('prodid').value = self.vobject_item.prodid.value + PRODID_SUFFIX
        else:
            item_ics.add('prodid').value = PRODID_CONVERTED

        # prepare SUMMARY
        if ShareActions is not None and 'config' in ShareActions and 'conversion_bday_summary_template' in ShareActions['config']:
            summary = ShareActions['config']['conversion_bday_summary_template']
        elif ShareActions is not None and 'config_default' in ShareActions and 'conversion_bday_summary_template' in ShareActions['config_default']:
            summary = ShareActions['config_default']['conversion_bday_summary_template']
        else:
            summary = sharing.SHARING_BDAY_SUMMARY_TEMPLATE_DEFAULT  # fallback

        # prepare DESCRIPTION
        if ShareActions is not None and 'config' in ShareActions and 'conversion_bday_description_template' in ShareActions['config']:
            description = ShareActions['config']['conversion_bday_description_template']
        elif ShareActions is not None and 'config_default' in ShareActions and 'conversion_bday_description_template' in ShareActions['config_default']:
            description = ShareActions['config_default']['conversion_bday_description_template']
        else:
            description = sharing.SHARING_BDAY_DESCRIPTION_TEMPLATE_DEFAULT  # fallback

        # create CATEGORIES
        if ShareActions is not None and 'config' in ShareActions and 'conversion_bday_categories' in ShareActions['config']:
            categories = ShareActions['config']['conversion_bday_categories'].split(',')
        elif ShareActions is not None and 'config_default' in ShareActions and 'conversion_bday_categories' in ShareActions['config_default']:
            categories = ShareActions['config_default']['conversion_bday_categories'].split(',')
        else:
            categories = sharing.SHARING_BDAY_CATEGORIES_DEFAULT.split(',')  # fallback

        # check ALARM
        if ShareActions is not None and 'config' in ShareActions and 'conversion_bday_alarm_trigger_template' in ShareActions['config']:
            alarm_trigger = ShareActions['config']['conversion_bday_alarm_trigger_template']
        elif ShareActions is not None and 'config_default' in ShareActions and 'conversion_bday_alarm_trigger_template' in ShareActions['config_default']:
            alarm_trigger = ShareActions['config_default']['conversion_bday_alarm_trigger_template']
        else:
            alarm_trigger = ""  # default

        vevent_enable_age = False
        age_max = 0
        if vcard_has_year and ("{age}" in summary or "{age}" in description or "age" in alarm_trigger):
            if ShareActions is not None and 'config' in ShareActions and 'conversion_bday_age_max' in ShareActions['config']:
                age_max = ShareActions['config']['conversion_bday_age_max']
            elif ShareActions is not None and 'config_default' in ShareActions and 'conversion_bday_age_max' in ShareActions['config_default']:
                age_max = ShareActions['config_default']['conversion_bday_age_max']
            else:
                age_max = sharing.SHARING_BDAY_AGE_MAX_DEFAULT  # fallback

            # check for age_max in the past
            currentDateTime = datetime.datetime.now()
            date = currentDateTime.date()
            if bdayY + age_max < date.year:
                logger.trace("item/convert_vcf_to_ics: bdayY=%d + age_max=%d < current year %d -> disable age support", bdayY, age_max, date.year)
                vcard_age_exceed_max = True
                age_max = 0
            else:
                vevent_enable_age = True

        # create UID
        if hasattr(self.vobject_item, "uid"):
            pattern = re.compile('^(.*)-[0-9a-fA-F]{12}(.*)$')
            match = pattern.match(self.vobject_item.uid.value)
            if match:
                # replace part of UUID by bday
                uid = match[1] + '-' + 'bda0' + bdayS + match[2]
            else:
                uid = self.vobject_item.uid.value + UID_SUFFIX
        else:
            uid = match[1] + match[2] + match[3] + "@" + name.replace(" ", "-") + UID_SUFFIX

        age = 0
        while age <= age_max:
            # create EVENT
            vevent = item_ics.add('vevent')

            # set DTSTART
            if vevent_enable_age:
                dtstart = datetime.date(bdayY + age, bdayM, bdayD)
            else:
                dtstart = datetime.date(bdayY, bdayM, bdayD)
            vevent.add('dtstart').value = dtstart

            # calculate and set DTEND
            dtend = dtstart + datetime.timedelta(days=1)
            vevent.add('dtend').value = dtend

            # set UID
            if vevent_enable_age:
                uid_value = uid + "-AGE-" + str(age)
            else:
                uid_value = uid
            vevent.add('uid').value = uid_value

            # set placehoder for "age"
            if vevent_enable_age:
                placeholder_mapping['{age}'] = str(age)
            elif not vcard_has_year:
                placeholder_mapping['{age}'] = "??"
            elif vcard_age_exceed_max:
                placeholder_mapping['{age}'] = "!age!"

            # set SUMMARY
            vevent.add('summary').value = replace_placeholders(summary, placeholder_mapping)

            # set CATEGORIES
            if categories is not None and categories != []:
                vevent.add('categories').value = categories

            # set CLASS
            vevent.add('class').value = "PRIVATE"

            # set STATUS
            vevent.add('status').value = "CONFIRMED"

            # set VALARM
            if alarm_trigger is not None and alarm_trigger != "":
                for entry in alarm_trigger.split('$'):
                    (trigger, alarm_description) = entry.split(';')
                    logger.trace("item/convert_vcf_to_ics: alarm trigger entry: %r (trigger=%r description=%r)", entry, trigger, alarm_description)
                    td = trigger_to_timedelta(trigger)
                    if td is not None:
                        valarm = vevent.add('valarm')
                        valarm.add('action').value = "DISPLAY"
                        valarm.add('description').value = replace_placeholders(alarm_description, placeholder_mapping)
                        valarm.add('trigger').value = td

            # set RRULE
            if not vevent_enable_age:
                vevent.add('rrule').value = "FREQ=YEARLY"

            # add transparency
            vevent.add('transp').value = "TRANSPARENT"

            # set DESCRIPTION
            if description != "":
                vevent.add('description').value = replace_placeholders(description, placeholder_mapping)

            # increase age
            age = age + 1

        href = self.href
        if href is not None:
            href = href.removesuffix(".vcf") + ".ics"

        etag = self.etag
        # replace 14 leading chars of etag "<hexdigits>" by special format bda0YYYYMMDD00
        etag = '"bda0' + bdayS + '00' + etag[15:]

        item_new: Item = Item(
                collection=self.collection,
                etag=etag,
                href=href,
                vobject_item=item_ics)

        logger.trace("storage: item generated/vobject: %r", item_ics.serialize())
        logger.trace("storage: item orig     /etag   : %r", self.etag)
        logger.trace("storage: item generated/etag   : %r", item_new.etag)
        logger.trace("storage: item generated/href   : %r", item_new.href)

        return item_new
