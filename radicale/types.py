# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2020 Unrud <unrud@outlook.com>
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

import contextlib
from typing import (Any, Callable, ContextManager, Iterator, List, Mapping,
                    MutableMapping, Protocol, Sequence, Tuple, TypeVar, Union,
                    runtime_checkable)

WSGIResponseHeaders = Union[Mapping[str, str], Sequence[Tuple[str, str]]]
WSGIResponse = Tuple[int, WSGIResponseHeaders, Union[None, str, bytes]]
WSGIEnviron = Mapping[str, Any]
WSGIStartResponse = Callable[[str, List[Tuple[str, str]]], Any]

CONFIG = Mapping[str, Mapping[str, Any]]
MUTABLE_CONFIG = MutableMapping[str, MutableMapping[str, Any]]
CONFIG_SCHEMA = Mapping[str, Mapping[str, Any]]

_T = TypeVar("_T")


def contextmanager(func: Callable[..., Iterator[_T]]
                   ) -> Callable[..., ContextManager[_T]]:
    """Compatibility wrapper for `contextlib.contextmanager` with
    `typeguard`"""
    result = contextlib.contextmanager(func)
    result.__annotations__ = {**func.__annotations__,
                              "return": ContextManager[_T]}
    return result


@runtime_checkable
class InputStream(Protocol):
    def read(self, size: int = ...) -> bytes: ...


@runtime_checkable
class ErrorStream(Protocol):
    def flush(self) -> object: ...

    def write(self, s: str) -> object: ...


from radicale import item, storage  # noqa:E402 isort:skip

CollectionOrItem = Union[item.Item, storage.BaseCollection]
