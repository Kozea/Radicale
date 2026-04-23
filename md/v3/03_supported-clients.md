## Supported Clients

Radicale has been tested with:

* [Android](https://android.com/) with
  [DAVx⁵](https://www.davx5.com/) (formerly DAVdroid),
* [OneCalendar](https://www.onecalendar.nl/)
* [GNOME Calendar](https://wiki.gnome.org/Apps/Calendar),
  [Contacts](https://wiki.gnome.org/Apps/Contacts) and
  [Evolution](https://wiki.gnome.org/Apps/Evolution)
* [KDE PIM Applications](https://kontact.kde.org/),
  [KDE Merkuro](https://apps.kde.org/de/merkuro/)
* [Mozilla Thunderbird](https://www.mozilla.org/thunderbird/) ([Thunderbird/Radicale](https://github.com/Kozea/Radicale/wiki/Client-Thunderbird)) with
  [CardBook](https://addons.mozilla.org/thunderbird/addon/cardbook/) and
  [Lightning](https://www.mozilla.org/projects/calendar/)
* [InfCloud](https://www.inf-it.com/open-source/clients/infcloud/) ([InfCloud/Radicale](https://github.com/Kozea/Radicale/wiki/Client-InfCloud)),
  [CalDavZAP](https://www.inf-it.com/open-source/clients/caldavzap/),
  [CardDavMATE](https://www.inf-it.com/open-source/clients/carddavmate/) and
  [Open Calendar](https://github.com/algoo/open-calendar/)
* [pimsync](https://pimsync.whynothugo.nl/) ([pimsync/Radicale](https://github.com/Kozea/Radicale/wiki/Client-pimsync))

Many clients do not support the creation of new calendars and address books.
You can use Radicale's web interface
(e.g. <http://localhost:5232>) to create and manage address books and calendars.

In some clients, it is sufficient to simply enter the URL of the Radicale server
(e.g. `http://localhost:5232`) and your username. In others, you have to
enter the URL of the collection directly (e.g. `http://localhost:5232/user/calendar`).

Some clients (notably macOS's Calendar.app) may silently refuse to include
account credentials over unsecured HTTP, leading to unexpected authentication
failures. In these cases, you want to make sure the Radicale server is
[accessible over HTTPS](#ssl).

#### DAVx⁵

Enter the URL of the Radicale server (e.g. `http://localhost:5232`) and your
username. DAVx⁵ will show all existing calendars and address books and you
can create new ones.

#### OneCalendar

When adding account, select CalDAV account type, then enter username, password and the
Radicale server (e.g. `https://yourdomain:5232`). OneCalendar will show all
existing calendars and (FIXME: address books), you need to select which ones
you want to see. OneCalendar supports many other server types too.

#### GNOME Calendar, Contacts

GNOME 46 added CalDAV and CardDAV support to _GNOME Online Accounts_.

Open GNOME Settings, navigate to _Online Accounts_ > _Connect an Account_ > _Calendar, Contacts and Files_.
Enter the URL (e.g. `https://example.com/radicale`) and your credentials then click _Sign In_.
In the pop-up dialog, turn off _Files_. After adding Radicale in _GNOME Online Accounts_,
it should be available in GNOME Contacts and GNOME Calendar.

#### Evolution

In **Evolution** add a new calendar and address book respectively with WebDAV.
Enter the URL of the Radicale server (e.g. `http://localhost:5232`) and your
username. Clicking on the search button will list the existing calendars and
address books.

Adding CalDAV and CardDAV accounts in Evolution will automatically make them
available in GNOME Contacts and GNOME Calendar.

#### KDE PIM Applications

In **Kontact** add a _DAV Groupware resource_ to Akonadi under
_Settings > Configure Kontact > Calendar > General > Calendars_,
select the protocol (CalDAV or CardDAV), add the URL to the Radicale collections
and enter the credentials. After synchronization of the calendar resp.
addressbook items, you can manage them in Kontact.

#### Thunderbird

Add a new calendar on the network. Enter your username and the URL of the
Radicale server (e.g. `http://localhost:5232`). After asking for your password,
it will list the existing calendars.

##### Address books with CardBook add-on

Add a new address book on the network with CardDAV. Enter the URL of the
Radicale server (e.g. `http://localhost:5232`) and your username and password.
It will list your existing address books.

#### InfCloud, CalDavZAP and CardDavMATE

You can integrate InfCloud into Radicale's web interface with by simply
downloading the latest package from [InfCloud](https://www.inf-it.com/open-source/clients/infcloud/)
and extract the content into a folder named `infcloud` in `radicale/web/internal_data/`.

No further adjustments are required as content is adjusted on the fly (tested with 0.13.1).

See also [Wiki/Client InfCloud](https://github.com/Kozea/Radicale/wiki/Client-InfCloud).

#### Command line

This is not the recommended way of creating and managing your calendars and
address books. Use Radicale's web interface or a client with support for it
(e.g. **DAVx⁵**).

To create a new calendar run something like:

```bash
$ curl -u user -X MKCOL 'http://localhost:5232/user/calendar' --data \
'<?xml version="1.0" encoding="UTF-8" ?>
<create xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:I="http://apple.com/ns/ical/">
  <set>
    <prop>
      <resourcetype>
        <collection />
        <C:calendar />
      </resourcetype>
      <C:supported-calendar-component-set>
        <C:comp name="VEVENT" />
        <C:comp name="VJOURNAL" />
        <C:comp name="VTODO" />
      </C:supported-calendar-component-set>
      <displayname>Calendar</displayname>
      <C:calendar-description>Example calendar</C:calendar-description>
      <I:calendar-color>#ff0000ff</I:calendar-color>
    </prop>
  </set>
</create>'
```

To create a new address book run something like:

```bash
$ curl -u user -X MKCOL 'http://localhost:5232/user/addressbook' --data \
'<?xml version="1.0" encoding="UTF-8" ?>
<create xmlns="DAV:" xmlns:CR="urn:ietf:params:xml:ns:carddav">
  <set>
    <prop>
      <resourcetype>
        <collection />
        <CR:addressbook />
      </resourcetype>
      <displayname>Address book</displayname>
      <CR:addressbook-description>Example address book</CR:addressbook-description>
    </prop>
  </set>
</create>'
```

The collection `/USERNAME` will be created automatically, when the user
authenticates to Radicale for the first time. Clients with automatic discovery
of collections will only show calendars and address books that are direct
children of the path `/USERNAME/`.

Delete the collections by running something like:

```bash
curl -u user -X DELETE 'http://localhost:5232/user/calendar'
```

Note: requires config/option `permit_delete_collection = True`

### Authorization and Rights

This section describes the format of the rights file for the `from_file`
authentication backend. The configuration option `file` in the `rights`
section must point to the rights file.

The recommended rights method is `owner_only`. If access is granted
to calendars and address books outside the home directory of users
(that's `/USERNAME/`), clients will not detect these collections automatically,
and will not show them to the users.
This is only useful if you access calendars and address books directly via URL.

An example rights file:

```ini
# Allow reading root collection for authenticated users
[root]
user: .+
collection:
permissions: R

# Allow reading and writing principal collection (same as username)
[principal]
user: .+
collection: {user}
permissions: RW

# Allow reading and writing calendars and address books that are direct
# children of the principal collection
[calendars]
user: .+
collection: {user}/[^/]+
permissions: rw
```

The titles of the sections are ignored (but must be unique). The keys `user`
and `collection` contain regular expressions, that are matched against the
username and the path of the collection. Permissions from the first
matching section are used. If no section matches, access gets denied.

The username is empty for anonymous users. Therefore, the regex `.+` only
matches authenticated users and `.*` matches everyone (including anonymous
users).

The path of the collection is separated by `/` and has no leading or trailing
`/`. Therefore, the path of the root collection is empty.

In the `collection` regex you can use `{user}` and get groups from the `user`
regex with `{0}`, `{1}`, etc.

In consequence of the parameter substitution you have to write `{{` and `}}`
if you want to use regular curly braces in the `user` and `collection` regexes.

The following `permissions` are recognized:

* **R:** read collections (excluding address books and calendars)
* **r:** read address book and calendar collections
* **i:** subset of **r** that only allows direct access via HTTP method GET
  (CalDAV/CardDAV is susceptible to expensive search requests)
* **W:** write collections (excluding address books and calendars)
* **w:** write address book and calendar collections
* **D:** allow deleting a collection in case `permit_delete_collection=False` _(>= 3.3.0)_
* **d:** deny deleting a collection in case `permit_delete_collection=True` _(>= 3.3.0)_
* **O:** allow overwriting a collection in case `permit_overwrite_collection=False` _(>= 3.3.0)_
* **o:** deny overwriting a collection in case `permit_overwrite_collection=True` _(>= 3.3.0)_
* **T:** permit create of token-based sharing of collection in case `permit_create_token=False` _(>= 3.7.0)_
* **t:** deny create of token-based sharing of collection in case `permit_create_token=True` _(>= 3.7.0)_
* **M:** permit create of map-based sharing of collection in case `permit_create_map= False` _(>= 3.7.0)_
* **m:** deny create of map-based sharing of collection in case `permit_create_map=True` _(>= 3.7.0)_

### Storage

This document describes the layout and format of the file system storage,
the `multifilesystem` backend.

It is safe to access and manipulate the data by hand or with scripts.
Scripts can be invoked manually, periodically (e.g. using
[cron](https://manpages.debian.org/unstable/cron/cron.8.en.html)) or after each
change to the storage with the configuration option `hook` in the `storage`
section (e.g. [Versioning collections with Git](#versioning-collections-with-git)).

#### Layout

The file system comprises the following files and folders:
* `.Radicale.lock`: The lock file for locking the storage.
* `collection-root`: This folder contains all collections and items.

Each collection is represented by a folder. This folder may contain the file
`.Radicale.props` with all WebDAV properties of the collection encoded
as [JSON](https://en.wikipedia.org/wiki/JSON).

Each item in a calendar or address book collection is represented by
a file containing the item's iCalendar resp. vCard data.

All files and folders, whose names start with a dot but not with `.Radicale.`
(internal files) are ignored.

Syntax errors in any of the files will cause all requests accessing
the faulty data to fail. The logging output should contain the names of the
culprits.

Caches and sync-tokens are stored in the `.Radicale.cache` folder inside of
collections.
This folder may be created or modified, while the storage is locked for shared
access.
In theory, it should be safe to delete the folder. Caches will be recreated
automatically and clients will be told that their sync-token is not valid
anymore.

You may encounter files or folders that start with `.Radicale.tmp-`.
Radicale uses them for atomic creation and deletion of files and folders.
They should be deleted after requests are finished but it is possible that
they are left behind when Radicale or the computer crashes.
You can safely delete them.

#### Locking

When the data is accessed by hand or by an externally invoked script,
the storage must be locked. The storage can be locked for exclusive or
shared access. It prevents Radicale from reading or writing the file system.
The storage is locked with exclusive access while the `hook` runs.

##### Linux shell scripts

Use the
[flock](https://manpages.debian.org/unstable/util-linux/flock.1.en.html)
utility to acquire exclusive or shared locks for the commands you want to run
on Radicale's data.

```bash
# Exclusive lock for COMMAND
$ flock --exclusive /path/to/storage/.Radicale.lock COMMAND
# Shared lock for COMMAND
$ flock --shared /path/to/storage/.Radicale.lock COMMAND
```

##### Linux and MacOS

Use the
[flock](https://manpages.debian.org/unstable/manpages-dev/flock.2.en.html)
syscall. Python provides it in the
[fcntl](https://docs.python.org/3/library/fcntl.html#fcntl.flock) module.

##### Windows

Use
[LockFile](https://msdn.microsoft.com/en-us/library/windows/desktop/aa365202%28v=vs.85%29.aspx)
for exclusive access or
[LockFileEx](https://msdn.microsoft.com/en-us/library/windows/desktop/aa365203%28v=vs.85%29.aspx)
which also supports shared access. Setting `nNumberOfBytesToLockLow` to `1`
and `nNumberOfBytesToLockHigh` to `0` works.

#### Manually creating collections

To create a new collection, you need to create the corresponding folder in the
file system storage (e.g. `collection-root/user/calendar`).
To indicate to Radicale and clients that the collection is a calendar, you have to
create the file ``.Radicale.props`` with the following content in the folder:

```json
{"tag": "VCALENDAR"}
```

The calendar is now available at the URL path (e.g. ``/user/calendar``).
For address books ``.Radicale.props`` must contain:

```json
{"tag": "VADDRESSBOOK"}
```

Calendar and address book collections must not have any child collections.
Clients with automatic discovery of collections will only show calendars and
address books that are direct children of the path `/USERNAME/`.

Delete collections by deleting the corresponding folders.

### Logging overview

Radicale logs to `stderr`. The verbosity of the log output can be controlled
with `--debug` command line argument or the `level` configuration option in
the [logging](#logging) section.

### Architecture

Radicale is a small piece of software, but understanding it is not as
easy as it seems. But don't worry, reading this short section is enough to
understand what a CalDAV/CardDAV server is, and how Radicale's code is
organized.

#### Protocol overview

Here is a simple overview of the global architecture for reaching a calendar or
an address book through network:

| Part     | Layer                    | Protocol or Format                 |
|----------|--------------------------|------------------------------------|
| Server   | Calendar/Contact Storage | iCal/vCard                         |
| ''       | Calendar/Contact Server  | CalDAV/CardDAV Server              |
| Transfer | Network                  | CalDAV/CardDAV (HTTP + TLS)        |
| Client   | Calendar/Contact Client  | CalDAV/CardDAV Client              |
| ''       | GUI                      | Terminal, GTK, Web interface, etc. |

Radicale is **only the server part** of this architecture.

Please note:

* CalDAV and CardDAV are extension protocols of WebDAV,
* WebDAV is an extension of the HTTP protocol.

Radicale being a CalDAV/CardDAV server, can also be seen as a special WebDAV
and HTTP server.

Radicale is **not the client part** of this architecture. It means that
Radicale never draws calendars, address books, events and contacts on the
screen. It only stores them and give the possibility to share them online with
other people.

If you want to see or edit your events and your contacts, you have to use
another software called a client, that can be a "normal" applications with
icons and buttons, a terminal or another web application.

#### Code Architecture

The ``radicale`` package offers the following modules.

* `__init__`
  : Contains the entry point for WSGI.

* `__main__`
  : Provides the entry point for the ``radicale`` executable and
  includes the command line parser. It loads configuration files from
  the default (or specified) paths and starts the internal server.

* `app`
  : This is the core part of Radicale, with the code for the CalDAV/CardDAV
  server. The code managing the different HTTP requests according to the
  CalDAV/CardDAV specification can be found here.

* `auth`
  : Used for authenticating users based on username and password, mapping
  usernames to internal users and optionally retrieving credentials from
  the environment.

* `config`
  : Contains the code for managing configuration and loading settings from files.

* `ìtem`
  : Internal representation of address book and calendar entries. Based on
  [VObject](https://github.com/py-vobject/vobject/).

* `log`
  : The logger for Radicale based on the default Python logging module.

* `rights`
  : This module is used by Radicale to manage access rights to collections,
  address books and calendars.

* `server`
: The integrated HTTP server for standalone use.

* `storage`
  : This module contains the classes representing collections in Radicale and
  the code for storing and loading them in the filesystem.

* `web`
  : This module contains the web interface.

* `utils`
  : Contains general helper functions.

* `httputils`
  : Contains helper functions for working with HTTP.

* `pathutils`
  : Helper functions for working with paths and the filesystem.

* `xmlutils`
  : Helper functions for working with the XML part of CalDAV/CardDAV requests
  and responses. It's based on the ElementTree XML API.

### Plugins

Radicale can be extended by plugins for authentication, rights management and
storage. Plugins are **python** modules.

#### Getting started with plugin development

To get started we walk through the creation of a simple authentication
plugin, that accepts login attempts with a static password.

The easiest way to develop and install **python** modules is
[Distutils](https://docs.python.org/3/distutils/setupscript.html).
For a minimal setup create the file `setup.py` with the following content
in an empty folder:

```python
#!/usr/bin/env python3

from distutils.core import setup

setup(name="radicale_static_password_auth",
      packages=["radicale_static_password_auth"])
```

In the same folder create the sub-folder `radicale_static_password_auth`.
The folder must have the same name as specified in `packages` above.

Create the file `__init__.py` in the `radicale_static_password_auth` folder
with the following content:

```python
from radicale.auth import BaseAuth
from radicale.log import logger

PLUGIN_CONFIG_SCHEMA = {"auth": {
    "password": {"value": "", "type": str}}}


class Auth(BaseAuth):
    def __init__(self, configuration):
        super().__init__(configuration.copy(PLUGIN_CONFIG_SCHEMA))

    def _login(self, login, password):
        # Get password from configuration option
        static_password = self.configuration.get("auth", "password")
        # Check authentication
        logger.info("Login attempt by %r with password %r",
                    login, password)
        if password == static_password:
            return login
        return ""
```

Install the python module by running the following command in the same folder
as `setup.py`:

```bash
python3 -m pip install .
```

To make use this great creation in Radicale, set the configuration option
`type` in the `auth` section to `radicale_static_password_auth`:

```ini
[auth]
type = radicale_static_password_auth
password = secret
```

You can uninstall the module with:

```bash
python3 -m pip uninstall radicale_static_password_auth
```

#### Authentication plugins

This plugin type is used to check login credentials.
The module must contain a class `Auth` that extends
`radicale.auth.BaseAuth`. Take a look at the file `radicale/auth/__init__.py`
in Radicale's source code for more information.

#### Rights management plugins

This plugin type is used to check if a user has access to a path.
The module must contain a class `Rights` that extends
`radicale.rights.BaseRights`. Take a look at the file
`radicale/rights/__init__.py` in Radicale's source code for more information.

#### Web plugins

This plugin type is used to provide the web interface for Radicale.
The module must contain a class `Web` that extends
`radicale.web.BaseWeb`. Take a look at the file `radicale/web/__init__.py` in
Radicale's source code for more information.

#### Storage plugins

This plugin is used to store collections and items.
The module must contain a class `Storage` that extends
`radicale.storage.BaseStorage`. Take a look at the file
`radicale/storage/__init__.py` in Radicale's source code for more information.
