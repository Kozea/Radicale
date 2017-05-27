---
layout: page
title: Plugins
permalink: /plugins/
---

Radicale can be extended by plugins for authentication, rights management and
storage. Plugins are **python** modules.

## Getting started

To get started we walk through the creation of a simple authentication
plugin, that accepts login attempts if the username and password are equal.

The easiest way to develop and install **python** modules is
[Distutils](https://docs.python.org/3/distutils/setupscript.html).
For a minimal setup create the file `setup.py` with the following content
in an empty folder:

```python
#!/usr/bin/env python3

from distutils.core import setup

setup(packages=["silly_auth_plugin"])
```

In the same folder create the sub-folder `silly_auth_plugin`. The folder
must have the same name as specified in `packages` above.

Create the file `\_\_init\_\_.py` in the `silly_auth_plugin` folder with the
following content:

```python
from radicale.auth import BaseAuth

class Auth(BaseAuth):
    def is_authenticated(self, user, password):
        self.logger.info("Login attempt by '%s' with password '%s'",
                         user, password)
        return user == password
```

Install the python module by running the following command in the same folder
as `setup.py`:
```shell
python3 -m pip install --upgrade .
```

To make use this great creation in Radicale, set the configuration option
`type` in the `auth` section to `silly_auth_plugin`.

## Authentication plugins
This plugin type is used to check login credentials.
The module must contain a class `Auth` that extends
`radicale.auth.BaseAuth`. Take a look at the file `radicale/auth.py` in
Radicale's source code for more information.

## Rights management plugins
This plugin type is used to check if a user has access to a path.
The module must contain a class `Rights` that extends
`radicale.auth.BaseAuth`. Take a look at the file `radicale/rights.py` in
Radicale's source code for more information.

## Storage plugins
This plugin is used to store collections and items.
The module must contain a class `Storage` that extends
`radicale.auth.BaseStorage`. Take a look at the file `radicale/storage.py` in
Radicale's source code for more information.
