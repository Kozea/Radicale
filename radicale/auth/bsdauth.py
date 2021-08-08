# This file is part of Radicale Server - Calendar Server
# Copyright © 2008 Nicolas Kandel
# Copyright © 2008 Pascal Halter
# Copyright © 2008-2017 Guillaume Ayoub
# Copyright © 2017-2019 Unrud <unrud@outlook.com>
# Copyright © 2021 <nick@kousu.ca>
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
Authentication that uses OpenBSD's authentication backends.

This is the same as Dovecot's https://doc.dovecot.org/configuration_manual/authentication/bsdauth/

In order for this to function, you must authorize it by putting the radicale user into the auth group, e.g.

usermod -G auth _radicale
"""


import sys
import ctypes

libc = ctypes.CDLL('libc.so')

def auth_userokay(name, password, type=None, style=None):
    """
    wrap auth_userokay(8). see its manpage for full details.
    quickly though: name is the username, password is the password
    style defines the authentication method to use ('passwd' by default for most users, but could be anything in /usr/libexec/auth/login_*)
      if left unset, the *user* can set it by setting their username to 'name:style'
    type is just for logging: your app should an authentication

    Example:
      auth_userokay('test1', 'test1test1', 'spiffyd')
    """

    # convert python strings to C strings
    # None doubles as the NULL pointer, when translated by ctypes
    if name is not None:
        name = ctypes.c_char_p(name.encode())
    if style is not None:
        style = ctypes.c_char_p(style.encode())
    if type is not None:
        type = ctypes.c_char_p(type.encode())
    if password is not None:
        password = ctypes.c_char_p(password.encode())

    return bool(libc.auth_userokay(name, style, type, password))



from radicale import auth

class Auth(auth.BaseAuth):
    def login(self, login, password):
        if auth_userokay(login, password):
            login = login.split(':',1)[0] # split off just the username, in case the user passed 'user:style' as their username; see auth_userokay(3).
            return login
