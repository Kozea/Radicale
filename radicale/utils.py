# This file is part of Radicale - CalDAV and CardDAV server
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

from importlib import import_module
from typing import Callable, Sequence, Type, TypeVar, Union

from radicale import config
from radicale.log import logger

_T_co = TypeVar("_T_co", covariant=True)


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
