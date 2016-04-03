#
# This file is part of Radicale Server - Calendar Server
# Copyright (C) 2015 Troels E. Linnet
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

# Module docstring.
"""Module for checking Radicale dependencies."""

# Python modules.


# Essential packages.
#####################

# Path to config file.
try:
    import os
    os.path.expanduser("~/.config/radicale")
    os_path_expanduser = True
except ImportError:
    os_path_expanduser = False
