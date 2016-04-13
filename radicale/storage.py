# This file is part of Radicale Server - Calendar Server
# Copyright © 2014 Jean-Marc Martins
# Copyright © 2012-2016 Guillaume Ayoub
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
Storage backends.

This module loads the storage backend, according to the storage configuration.

Default storage uses one folder per collection and one file per collection
entry.

"""

import json
import os
import posixpath
import shutil
import sys
import time
from contextlib import contextmanager
from hashlib import md5
from uuid import uuid4

import vobject

from . import config, log


def _load():
    """Load the storage manager chosen in configuration."""
    storage_type = config.get("storage", "type")
    if storage_type == "multifilesystem":
        module = sys.modules[__name__]
    else:
        __import__(storage_type)
        module = sys.modules[storage_type]
    sys.modules[__name__].Collection = module.Collection


FOLDER = os.path.expanduser(config.get("storage", "filesystem_folder"))
FILESYSTEM_ENCODING = sys.getfilesystemencoding()
STORAGE_ENCODING = config.get("encoding", "stock")
MIMETYPES = {"VADDRESSBOOK": "text/vcard", "VCALENDAR": "text/calendar"}


def get_etag(text):
    """Etag from collection or item."""
    etag = md5()
    etag.update(text.encode("utf-8"))
    return '"%s"' % etag.hexdigest()


def sanitize_path(path):
    """Make path absolute with leading slash to prevent access to other data.

    Preserve a potential trailing slash.

    """
    trailing_slash = "/" if path.endswith("/") else ""
    path = posixpath.normpath(path)
    new_path = "/"
    for part in path.split("/"):
        if not part or part in (".", ".."):
            continue
        new_path = posixpath.join(new_path, part)
    trailing_slash = "" if new_path.endswith("/") else trailing_slash
    return new_path + trailing_slash


def is_safe_filesystem_path_component(path):
    """Check if path is a single component of a filesystem path.

    Check that the path is safe to join too.

    """
    return (
        path and not os.path.splitdrive(path)[0] and
        not os.path.split(path)[0] and path not in (os.curdir, os.pardir))


def path_to_filesystem(root, *paths):
    """Convert path to a local filesystem path relative to base_folder.

    Conversion is done in a secure manner, or raises ``ValueError``.

    """
    root = sanitize_path(root)
    paths = [sanitize_path(path).strip("/") for path in paths]
    safe_path = root
    for path in paths:
        if not path:
            continue
        for part in path.split("/"):
            if not is_safe_filesystem_path_component(part):
                log.LOGGER.debug(
                    "Can't translate path safely to filesystem: %s", path)
                raise ValueError("Unsafe path")
            safe_path = os.path.join(safe_path, part)
    return safe_path


class Item:
    def __init__(self, item, href, etag):
        self.item = item
        self.href = href
        self.etag = etag

    def __getattr__(self, attr):
        return getattr(self.item, attr)


class Collection:
    """Collection stored in several files per calendar."""
    def __init__(self, path, principal=False):
        """Initialize the collection.

        ``path`` must be the normalized relative path of the collection, using
        the slash as the folder delimiter, with no leading nor trailing slash.

        """
        self.encoding = "utf-8"
        # path should already be sanitized
        self.path = sanitize_path(path).strip("/")
        self._filesystem_path = path_to_filesystem(FOLDER, self.path)
        split_path = self.path.split("/")
        if len(split_path) > 1:
            # URL with at least one folder
            self.owner = split_path[0]
        else:
            self.owner = None
        self.is_principal = principal

    @classmethod
    def discover(cls, path, depth="1"):
        """Discover a list of collections under the given ``path``.

        If ``depth`` is "0", only the actual object under ``path`` is
        returned.

        If ``depth`` is anything but "0", it is considered as "1" and direct
        children are included in the result. If ``include_container`` is
        ``True`` (the default), the containing object is included in the
        result.

        The ``path`` is relative.

        """
        # path == None means wrong URL
        if path is None:
            return

        # path should already be sanitized
        sane_path = sanitize_path(path).strip("/")
        attributes = sane_path.split("/")
        if not attributes:
            return

        # Try to guess if the path leads to a collection or an item
        if os.path.exists(path_to_filesystem(
                FOLDER, *attributes[:-1]) + ".props"):
            attributes.pop()

        path = "/".join(attributes)

        principal = len(attributes) <= 1
        collection = cls(path, principal)
        yield collection
        if depth != "0":
            # TODO: fix this
            items = list(collection.list())
            if items:
                for item in items:
                    yield collection.get(item[0])
            else:
                _, directories, _ = next(os.walk(collection._filesystem_path))
                for sub_path in directories:
                    full_path = os.path.join(collection._filesystem_path, sub_path)
                    if os.path.exists(path_to_filesystem(full_path)):
                        yield cls(posixpath.join(path, sub_path))

    @classmethod
    def create_collection(cls, href, collection=None, tag=None):
        """Create a collection.

        ``collection`` is a list of vobject components.

        ``tag`` is the type of collection (VCALENDAR or VADDRESSBOOK). If
        ``tag`` is not given, it is guessed from the collection.

        """
        path = path_to_filesystem(FOLDER, href)
        if not os.path.exists(path):
            os.makedirs(path)
        if not tag and collection:
            tag = collection[0].name
        self = cls(href)
        if tag == "VCALENDAR":
            self.set_meta("tag", "VCALENDAR")
            if collection:
                collection, = collection
                for content in ("vevent", "vtodo", "vjournal"):
                    if content in collection.contents:
                        for item in getattr(collection, "%s_list" % content):
                            new_collection = vobject.iCalendar()
                            new_collection.add(item)
                            self.upload(uuid4().hex, new_collection)
        elif tag == "VCARD":
            self.set_meta("tag", "VADDRESSBOOK")
            if collection:
                for card in collection:
                    self.upload(uuid4().hex, card)
        return self

    def list(self):
        """List collection items."""
        try:
            hrefs = os.listdir(self._filesystem_path)
        except IOError:
            return

        for href in hrefs:
            path = os.path.join(self._filesystem_path, href)
            if not href.endswith(".props") and os.path.isfile(path):
                with open(path, encoding=STORAGE_ENCODING) as fd:
                    yield href, get_etag(fd.read())

    def get(self, href):
        """Fetch a single item."""
        if not href:
            return
        href = href.strip("{}").replace("/", "_")
        if is_safe_filesystem_path_component(href):
            path = os.path.join(self._filesystem_path, href)
            if os.path.isfile(path):
                with open(path, encoding=STORAGE_ENCODING) as fd:
                    text = fd.read()
                return Item(vobject.readOne(text), href, get_etag(text))
        else:
            log.LOGGER.debug(
                "Can't tranlate name safely to filesystem, "
                "skipping component: %s", href)

    def get_multi(self, hrefs):
        """Fetch multiple items. Duplicate hrefs must be ignored.

        Functionally similar to ``get``, but might bring performance benefits
        on some storages when used cleverly.

        """
        for href in set(hrefs):
            yield self.get(href)

    def has(self, href):
        """Check if an item exists by its href."""
        return self.get(href) is not None

    def upload(self, href, item):
        """Upload a new item."""
        # TODO: use returned object in code
        if is_safe_filesystem_path_component(href):
            path = path_to_filesystem(self._filesystem_path, href)
            if not os.path.exists(path):
                text = item.serialize()
                with open(path, "w", encoding=STORAGE_ENCODING) as fd:
                    fd.write(text)
                return href, get_etag(text)
        else:
            log.LOGGER.debug(
                "Can't tranlate name safely to filesystem, "
                "skipping component: %s", href)

    def update(self, href, item, etag=None):
        """Update an item."""
        # TODO: use etag in code and test it here
        # TODO: use returned object in code
        if is_safe_filesystem_path_component(href):
            path = path_to_filesystem(self._filesystem_path, href)
            if os.path.exists(path):
                with open(path, encoding=STORAGE_ENCODING) as fd:
                    text = fd.read()
                if not etag or etag == get_etag(text):
                    new_text = item.serialize()
                    with open(path, "w", encoding=STORAGE_ENCODING) as fd:
                        fd.write(new_text)
                    return get_etag(new_text)
        else:
            log.LOGGER.debug(
                "Can't tranlate name safely to filesystem, "
                "skipping component: %s", href)

    def delete(self, href=None, etag=None):
        """Delete an item.

        When ``href`` is ``None``, delete the collection.

        """
        # TODO: use etag in code and test it here
        # TODO: use returned object in code
        if href is None:
            # Delete the collection
            if os.path.isdir(self._filesystem_path):
                shutil.rmtree(self._filesystem_path)
            props_path = self._filesystem_path + ".props"
            if os.path.isfile(props_path):
                os.remove(props_path)
            return
        elif is_safe_filesystem_path_component(href):
            # Delete an item
            path = path_to_filesystem(self._filesystem_path, href)
            if os.path.isfile(path):
                with open(path, encoding=STORAGE_ENCODING) as fd:
                    text = fd.read()
                if not etag or etag == get_etag(text):
                    os.remove(path)
                    return
        else:
            log.LOGGER.debug(
                "Can't tranlate name safely to filesystem, "
                "skipping component: %s", href)

    @contextmanager
    def at_once(self):
        """Set a context manager buffering the reads and writes."""
        # TODO: use in code
        # TODO: use a file locker
        yield

    def get_meta(self, key):
        """Get metadata value for collection."""
        props_path = self._filesystem_path + ".props"
        if os.path.exists(props_path):
            with open(props_path, encoding=STORAGE_ENCODING) as prop_file:
                return json.load(prop_file).get(key)

    def set_meta(self, key, value):
        """Get metadata value for collection."""
        props_path = self._filesystem_path + ".props"
        properties = {}
        if os.path.exists(props_path):
            with open(props_path, encoding=STORAGE_ENCODING) as prop_file:
                properties.update(json.load(prop_file))

        if value:
            properties[key] = value
        else:
            properties.pop(key, None)

        with open(props_path, "w+", encoding=STORAGE_ENCODING) as prop_file:
            json.dump(properties, prop_file)

    @property
    def last_modified(self):
        """Get the HTTP-datetime of when the collection was modified."""
        last = max([
            os.path.getmtime(os.path.join(self._filesystem_path, filename))
            for filename in os.listdir(self._filesystem_path)] or [0])
        return time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(last))

    def serialize(self):
        items = []
        for href in os.listdir(self._filesystem_path):
            path = os.path.join(self._filesystem_path, href)
            if os.path.isfile(path) and not path.endswith(".props"):
                with open(path, encoding=STORAGE_ENCODING) as fd:
                    items.append(vobject.readOne(fd.read()))
        if self.get_meta("tag") == "VCALENDAR":
            collection = vobject.iCalendar()
            for item in items:
                for content in ("vevent", "vtodo", "vjournal"):
                    if content in item.contents:
                        collection.add(getattr(item, content))
                        break
            return collection.serialize()
        elif self.get_meta("tag") == "VADDRESSBOOK":
            return "".join([item.serialize() for item in items])
        return ""

    @property
    def etag(self):
        return get_etag(self.serialize())
