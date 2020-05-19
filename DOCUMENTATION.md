# Getting started

### About Radicale

Radicale is a small but powerful CalDAV (calendars, todo-lists) and CardDAV
(contacts) server, that:

  * Shares calendars through CalDAV, WebDAV and HTTP.
  * Shares contacts through CardDAV, WebDAV and HTTP.
  * Supports events, todos, journal entries and business cards.
  * Works out-of-the-box, no installation nor configuration required.
  * Can warn users on concurrent editing.
  * Can limit access by authentication.
  * Can secure connections.
  * Works with many CalDAV and CardDAV clients.
  * Is GPLv3-licensed free software.

### Installation

Radicale is really easy to install and works out-of-the-box.

```bash
$ python3 -m pip install --upgrade radicale
$ python3 -m radicale --config "" --storage-filesystem-folder=~/.var/lib/radicale/collections
```

When your server is launched, you can check that everything's OK by going
to http://localhost:5232/ with your browser!
You can login with any username and password.

Want more? Why don't you check our wonderful
[documentation](#documentation)?

### What's New?

Latest version of Radicale is 2.1.12,
released on May 19, 2020
([changelog](https://github.com/Kozea/Radicale/blob/2.1.12/NEWS.md)).

[Read latest news…](#news)

# Documentation

This documentation page is written for version 2.x.x. If you want to update
Radicale from 1.x.x to 2.x.x, please follow
our [migration guide](#documentation/migration-from-1xx-to-2xx). You can find on GitHub the
[documentation page for the 1.1.x versions](1.1.x.html).

### Install and Set Up

You're new to Radicale and you want to know how to use it? Welcome aboard!

- [What is Radicale?](#about)
- [A really simple 5-minute tutorial.](#documentation/tutorial)
- [A simple but solid setup.](#documentation/basic-setup)
- [Run behind a reverse proxy.](#documentation/reverse-proxy)
- [Run with a WSGI server.](#documentation/wsgi)
- [Track all changes to calendars and address books with Git.](#documentation/versioning)

### Use

- [Which clients are supported?](#documentation/clients)

### Configure

Now that you have Radicale running, let's see what we can configure to make it
fit your needs.

- [What can I configure?](#documentation/configuration)
- [Authentication & Rights.](#documentation/authentication-and-rights)
- [Storage.](#documentation/storage)
- [Logging.](#documentation/logging)

### Hack

Using is fun, but hacking is soooooooo coooooool. Radicale is a really small
and simple piece of code, it may be the perfect project to start hacking!

- [How does Radicale work?](#documentation/architecture)
- [Plugins.](#documentation/plugins)
- [Adding or fixing documentation.](#contribute)

## Tutorial

You want to try Radicale but only have 5 minutes free in your calendar? Let's
go right now! You won't have the best installation ever, but it will be enough
to play a little bit with Radicale.

When everything works, you can get a [client](#documentation/clients) and
start creating calendars and address books. The server **only** binds to
localhost (is **not** reachable over the network) and you can log in with any
user name and password. If Radicale fits your needs, it may be time for
[some basic configuration](#documentation/basic-setup).

Follow one of the chapters below depending on your operating system.

### Linux / \*BSD

First of all, make sure that **python** 3.3 or later (**python** ≥ 3.6 is
recommended) and **pip** are installed. On most distributions it should be
enough to install the package ``python3-pip``.

Then open a console and type:

```bash
# Run the following command as root or
# add the --user argument to only install for the current user
$ python3 -m pip install --upgrade radicale
$ python3 -m radicale --config "" --storage-filesystem-folder=~/.var/lib/radicale/collections
```

Victory! Open [http://localhost:5232/](http://localhost:5232/) in your browser!
You can login with any username and password.

### Windows

The first step is to install Python. Go to
[python.org](https://python.org) and download the latest version of Python 3.
Then run the installer.
On the first window of the installer, check the "Add Python to PATH" box and
click on "Install now". Wait a couple of minutes, it's done!

Launch a command prompt and type:

```powershell
C:\Users\User> python -m pip install --upgrade radicale
C:\Users\User> python -m radicale --config "" --storage-filesystem-folder=~/radicale/collections
```

If you are using PowerShell replace ``--config ""`` with ``--config '""'``.

Victory! Open [http://localhost:5232/](http://localhost:5232/) in your browser!
You can login with any username and password.

### MacOS

*To be written.*

## Basic Setup

Installation instructions can be found on the
[Tutorial](#documentation/tutorial) page.

### Configuration

Radicale tries to load configuration files from `/etc/radicale/config`,
`~/.config/radicale/config` and the `RADICALE_CONFIG` environment variable.
A custom path can be specified with the `--config /path/to/config` command
line argument.

You should create a new configuration file at the desired location.
(If the use of a configuration file is inconvenient, all options can be
passed via command line arguments.)

All configuration options are described in detail on the
[Configuration](#documentation/configuration) page.

### Authentication

In its default configuration Radicale doesn't check user names or passwords.
If the server is reachable over a network, you should change this.

First a `users` file with all user names and passwords must be created.
It can be stored in the same directory as the configuration file.

#### The secure way

The `users` file can be created and managed with
[htpasswd](https://httpd.apache.org/docs/current/programs/htpasswd.html):
```bash
# Create a new htpasswd file with the user "user1"
$ htpasswd -B -c /path/to/users user1
New password:
Re-type new password:
# Add another user
$ htpasswd -B /path/to/users user2
New password:
Re-type new password:
```
**bcrypt** is used to secure the passwords. Radicale requires additional
dependencies for this encryption method:
```bash
$ python3 -m pip install --upgrade radicale[bcrypt]
```

Authentication can be enabled with the following configuration:
```ini
[auth]
type = htpasswd
htpasswd_filename = /path/to/users
# encryption method used in the htpasswd file
htpasswd_encryption = bcrypt
```

#### The simple but insecure way

Create the `users` file by hand with lines containing the user name and
password separated by `:`. Example:

```htpasswd
user1:password1
user2:password2
```

Authentication can be enabled with the following configuration:
```ini
[auth]
type = htpasswd
htpasswd_filename = /path/to/users
# encryption method used in the htpasswd file
htpasswd_encryption = plain
```

### Addresses

The default configuration binds the server to localhost. It can't be reached
from other computers. This can be changed with the following configuration
options:

```ini
[server]
hosts = 0.0.0.0:5232
```

More addresses can be added (separated by commas).

### Storage

Data is stored in the folder `/var/lib/radicale/collections`. The path can
be changed with the following configuration:

```ini
[storage]
filesystem_folder = /path/to/storage
```

**Security:** The storage folder should not be readable by unauthorized users.
Otherwise, they can read the calendar data and lock the storage.
You can find OS dependent instructions in the **Running as a service** section.

### Limits

Radicale enforces limits on the maximum number of parallel connections,
the maximum file size (important for contacts with big photos) and the rate of
incorrect authentication attempts. Connections are terminated after a timeout.
The default values should be fine for most scenarios.

```ini
[server]
max_connections = 20
# 100 Megabyte
max_content_length = 100000000
# 30 seconds
timeout = 30

[auth]
# Average delay after failed login attempts in seconds
delay = 1
```

### Running as a service

The method to run Radicale as a service depends on your host operating system.
Follow one of the chapters below depending on your operating system and
requirements.

#### Linux with systemd as a user

Create the file `~/.config/systemd/user/radicale.service`:
```ini
[Unit]
Description=A simple CalDAV (calendar) and CardDAV (contact) server

[Service]
ExecStart=/usr/bin/env python3 -m radicale
Restart=on-failure

[Install]
WantedBy=default.target
```

Radicale will load the configuration file from `~/.config/radicale/config`.
You should set the configuration option `filesystem_folder` in the `storage`
section to something like `~/.var/lib/radicale/collections`.

To enable and manage the service run:
```bash
# Enable the service
$ systemctl --user enable radicale
# Start the service
$ systemctl --user start radicale
# Check the status of the service
$ systemctl --user status radicale
# View all log messages
$ journalctl --user --unit radicale.service
```

#### Linux with systemd system-wide

Create the **radicale** user and group for the Radicale service.
(Run `useradd --system --home-dir / --shell /sbin/nologin radicale` as root.)
The storage folder must be writable by **radicale**. (Run
`mkdir -p /var/lib/radicale/collections && chown -R radicale:radicale /var/lib/radicale/collections`
as root.)

**Security:** The storage should not be readable by others.
(Run `chmod -R o= /var/lib/radicale/collections` as root.)

Create the file `/etc/systemd/system/radicale.service`:
```ini
[Unit]
Description=A simple CalDAV (calendar) and CardDAV (contact) server
After=network.target
Requires=network.target

[Service]
ExecStart=/usr/bin/env python3 -m radicale
Restart=on-failure
User=radicale
# Deny other users access to the calendar data
UMask=0027
# Optional security settings
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
NoNewPrivileges=true
ReadWritePaths=/var/lib/radicale/collections

[Install]
WantedBy=multi-user.target
```
Radicale will load the configuration file from `/etc/radicale/config`.

To enable and manage the service run:
```bash
# Enable the service
$ systemctl enable radicale
# Start the service
$ systemctl start radicale
# Check the status of the service
$ systemctl status radicale
# View all log messages
$ journalctl --unit radicale.service
```

### MacOS with launchd

*To be written.*

### Classic daemonization

Set the configuration option `daemon` in the section `server` to `True`.
You may want to set the option `pid` to the path of a PID file.

After daemonization the server will not log anything. You have to configure
[Logging](#documentation/logging).

If you start Radicale now, it will initialize and fork into the background.
The main process exits, after the PID file is written.

**Security:** You can set the **umask** with `umask 0027` before you start the
daemon, to protect your calendar data and log files from other users.
Don't forget to set permissions of files that are already created!

### Windows with "NSSM - the Non-Sucking Service Manager"

First install [NSSM](https://nssm.cc/) and start `nssm install` in a command
prompt. Apply the following configuration:

* Service name: `Radicale`
* Application
  * Path: `C:\Path\To\Python\python.exe`
  * Arguments: `-m radicale --config C:\Path\To\Config`
* I/O redirection
  * Error: `C:\Path\To\Radicale.log`

**Security:** Be aware that the service runs in the local system account,
you might want to change this. Managing user accounts is beyond the scope of
this manual. Also make sure that the storage folder and log file is not readable
by unauthorized users.

The log file might grow very big over time, you can configure file rotation
in **NSSM** to prevent this.

The service is configured to start automatically when the computer starts.
To start the service manually open **Services** in **Computer Management** and
start the **Radicale** service.

## Reverse Proxy

When a reverse proxy is used, the path at which Radicale is available must
be provided via the `X-Script-Name` header. The proxy must remove the location
from the URL path that is forwarded to Radicale.

Example **nginx** configuration:
```nginx
location /radicale/ { # The trailing / is important!
    proxy_pass        http://localhost:5232/; # The / is important!
    proxy_set_header  X-Script-Name /radicale;
    proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_pass_header Authorization;
}
```

Example **Apache** configuration:
```apache
RewriteEngine On
RewriteRule ^/radicale$ /radicale/ [R,L]

<Location "/radicale/">
    ProxyPass        http://localhost:5232/ retry=0
    ProxyPassReverse http://localhost:5232/
    RequestHeader    set X-Script-Name /radicale/
</Location>
```

Be reminded that Radicale's default configuration enforces limits on the
maximum number of parallel connections, the maximum file size and the rate of
incorrect authentication attempts. Connections are terminated after a timeout.

### Manage user accounts with the reverse proxy

Set the configuration option `type` in the `auth` section to
`http_x_remote_user`.
Radicale uses the user name provided in the `X-Remote-User` HTTP header and
disables HTTP authentication.

Example **nginx** configuration:

```nginx
location /radicale/ {
    proxy_pass           http://localhost:5232/;
    proxy_set_header     X-Script-Name /radicale;
    proxy_set_header     X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header     X-Remote-User $remote_user;
    auth_basic           "Radicale - Password Required";
    auth_basic_user_file /etc/nginx/htpasswd;
}
```

Example **Apache** configuration:
```apache
RewriteEngine On
RewriteRule ^/radicale$ /radicale/ [R,L]

<Location "/radicale/">
    AuthType      Basic
    AuthName      "Radicale - Password Required"
    AuthUserFile  "/etc/radicale/htpasswd"
    Require       valid-user

    ProxyPass        http://localhost:5232/ retry=0
    ProxyPassReverse http://localhost:5232/
    RequestHeader    set X-Script-Name /radicale/
    RequestHeader    set X-Remote-User expr=%{REMOTE_USER}
</Location>
```

**Security:** Untrusted clients should not be able to access the Radicale
server directly. Otherwise, they can authenticate as any user.

### Secure connection between Radicale and the reverse proxy

SSL certificates can be used to encrypt and authenticate the connection between
Radicale and the reverse proxy. First you have to generate a certificate for
Radicale and a certificate for the reverse proxy. The following commands
generate self-signed certificates. You will be asked to enter additional
information about the certificate, the values don't matter and you can keep the
defaults.

```bash
$ openssl req -x509 -newkey rsa:4096 -keyout server_key.pem -out server_cert.pem -nodes -days 9999
$ openssl req -x509 -newkey rsa:4096 -keyout client_key.pem -out client_cert.pem -nodes -days 9999
```

Use the following configuration for Radicale:

```ini
[server]
ssl = True
certificate = /path/to/server_cert.pem
key = /path/to/server_key.pem
certificate_authority = /path/to/client_cert.pem
```

Example **nginx** configuration:

```nginx
location /radicale/ {
    proxy_pass https://localhost:5232/;
    ...
    # Place the files somewhere nginx is allowed to access (e.g. /etc/nginx/...).
    proxy_ssl_certificate         /path/to/client_cert.pem;
    proxy_ssl_certificate_key     /path/to/client_key.pem;
    proxy_ssl_trusted_certificate /path/to/server_cert.pem;
}
```

## WSGI

Radicale is compatible with the WSGI specification.

A configuration file can be set with the `RADICALE_CONFIG` environment variable,
otherwise no configuration file is loaded and the default configuration is used.

Be reminded that Radicale's default configuration enforces limits on the
maximum upload file size.

**Security:** The `None` authentication type disables all rights checking.
Don't use it with `REMOTE_USER`. Use `remote_user` instead.

Example **uWSGI** configuration:

```ini
[uwsgi]
http-socket = 127.0.0.1:5232
processes = 8
plugin = python3
module = radicale
env = RADICALE_CONFIG=/etc/radicale/config
```

Example **Gunicorn** configuration:

```bash
gunicorn --bind '127.0.0.1:5232' --workers 8 --env 'RADICALE_CONFIG=/etc/radicale/config' radicale
```

### Manage user accounts with the WSGI server

Set the configuration option `type` in the `auth` section to `remote_user`.
Radicale uses the user name provided by the WSGI server and disables
authentication over HTTP.

## Versioning

This page describes how to keep track of all changes to calendars and
address books with **git** (or any other version control system).

The repository must be initialized by running `git init` in the file
system folder. Internal files of Radicale can be excluded by creating the
file `.gitignore` with the following content:
```
.Radicale.cache
.Radicale.lock
.Radicale.tmp-*
```

The configuration option `hook` in the `storage` section must be set to
the following command:
```bash
git add -A && (git diff --cached --quiet || git commit -m "Changes by "%(user)s)
```

The command gets executed after every change to the storage and commits
the changes into the **git** repository.

## Clients

Radicale has been tested with:

  * [Android](https://android.com/) with
    [DAVx⁵](https://www.davx5.com/) (formerly DAVdroid)
  * [GNOME Calendar](https://wiki.gnome.org/Apps/Calendar),
    [Contacts](https://wiki.gnome.org/Apps/Contacts) and
    [Evolution](https://wiki.gnome.org/Apps/Evolution)
  * [Mozilla Thunderbird](https://www.mozilla.org/thunderbird/) with
    [CardBook](https://addons.mozilla.org/thunderbird/addon/cardbook/) and
    [Lightning](https://www.mozilla.org/projects/calendar/)
  * [InfCloud](https://www.inf-it.com/open-source/clients/infcloud/),
    [CalDavZAP](https://www.inf-it.com/open-source/clients/caldavzap/) and
    [CardDavMATE](https://www.inf-it.com/open-source/clients/carddavmate/)

Many clients do not support the creation of new calendars and address books.
You can use Radicale's web interface
(e.g. [http://localhost:5232](http://localhost:5232)) to create and manage
collections.

In some clients you can just enter the URL of the Radicale server
(e.g. `http://localhost:5232`) and your user name. In others, you have to
enter the URL of the collection directly
(e.g. `http://localhost:5232/user/calendar`).

### DAVx⁵

Enter the URL of the Radicale server (e.g. `http://localhost:5232`) and your
user name. DAVx⁵ will show all existing calendars and address books and you
can create new.

### GNOME Calendar, Contacts and Evolution

**GNOME Calendar** and **Contacts** do not support adding WebDAV calendars
and address books directly, but you can add them in **Evolution**.

In **Evolution** add a new calendar and address book respectively with WebDAV.
Enter the URL of the Radicale server (e.g. `http://localhost:5232`) and your
user name. Clicking on the search button will list the existing calendars and
address books.

### Thunderbird
#### CardBook

Add a new address book on the network with CardDAV. You have to enter the full
URL of the collection (e.g. `http://localhost:5232/user/addressbook`) and
your user name.

#### Lightning

Add a new calendar on the network with `CalDAV`. (Don't use `iCalendar (ICS)`!)
You have to enter the full URL of the collection (e.g.
`http://localhost:5232/user/calendar`). If you want to add calendars from
different users on the same server, you can specify the user name in the URL
(e.g. `http://user@localhost...`)

### InfCloud, CalDavZAP and CardDavMATE

You can integrate InfCloud into Radicale's web interface with
[RadicaleInfCloud](https://github.com/Unrud/RadicaleInfCloud). No additional
configuration is required.

Set the URL of the Radicale server in ``config.js``. If **InfCloud** is not
hosted on the same server and port as Radicale, the browser will deny access to
the Radicale server, because of the
[same-origin policy](https://en.wikipedia.org/wiki/Same-origin_policy).
You have to add additional HTTP header in the `headers` section of Radicale's
configuration. The documentation of **InfCloud** has more details on this.

### Manual creation of calendars and address books

This is not the recommended way of creating and managing your calendars and
address books. Use Radicale's web interface or a client with support for it
(e.g. **DAVx⁵**).

#### Direct editing of the storage

To create a new collection, you have to create the corresponding folder in the
file system storage (e.g. `collection-root/user/calendar`).
To tell Radicale and clients that the collection is a calendar, you have to
create the file ``.Radicale.props`` with the following content in the folder:

```json
{"tag": "VCALENDAR"}
```

The calendar is now available at the URL path ``/user/calendar``.
For address books the file must contain:

```json
{"tag": "VADDRESSBOOK"}
```

Calendar and address book collections must not have any child collections.
Clients with automatic discovery of collections will only show calendars and
addressbooks that are direct children of the path `/USERNAME/`.

Delete collections by deleting the corresponding folders.

#### HTTP requests with curl

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
$ curl -u user -X DELETE 'http://localhost:5232/user/calendar'
```

## Configuration

Radicale can be configured with a configuration file or with
command line arguments.

An example configuration file looks like:
```ini
[server]
# Bind all addresses
hosts = 0.0.0.0:5232

[auth]
type = htpasswd
htpasswd_filename = /path/to/users
htpasswd_encryption = bcrypt
[storage]
filesystem_folder = ~/.var/lib/radicale/collections
```

Radicale tries to load configuration files from `/etc/radicale/config`,
`~/.config/radicale/config` and the `RADICALE_CONFIG` environment variable.
This behaviour can be overwritten by specifying a path with the
`--config /path/to/config` command line argument.

The same example configuration via command line arguments looks like:
```bash
python3 -m radicale --config "" --server-hosts 0.0.0.0:5232 --auth-type htpasswd --htpasswd-filename /path/to/htpasswd --htpasswd-encryption bcrypt
```

The `--config ""` argument is required to stop Radicale from trying
to load configuration files. Run `python3 -m radicale --help` for more information.

In the following, all configuration categories and options are described.

### server

Most configuration options in this category are only relevant in standalone
mode. All options beside `max_content_length` and `realm` are ignored,
when Radicale runs via WSGI.

#### hosts

A comma separated list of addresses that the server will bind to.

Default: `127.0.0.1:5232`

#### daemon

Daemonize the Radicale process. It does not reset the umask.

Default: `False`

#### pid

If daemon mode is enabled, Radicale will write its PID to this file.

Default:

#### max_connections

The maximum number of parallel connections. Set to `0` to disable the limit.

Default: `20`

#### max_content_length

The maximum size of the request body. (bytes)

Default: `100000000`

#### timeout

Socket timeout. (seconds)

Default: `30`

#### ssl

Enable transport layer encryption.

Default: `False`

#### certificate

Path of the SSL certifcate.

Default: `/etc/ssl/radicale.cert.pem`

#### key

Path to the private key for SSL. Only effective if `ssl` is enabled.

Default: `/etc/ssl/radicale.key.pem`

#### certificate_authority

Path to the CA certificate for validating client certificates. This can be used
to secure TCP traffic between Radicale and a reverse proxy. If you want to
authenticate users with client-side certificates, you also have to write an
authentication plugin that extracts the user name from the certifcate.

Default:

#### protocol

SSL protocol used. See python's ssl module for available values.

Default: `PROTOCOL_TLSv1_2`

#### ciphers

Available ciphers for SSL. See python's ssl module for available ciphers.

Default:

#### dns_lookup

Reverse DNS to resolve client address in logs.

Default: `True`

#### realm

Message displayed in the client when a password is needed.

Default: `Radicale - Password Required`

### encoding
#### request

Encoding for responding requests.

Default: `utf-8`

#### stock

Encoding for storing local collections

Default: `utf-8`

### auth
#### type

The method to verify usernames and passwords.

Available backends:

`None`
: Just allows all usernames and passwords. It also disables rights checking.

`htpasswd`
: Use an [Apache htpasswd file](https://httpd.apache.org/docs/current/programs/htpasswd.html) to store
  usernames and passwords.

`remote_user`
: Takes the user name from the `REMOTE_USER` environment variable and disables
  HTTP authentication. This can be used to provide the user name from a WSGI
  server.

`http_x_remote_user`
: Takes the user name from the `X-Remote-User` HTTP header and disables HTTP
  authentication. This can be used to provide the user name from a reverse
  proxy.

Default: `None`

#### htpasswd_filename

Path to the htpasswd file.

Default:

#### htpasswd_encryption

The encryption method that is used in the htpasswd file. Use the
[htpasswd](https://httpd.apache.org/docs/current/programs/htpasswd.html)
or similar to generate this files.

Available methods:

`plain`
: Passwords are stored in plaintext. This is obviously not secure!
  The htpasswd file for this can be created by hand and looks like:
  ```htpasswd
  user1:password1
  user2:password2
  ```

`bcrypt`
: This uses a modified version of the Blowfish stream cipher. It's very secure.
  The **passlib** python module is required for this. Additionally you may need
  one of the following python modules: **bcrypt**, **py-bcrypt** or **bcryptor**.

`md5`
: This uses an iterated md5 digest of the password with a salt.
  The **passlib** python module is required for this.

`sha1`
: Passwords are stored as SHA1 hashes. It's insecure!

`ssha`
: Passwords are stored as salted SHA1 hashes. It's insecure!

`crypt`
: This uses UNIX
  [crypt(3)](https://manpages.debian.org/unstable/manpages-dev/crypt.3.en.html).
  It's insecure!

Default: `bcrypt`

#### delay

Average delay after failed login attempts in seconds.

Default: `1`

### rights
#### type

The backend that is used to check the access rights of collections.

The recommended backend is `owner_only`. If access to calendars
and address books outside of the home directory of users (that's `/USERNAME/`)
is granted, clients won't detect these collections and will not show them to
the user. Choosing any other method is only useful if you access calendars and
address books directly via URL.

Available backends:

`None`
: Everyone can read and write everything.

`authenticated`
: Authenticated users can read and write everything.

`owner_only`
: Authenticated users can read and write their own collections under the path
  */USERNAME/*.

`owner_write`
: Authenticated users can read everything and write their own collections under
  the path */USERNAME/*.

`from_file`
: Load the rules from a file.

Default: `owner_only`

#### file

File for the rights backend `from_file`.  See the
[Rights](#documentation/authentication-and-rights) page.

### storage
#### type

The backend that is used to store data.

Available backends:

`multifilesystem`
: Stores the data in the filesystem.

Default: `multifilesystem`

#### filesystem_folder

Folder for storing local collections, created if not present.

Default: `/var/lib/radicale/collections`

#### filesystem_locking

Lock the storage. This must be disabled if locking is not supported by the
underlying file system. Never start multiple instances of Radicale or edit the
storage externally while Radicale is running if disabled.

Default: `True`

#### max_sync_token_age

Delete sync-token that are older than the specified time. (seconds)

Default: `2592000`

#### filesystem_fsync

Sync all changes to disk during requests. (This can impair performance.)
Disabling it increases the risk of data loss, when the system crashes or
power fails!

Default: `True`

#### hook

Command that is run after changes to storage. Take a look at the
[Versioning](#documentation/versioning) page for an example.

Default:

### web
#### type

The backend that provides the web interface of Radicale.

Available backends:

`none`
: Just shows the message "Radicale works!".

`internal`
: Allows creation and management of address books and calendars.

Default: `internal`

### logging
#### debug

Set the default logging level to debug.

Default: `False`

#### full_environment

Log all environment variables (including those set in the shell).

Default: `False`

#### mask_passwords

Don't include passwords in logs.

Default: `True`

#### config

Logging configuration file. See the [Logging](#documentation/logging) page.

Default:

### headers

In this section additional HTTP headers that are sent to clients can be
specified.

An example to relax the same-origin policy:
```ini
Access-Control-Allow-Origin = *
```

## Authentication and Rights

This page describes the format of the rights file for the `from_file`
authentication backend. The configuration option `file` in the `rights`
section must point to the rights file.

The recommended rights method is `owner_only`. If access to calendars
and address books outside of the home directory of users (that's `/USERNAME/`)
is granted, clients won't detect these collections and will not show them to
the user.
This is only useful if you access calendars and address books directly via URL.

An example rights file:
```ini
# The user "admin" can read and write any collection.
[admin]
user = admin
collection = .*
permission = rw

# Block access for the user "user" to everything.
[block]
user = user
collection = .*
permission =

# Authenticated users can read and write their own collections.
[owner-write]
user = .+
collection = %(login)s(/.*)?
permission = rw

# Everyone can read the root collection
[read]
user = .*
collection =
permission = r
```

The titles of the sections are ignored (but must be unique). The keys `user`
and `collection` contain regular expressions, that are matched against the
user name and the path of the collection. Permissions from the first
matching section are used. If no section matches, access gets denied.

The user name is empty for anonymous users. Therefore, the regex `.+` only
matches authenticated users and `.*` matches everyone (including anonymous
users).

The path of the collection is separated by `/` and has no leading or trailing
`/`. Therefore, the path of the root collection is empty.

`%(login)s` gets replaced by the user name and `%(path)s` by the path of
the collection. You can also get groups from the `user` regex in the
`collection` regex with `{0}`, `{1}`, etc.

## Storage

This document describes the layout and format of the file system storage
(`multifilesystem` backend).

It's safe to access and manipulate the data by hand or with scripts.
Scripts can be invoked manually, periodically (e.g. with
[cron](https://manpages.debian.org/unstable/cron/cron.8.en.html)) or after each
change to the storage with the configuration option `hook` in the `storage`
section (e.g. [Git Versioning](#documentation/versioning)).

### Layout

The file system contains the following files and folders:

  * `.Radicale.lock`: The lock file for locking the storage.
  * `collection-root`: This folder contains all collections and items.

A collection is represented by a folder. This folder may contain the file
`.Radicale.props` with all WebDAV properties of the collection encoded
as [JSON](https://en.wikipedia.org/wiki/JSON).

An item is represented by a file containing the iCalendar data.

All files and folders, whose names start with a dot but not `.Radicale.`
(internal files) are ignored.

If you introduce syntax errors in any of the files, all requests that access
the faulty data will fail. The logging output should contain the names of the
culprits.

Future releases of Radicale 2.x.x will store caches and sync-tokens in the
`.Radicale.cache` folder inside of collections.
This folder may be created or modified, while the storage is locked for shared
access.
In theory, it should be safe to delete the folder. Caches will be recreated
automatically and clients will be told that their sync-token isn't valid
anymore.

You may encounter files or folders that start with `.Radicale.tmp-`.
Radicale uses them for atomic creation and deletion of files and folders.
They should be deleted after requests are finished but it's possible that
they are left behind when Radicale or the computer crashes.
It's safe to delete them.

### Locking

When the data is accessed by hand or by an externally invoked script,
the storage must be locked. The storage can be locked for exclusive or
shared access. It prevents Radicale from reading or writing the file system.
The storage is locked with exclusive access while the `hook` runs.

#### Linux shell scripts

Use the
[flock](https://manpages.debian.org/unstable/util-linux/flock.1.en.html)
utility.

```bash
# Exclusive
$ flock --exclusive /path/to/storage/.Radicale.lock COMMAND
# Shared
$ flock --shared /path/to/storage/.Radicale.lock COMMAND
```

#### Linux and MacOS

Use the
[flock](https://manpages.debian.org/unstable/manpages-dev/flock.2.en.html)
syscall. Python provides it in the
[fcntl](https://docs.python.org/3/library/fcntl.html#fcntl.flock) module.

#### Windows

Use
[LockFile](https://msdn.microsoft.com/en-us/library/windows/desktop/aa365202%28v=vs.85%29.aspx)
for exclusive access or
[LockFileEx](https://msdn.microsoft.com/en-us/library/windows/desktop/aa365203%28v=vs.85%29.aspx)
which also supports shared access. Setting `nNumberOfBytesToLockLow` to `1`
and `nNumberOfBytesToLockHigh` to `0` works.

## Logging

Radicale logs to `stderr`. The verbosity of the log output can be controlled
with `--debug` command line argument or the `debug` configuration option in
the `logging` section.

This is the recommended configuration for use with modern init systems
(like **systemd**) or if you just test Radicale in a terminal.

You can configure Radicale to write its logging output to files (and even
rotate them).
This is useful if the process daemonizes or if your chosen method of running
Radicale doesn't handle logging output.

A logging configuration file can be specified in the `config` configuration
option in the `logging` section. The file format is explained in the
[Python Logging Module](https://docs.python.org/3/library/logging.config.html#configuration-file-format).

### Logging to a file

An example configuration to write the log output to the file `/var/log/radicale/log`:
```ini
[loggers]
keys = root

[handlers]
keys = file

[formatters]
keys = full

[logger_root]
# Change this to DEBUG or INFO for higher verbosity.
level = WARNING
handlers = file

[handler_file]
class = FileHandler
# Specify the output file here.
args = ('/var/log/radicale/log',)
formatter = full

[formatter_full]
format = %(asctime)s - [%(thread)x] %(levelname)s: %(message)s
```

You can specify multiple **logger**, **handler** and **formatter** if you want
to have multiple simultaneous log outputs.

The parent folder of the log files must exist and must be writable by Radicale.

**Security:** The log files should not be readable by unauthorized users. Set
permissions accordingly.

#### Timed rotation of disk log files

An example **handler** configuration to write the log output to the file `/var/log/radicale/log` and rotate it.
Replace the section `handler_file` from the file logging example:
```ini
[handler_file]
class = handlers.TimedRotatingFileHandler
# Specify the output file and parameter for rotation here.
# See https://docs.python.org/3/library/logging.handlers.html#logging.handlers.TimedRotatingFileHandler
# Example: rollover at midnight and keep 7 files (means one week)
args = ('/var/log/radicale/log', 'midnight', 1, 7)
formatter = full
```

#### Rotation of disk log files based on size

An example **handler** configuration to write the log output to the file `/var/log/radicale/log` and rotate it .
Replace the section `handle_file` from the file logging example:
```ini
[handler_file]
class = handlers.RotatingFileHandler
# Specify the output file and parameter for rotation here.
# See https://docs.python.org/3/library/logging.handlers.html#logging.handlers.RotatingFileHandler
# Example: rollover at 100000 kB and keep 10 files (means 1 MB)
args = ('/var/log/radicale/log', 'a', 100000, 10)
formatter = full
```

## Architecture

Radicale is a really small piece of software, but understanding it is not as
easy as it seems. But don't worry, reading this short page is enough to
understand what a CalDAV/CardDAV server is, and how Radicale's code is
organized.

### General Architecture

Here is a simple overview of the global architecture for reaching a calendar or
an address book through network:

<table>
  <thead>
    <tr>
      <th>Part</th>
      <th>Layer</th>
      <th>Protocol or Format</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td rowspan="2">Server</td>
      <td>Calendar/Contact Storage</td>
      <td>iCal/vCard</td>
    </tr>
    <tr>
      <td>Calendar/Contact Server</td>
      <td>CalDAV/CardDAV Server</td>
    </tr>
    <tr>
      <td>Transfer</td>
      <td>Network</td>
      <td>CalDAV/CardDAV (HTTP + TLS)</td>
    </tr>
    <tr>
      <td rowspan="2">Client</td>
      <td>Calendar/Contact Client</td>
      <td>CalDAV/CardDAV Client</td>
    </tr>
    <tr>
      <td>GUI</td>
      <td>Terminal, GTK, Web interface, etc.</td>
    </tr>
  </tbody>
</table>

Radicale is **only the server part** of this architecture.

Please note that:

- CalDAV and CardDAV are superset protocols of WebDAV,
- WebDAV is a superset protocol of HTTP.

Radicale being a CalDAV/CardDAV server, it also can be seen as a special WebDAV
and HTTP server.

Radicale is **not the client part** of this architecture. It means that
Radicale never draws calendars, address books, events and contacts on the
screen. It only stores them and give the possibility to share them online with
other people.

If you want to see or edit your events and your contacts, you have to use
another software called a client, that can be a "normal" applications with
icons and buttons, a terminal or another web application.

### Code Architecture

The ``radicale`` package offers 9 modules.

`__main__`
: The main module provides a simple function called run. Its main work is to
  read the configuration from the configuration file and from the options given
  in the command line; then it creates a server, according to the configuration.

`__init__`
: This is the core part of the module, with the code for the CalDAV/CardDAV
  server. The server inherits from a WSGIServer server class, which relies on
  the default HTTP server class given by Python. The code managing the
  different HTTP requests according to the CalDAV/CardDAV normalization is
  written here.

`config`
: This part gives a dict-like access to the server configuration, read from the
  configuration file. The configuration can be altered when launching the
  executable with some command line options.

`xmlutils`
: The functions defined in this module are mainly called by the CalDAV/CardDAV
  server class to read the XML part of the request, read or alter the
  calendars, and create the XML part of the response. The main part of this
  code relies on ElementTree.

`log`
: The start function provided by this module starts a logging mechanism based
  on the default Python logging module. Logging options can be stored in a
  logging configuration file.

`auth`
: This module provides a default authentication manager equivalent to Apache's
  htpasswd. Login + password couples are stored in a file and used to
  authenticate users. Passwords can be encrypted using various methods. Other
  authentication methods can inherit from the base class in this file and be
  provided as plugins.

`rights`
: This module is a set of Access Control Lists, a set of methods used by
  Radicale to manage rights to access the calendars. When the CalDAV/CardDAV
  server is launched, an Access Control List is chosen in the set, according to
  the configuration. The HTTP requests are then filtered to restrict the access
  depending on who is authenticated. Other configurations can be written using
  regex-based rules. Other rights managers can also inherit from the base class
  in this file and be provided as plugins.

`storage`
: In this module are written the classes representing collections and items in
  Radicale, and the class storing these collections and items in your
  filesystem. Other storage classes can inherit from the base class in this
  file and be provided as plugins.

`web`
: This module contains the web interface.

## Plugins

Radicale can be extended by plugins for authentication, rights management and
storage. Plugins are **python** modules.

### Getting started

To get started we walk through the creation of a simple authentication
plugin, that accepts login attempts if the username and password are equal.

The easiest way to develop and install **python** modules is
[Distutils](https://docs.python.org/3/distutils/setupscript.html).
For a minimal setup create the file `setup.py` with the following content
in an empty folder:

```python
#!/usr/bin/env python3

from distutils.core import setup

setup(name="radicale_silly_auth", packages=["radicale_silly_auth"])
```

In the same folder create the sub-folder `radicale_silly_auth`. The folder
must have the same name as specified in `packages` above.

Create the file `__init__.py` in the `radicale_silly_auth` folder with the
following content:

```python
from radicale.auth import BaseAuth


class Auth(BaseAuth):
    def is_authenticated(self, user, password):
        # Example custom configuration option
        foo = ""
        if self.configuration.has_option("auth", "foo"):
            foo = self.configuration.get("auth", "foo")
        self.logger.info("Configuration option %r is %r", "foo", foo)

        # Check authentication
        self.logger.info("Login attempt by %r with password %r",
                         user, password)
        return user == password
```

Install the python module by running the following command in the same folder
as `setup.py`:
```bash
python3 -m pip install --upgrade .
```

To make use this great creation in Radicale, set the configuration option
`type` in the `auth` section to `radicale_silly_auth`:

```ini
[auth]
type = radicale_silly_auth
foo = bar
```

You can uninstall the module with:
```bash
python3 -m pip uninstall radicale_silly_auth
```

### Authentication plugins

This plugin type is used to check login credentials.
The module must contain a class `Auth` that extends
`radicale.auth.BaseAuth`. Take a look at the file `radicale/auth.py` in
Radicale's source code for more information.

### Rights management plugins

This plugin type is used to check if a user has access to a path.
The module must contain a class `Rights` that extends
`radicale.rights.BaseRights`. Take a look at the file `radicale/rights.py` in
Radicale's source code for more information.

### Web plugins

This plugin type is used to provide the web interface for Radicale.
The module must contain a class `Web` that extends
`radicale.web.BaseWeb`. Take a look at the file `radicale/web.py` in
Radicale's source code for more information.

### Storage plugins

This plugin is used to store collections and items.
The module must contain a class `Collection` that extends
`radicale.storage.BaseCollection`. Take a look at the file `radicale/storage.py`
in Radicale's source code for more information.

## Migration from 1.x.x to 2.x.x
### Why a Migration?

Radicale 2.x.x is different from 1.x.x, here's everything you need to know about
this! **Please read this page carefully if you want to update Radicale.**

You'll also find extra information
in [issue #372](https://github.com/Kozea/Radicale/issues/372).

### Python 3 Only

Radicale 2.x.x works with Python >= 3.3, and **doesn't work anymore with
Python 2**.

(No, Python 3.3 is not new, it's been released more than 4 years ago.
Debian stable provides Python 3.4.)

### Dependencies

Radicale now depends on [VObject](https://eventable.github.io/vobject/), a
"full-featured Python package for parsing and creating iCalendar and vCard
files". That's the price to pay to correctly read crazy iCalendar files and
**support date-based filters, even on recurring events**.

### Storage

Calendars and address books are stored in a different way between 1.x.x and 2.x.x
versions. **Launching 2.x.x without migrating your collections first will not
work, Radicale won't be able to read your previous data.**

There's now only one way to store data in Radicale: collections are stored as
folders and events / contacts are stored in files. This new storage is close to
the `multifilesystem`, but **it's now thread-safe, with atomic writes and file
locks**. Other storage types can be used by creating
[plugins](#documentation/plugins).

To migrate data to Radicale 2.x.x the command line argument
``--export-storage`` was added to Radicale 1.1.x.
Start Radicale 1.x.x as you would normally do, but add the argument
``--export-storage path/to/empty/folder``. Radicale will export the storage
into the specified folder. This folder can be directly used with the
default storage backend of Radicale 2.x.x.

If you import big calendars or address books into Radicale 2.x.x the first
request might take a long time, because it has to initialize its internal
caches. Clients can time out, subsequent requests will be much faster.

You can check the imported storage for errors by starting Radicale >= 2.1.5
with the ``--verify-storage`` argument.

You can install version 1.1.6 with:

```bash
$ python3 -m pip install --upgrade radicale==1.1.6
```

### Authentication

**Radicale 2.x.x only provides htpasswd authentication out-of-the-box.** Other
authentication methods can be added by creating or using
[plugins](#documentation/plugins).

### Rights

In Radicale 2.x.x, rights are managed using regex-based rules based on the
login of the authenticated user and the URL of the resource. Default
configurations are built in for common cases, you'll find more about this on
the [Authentication & Rights](#documentation/authentication-and-rights) page.

Other rights managers can be added by creating
[plugins](#documentation/plugins).

### Versioning

Support for versioning with **git** was removed from Radicale 2.x.x.
Instead, the configuration option ``hook`` in the ``storage`` section was added,
the [Collection Versioning](#documentation/versioning) page explains its
usage for version control.

# Contribute

### Chat with Us on IRC

Want to say something? Join our IRC room: `##kozea` on Freenode.

### Report Bugs

Found a bug? Want a new feature? Report a new issue on the
[Radicale bug-tracker](https://github.com/Kozea/Radicale/issues).

### Hack

Interested in hacking? Feel free to clone the
[git repository on Github](https://github.com/Kozea/Radicale) if you want to
add new features, fix bugs or update the documentation.

### Documentation

To change or complement the documentation create a pull request to
[DOCUMENTATION.md](https://github.com/Kozea/Radicale/blob/master/DOCUMENTATION.md).

# Download

### PyPI

Radicale is [available on PyPI](https://pypi.python.org/pypi/Radicale/). To
install, just type as superuser:

    $ python3 -m pip install --upgrade radicale

### Git Repository

If you want the development version of Radicale, take a look at the
[git repository on GitHub](https://github.com/Kozea/Radicale/), or install it
directly with:

    $ python3 -m pip install --upgrade git+https://github.com/Kozea/Radicale

You can also download the content of the repository as an
[archive](https://github.com/Kozea/Radicale/tarball/master).

### Source Packages

You can download the Radicale package for each release:

- [**2.1.12 - Wild Radish**](https://api.github.com/repos/Kozea/Radicale/tarball/2.1.12)
- [**2.1.11 - Wild Radish**](https://api.github.com/repos/Kozea/Radicale/tarball/2.1.11)
- [**2.1.10 - Wild Radish**](https://api.github.com/repos/Kozea/Radicale/tarball/2.1.10)
- [**2.1.9 - Wild Radish**](https://api.github.com/repos/Kozea/Radicale/tarball/2.1.9)
- [**2.1.8 - Wild Radish**](https://api.github.com/repos/Kozea/Radicale/tarball/2.1.8)
- [**2.1.7 - Wild Radish**](https://api.github.com/repos/Kozea/Radicale/tarball/2.1.7)
- [**2.1.6 - Wild Radish**](https://api.github.com/repos/Kozea/Radicale/tarball/2.1.6)
- [**2.1.5 - Wild Radish**](https://api.github.com/repos/Kozea/Radicale/tarball/2.1.5)
- [**2.1.4 - Wild Radish**](https://api.github.com/repos/Kozea/Radicale/tarball/2.1.4)
- [**2.1.3 - Wild Radish**](https://api.github.com/repos/Kozea/Radicale/tarball/2.1.3)
- [**2.1.2 - Wild Radish**](https://api.github.com/repos/Kozea/Radicale/tarball/2.1.2)
- [**1.1.6 - Sixth Law of Nature**](https://api.github.com/repos/Kozea/Radicale/tarball/1.1.6)
- [**2.1.1 - Wild Radish Again**](https://api.github.com/repos/Kozea/Radicale/tarball/2.1.1)
- [**2.1.0 - Wild Radish**](https://api.github.com/repos/Kozea/Radicale/tarball/2.1.0)
- [**1.1.4 - Fifth Law of Nature**](https://api.github.com/repos/Kozea/Radicale/tarball/1.1.4)
- [2.1.0rc3](https://api.github.com/repos/Kozea/Radicale/tarball/2.1.0rc3)
- [2.1.0rc2](https://api.github.com/repos/Kozea/Radicale/tarball/2.1.0rc2)
- [2.1.0rc1](https://api.github.com/repos/Kozea/Radicale/tarball/2.1.0rc1)
- [**2.0.0 - Little Big Radish**](https://api.github.com/repos/Kozea/Radicale/tarball/2.0.0)
- [**1.1.3 - Fourth Law of Nature**](https://api.github.com/repos/Kozea/Radicale/tarball/1.1.3)
- [2.0.0rc2](https://api.github.com/repos/Kozea/Radicale/tarball/2.0.0rc2)
- [**1.1.2 - Third Law of Nature**](https://api.github.com/repos/Kozea/Radicale/tarball/1.1.2)
- [2.0.0rc1](https://api.github.com/repos/Kozea/Radicale/tarball/2.0.0rc1)
- [**1.1.1 - Second Law of Nature**](https://api.github.com/repos/Kozea/Radicale/tarball/1.1.1)
- [**1.1 - Law of Nature**](https://api.github.com/repos/Kozea/Radicale/tarball/1.1)
- [**1.0.1 - Sunflower Again**](https://api.github.com/repos/Kozea/Radicale/tarball/1.0.1)
- [**1.0 - Sunflower**](https://api.github.com/repos/Kozea/Radicale/tarball/1.0)

### Linux Distribution Packages

Radicale has been packaged for:

- [ArchLinux](https://www.archlinux.org/packages/community/any/radicale/) by
  David Runge
- [Debian](http://packages.debian.org/radicale) by Jonas Smedegaard
- [Gentoo](https://packages.gentoo.org/packages/www-apps/radicale)
  by René Neumann, Maxim Koltsov and Manuel Rüger
- [Fedora](https://admin.fedoraproject.org/pkgdb/package/radicale/) by Jorti
- [Mageia](http://madb.mageia.org/package/show/application/0/name/radicale) by
  Jani Välimaa
- [OpenBSD](http://openports.se/productivity/radicale) by Sergey Bronnikov,
  Stuart Henderson and Ian Darwin
- [openSUSE](http://software.opensuse.org/package/Radicale?search_term=radicale)
  by Ákos Szőts and Rueckert
- [PyPM](http://code.activestate.com/pypm/radicale/)
- [Slackware](http://schoepfer.info/slackware.xhtml#packages-network) by
  Johannes Schöpfer
- [Trisquel](http://packages.trisquel.info/search?searchon=names&keywords=radicale)
- [Ubuntu](http://packages.ubuntu.com/radicale) by the MOTU and Jonas
  Smedegaard

Radicale is also
[available on Cloudron](https://cloudron.io/button.html?app=org.radicale.cloudronapp)
and has a Dockerfile.

If you are interested in creating packages for other Linux distributions, read
the ["Contribute" page](#contribute).

# About

### Main Goals

Radicale is a complete calendar and contact storing and manipulating
solution. It can store multiple calendars and multiple address books.

Calendar and contact manipulation is available from both local and distant
accesses, possibly limited through authentication policies.

It aims to be a lightweight solution, easy to use, easy to install, easy to
configure. As a consequence, it requires few software dependencies and is
pre-configured to work out-of-the-box.

Radicale is written in Python. It runs on most of the UNIX-like platforms
(Linux, \*BSD, macOS) and Windows. It is free and open-source software.

### What Radicale Will Never Be

Radicale is a server, not a client. No interfaces will be created to work with
the server, as it is a really (really really) much more difficult task.

CalDAV and CardDAV are not perfect protocols. We think that their main problem
is their complexity, that is why we decided not to implement the whole standard
but just enough to understand some of its client-side implementations.

CalDAV and CardDAV are the best open standards available and they are quite
widely used by both clients and servers. We decided to use it, and we will not
use another one.

### Technical Choices

Important global development choices have been decided before writing
code. They are very useful to understand why the Radicale Project is different
from other CalDAV and CardDAV servers, and why features are included or not in
the code.

#### Oriented to Calendar and Contact User Agents

Calendar and contact servers work with calendar and contact clients, using a
defined protocol. CalDAV and CardDAV are good protocols, covering lots of
features and use cases, but it is quite hard to implement fully.

Some calendar servers have been created to follow the CalDAV and CardDAV RFCs
as much as possible: [Davical](http://www.davical.org/),
[Baïkal](http://sabre.io/baikal/) and
[Darwin Calendar Server](http://trac.calendarserver.org/), for example, are
much more respectful of CalDAV and CardDAV and can be used with a large number
of clients. They are very good choices if you want to develop and test new
CalDAV clients, or if you have a possibly heterogeneous list of user agents.

Even if it tries it best to follow the RFCs, Radicale does not and **will not**
blindly implements the CalDAV and CardDAV standards. It is mainly designed to
support the CalDAV and CardDAV implementations of different clients.

#### Simple

Radicale is designed to be simple to install, simple to configure, simple to
use.

The installation is very easy, particularly with Linux: one dependency, no
superuser rights needed, no configuration required, no database. Installing and
launching the main script out-of-the-box, as a normal user, are often the only
steps to have a simple remote calendar and contact access.

Contrary to other servers that are often complicated, require high privileges
or need a strong configuration, the Radicale Server can (sometimes, if not
often) be launched in a couple of minutes, if you follow the
[tutorial](#documentation/tutorial).

#### Lazy

The CalDAV RFC defines what must be done, what can be done and what cannot be
done. Many violations of the protocol are totally defined and behaviours are
given in such cases.

Radicale often assumes that the clients are perfect and that protocol
violations do not exist. That is why most of the errors in client requests have
undetermined consequences for the lazy server that can reply good answers, bad
answers, or even no answer.

### History

Radicale has been started as a (free topic) stupid school project replacing
another (assigned topic) even more stupid school project.

At the beginning, it was just a proof-of-concept. The main goal was to write a
small, dirty and simple CalDAV server working with Lightning, using no external
libraries. That's how we created a piece of code that's (quite) easy to
understand, to use and to hack.

The [first lines](https://github.com/Kozea/Radicale/commit/b1591aea) have been
added to the SVN (!) repository as I was drinking (many) beers at the very end
of 2008 (Python 2.6 and 3.0 were just released). It's now packaged for a
growing number of Linux distributions.

And that was fun going from here to there thanks to you!

# News

Latest version of Radicale is 2.1.12,
released on May 19, 2020
([changelog](https://github.com/Kozea/Radicale/blob/2.1.12/NEWS.md)).

## May 19, 2020 - Radicale 2.1.12

Radicale 2.1.12 is out!

### 2.1.12 - Wild Radish

This release is compatible with version 2.0.0. Follow our
[migration guide](#documentation/migration-from-1xx-to-2xx) if you want to switch
from 1.x.x to 2.x.x.

* Include documentation in source archive

## November 5, 2018 - Radicale 2.1.11

Radicale 2.1.11 is out!

### 2.1.11 - Wild Radish

This release is compatible with version 2.0.0. Follow our
[migration guide](#documentation/migration-from-1xx-to-2xx) if you want to switch
from 1.x.x to 2.x.x.

* Fix moving items between collections

## August 16, 2018 - Radicale 2.1.10

Radicale 2.1.10 is out!

### 2.1.10 - Wild Radish

This release is compatible with version 2.0.0. Follow our
[migration guide](#documentation/migration-from-1xx-to-2xx) if you want to switch
from 1.x.x to 2.x.x.

* Update required versions for dependencies
* Get ``RADICALE_CONFIG`` from WSGI environ
* Improve HTTP status codes
* Fix race condition in storage lock creation
* Raise default limits for content length and timeout
* Log output from hook

## April 21, 2018 - Radicale 2.1.9

Radicale 2.1.9 is out!

### 2.1.9 - Wild Radish

This release is compatible with version 2.0.0. Follow our
[migration guide](#documentation/migration-from-1xx-to-2xx) if you want to switch
from 1.x.x to 2.x.x.

* Specify versions for dependencies
* Move WSGI initialization into module
* Check if ``REPORT`` method is actually supported
* Include ``rights`` file in source distribution
* Specify ``md5`` and ``bcrypt`` as extras
* Improve logging messages
* Windows: Fix crash when item path is a directory

## September 24, 2017 - Radicale 2.1.8

Radicale 2.1.8 is out!

### 2.1.8 - Wild Radish

This release is compatible with version 2.0.0. Follow our
[migration guide](#documentation/migration-from-1xx-to-2xx) if you want to switch
from 1.x.x to 2.x.x.

* Flush files before fsync'ing

## September 17, 2017 - Radicale 2.1.7

Radicale 2.1.7 is out!

### 2.1.7 - Wild Radish

This release is compatible with version 2.0.0. Follow our
[migration guide](#documentation/migration-from-1xx-to-2xx) if you want to switch
from 1.x.x to 2.x.x.

* Don't print warning when cache format changes
* Add documentation for ``BaseAuth``
* Add ``is_authenticated2(login, user, password)`` to ``BaseAuth``
* Fix names of custom properties in PROPFIND requests with
  ``D:propname`` or ``D:allprop``
* Return all properties in PROPFIND requests with ``D:propname`` or
  ``D:allprop``
* Allow ``D:displayname`` property on all collections
* Answer with ``D:unauthenticated`` for ``D:current-user-principal`` property
  when not logged in
* Remove non-existing ``ICAL:calendar-color`` and ``C:calendar-timezone``
  properties from PROPFIND requests with ``D:propname`` or ``D:allprop``
* Add ``D:owner`` property to calendar and address book objects
* Remove ``D:getetag`` and ``D:getlastmodified`` properties from regular
  collections

## September 11, 2017 - Radicale 2.1.6

Radicale 2.1.6 is out!

### 2.1.6 - Wild Radish

This release is compatible with version 2.0.0. Follow our
[migration guide](#documentation/migration-from-1xx-to-2xx) if you want to switch
from 1.x.x to 2.x.x.

* Fix content-type of VLIST
* Specify correct COMPONENT in content-type of VCALENDAR
* Cache COMPONENT of calendar objects (improves speed with some clients)
* Stricter parsing of filters
* Improve support for CardDAV filter
* Fix some smaller bugs in CalDAV filter
* Add X-WR-CALNAME and X-WR-CALDESC to calendars downloaded via HTTP/WebDAV
* Use X-WR-CALNAME and X-WR-CALDESC from calendars published via WebDAV

## August 25, 2017 - Radicale 2.1.5

Radicale 2.1.5 is out!

### 2.1.5 - Wild Radish

This release is compatible with version 2.0.0. Follow our
[migration guide](#documentation/migration-from-1xx-to-2xx) if you want to switch
from 1.x.x to 2.x.x.

* Add ``--verify-storage`` command-line argument
* Allow comments in the htpasswd file
* Don't strip whitespaces from user names and passwords in the htpasswd file
* Remove cookies from logging output
* Allow uploads of whole collections with many components
* Show warning message if server.timeout is used with Python < 3.5.2

## August 4, 2017 - Radicale 2.1.4

Radicale 2.1.4 is out!

### 2.1.4 - Wild Radish

This release is compatible with version 2.0.0. Follow our
[migration guide](#documentation/migration-from-1xx-to-2xx) if you want to switch
from 1.x.x to 2.x.x.

* Fix incorrect time range matching and calculation for some edge-cases with
  rescheduled recurrences
* Fix owner property

## August 2, 2017 - Radicale 2.1.3

Radicale 2.1.3 is out!

### 2.1.3 - Wild Radish

This release is compatible with version 2.0.0. Follow our
[migration guide](#documentation/migration-from-1xx-to-2xx) if you want to switch
from 1.x.x to 2.x.x.

* Enable timeout for SSL handshakes and move them out of the main thread
* Create cache entries during upload of items
* Stop built-in server on Windows when Ctrl+C is pressed
* Prevent slow down when multiple requests hit a collection during cache warm-up

## July 24, 2017 - Radicale 2.1.2

Radicale 2.1.2 is out!

### 2.1.2 - Wild Radish

This release is compatible with version 2.0.0. Follow our
[migration guide](#documentation/migration-from-1xx-to-2xx) if you want to switch
from 1.x.x to 2.x.x.

* Remove workarounds for bugs in VObject < 0.9.5
* Error checking of collection tags and associated components
* Improve error checking of uploaded collections and components
* Don't delete empty collection properties implicitly
* Improve logging of VObject serialization

## July 1, 2017 - Radicale 2.1.1

Radicale 2.1.1 is out!

### 2.1.1 - Wild Radish Again

This release is compatible with version 2.0.0. Follow our
[migration guide](#documentation/migration-from-1xx-to-2xx) if you want to switch
from 1.x.x to 2.x.x.

* Add missing UIDs instead of failing
* Improve error checking of calendar and address book objects
* Fix upload of whole address books

## June 25, 2017 - Radicale 2.1.0

Radicale 2.1.0 is out!

### 2.1.0 - Wild Radish

This release is compatible with version 2.0.0. Follow our
[migration guide](#documentation/migration-from-1xx-to-2xx) if you want to switch
from 1.x.x to 2.1.0.

* Built-in web interface for creating and managing address books and calendars
  * can be extended with web plugins
* Much faster storage backend
* Significant reduction in memory usage
* Improved logging
  * Include paths (of invalid items / requests) in log messages
  * Include configuration values causing problems in log messages
  * Log warning message for invalid requests by clients
  * Log error message for invalid files in the storage backend
  * No stack traces unless debugging is enabled
* Time range filter also regards overwritten recurrences
* Items that couldn't be filtered because of bugs in VObject are always
  returned (and a warning message is logged)
* Basic error checking of configuration files
* File system locking isn't disabled implicitly anymore, instead a new
  configuration option gets introduced
* The permissions of the lock file are not changed anymore
* Support for sync-token
* Support for client-side SSL certificates
* Rights plugins can decide if access to an item is granted explicitly
  * Respond with 403 instead of 404 for principal collections of non-existing
    users when ``owner_only`` plugin is used (information leakage)
* Authentication plugins can provide the login and password from the
  environment
  * new ``remote_user`` plugin, that gets the login from the ``REMOTE_USER``
    environment variable (for WSGI server)
  * new ``http_x_remote_user`` plugin, that gets the login from the
    ``X-Remote-User`` HTTP header (for reverse proxies)

## May 27, 2017 - Radicale 2.0.0

Radicale 2.0.0 is out!

### 2.0.0 - Little Big Radish

This feature is not compatible with the 1.x.x versions. Follow our
[migration guide](#documentation/migration-from-1xx-to-2xx) if you want to switch
from 1.x.x to 2.0.0.

- Support Python 3.3+ only, Python 2 is not supported anymore
- Keep only one simple filesystem-based storage system
- Remove built-in Git support
- Remove built-in authentication modules
- Keep the WSGI interface, use Python HTTP server by default
- Use a real iCal parser, rely on the "vobject" external module
- Add a solid calendar discovery
- Respect the difference between "files" and "folders", don't rely on slashes
- Remove the calendar creation with GET requests
- Be stateless
- Use a file locker
- Add threading
- Get atomic writes
- Support new filters
- Support read-only permissions
- Allow External plugins for authentication, rights management, storage and version control

This release concludes endless months of hard work from the community. You, all
users and contributors, deserve a big **thank you**.

This project has been an increadible experience for me, your dear Guillaume,
creator and maintainer of Radicale. After more than 8 years of fun, I think
that it's time to open this software to its contributors. Radicale can grow and
become more than the toy it used to be. I've always seen Radicale as a small
and simple piece of code, and I don't want to prevent people from adding
features just because I can't or don't want to maintain them. The community is
now large enough to handle this.

If you're interested in Radicale, you can
read [#372](https://github.com/Kozea/Radicale/issues/372) and build its
future.

## May 3, 2017 - Radicale 1.1.2

Radicale 1.1.2 is out!

### 1.1.2 - Third Law of Nature

* **Security fix**: Add a random timer to avoid timing oracles and simple
  bruteforce attacks when using the htpasswd authentication method.
* Various minor fixes.

## December 31, 2015 - Radicale 1.1

Radicale 1.1 is out!

### 1.1 - Law of Nature

One feature in this release is **not backward compatible**:

* Use the first matching section for rights (inspired from daald)

Now, the first section matching the path and current user in your custom rights
file is used. In the previous versions, the most permissive rights of all the
matching sections were applied. This new behaviour gives a simple way to make
specific rules at the top of the file independant from the generic ones.

Many **improvements in this release are related to security**, you should
upgrade Radicale as soon as possible:

* Improve the regex used for well-known URIs (by Unrud)
* Prevent regex injection in rights management (by Unrud)
* Prevent crafted HTTP request from calling arbitrary functions (by Unrud)
* Improve URI sanitation and conversion to filesystem path (by Unrud)
* Decouple the daemon from its parent environment (by Unrud)

Some bugs have been fixed and little enhancements have been added:

* Assign new items to corret key (by Unrud)
* Avoid race condition in PID file creation (by Unrud)
* Improve the docker version (by cdpb)
* Encode message and commiter for git commits
* Test with Python 3.5

## September 14, 2015 - Radicale 1.0, what's next?

Radicale 1.0 is out!

### 1.0 - Sunflower

* Enhanced performances (by Mathieu Dupuy)
* Add MD5-APR1 and BCRYPT for htpasswd-based authentication (by Jan-Philip Gehrcke)
* Use PAM service (by Stephen Paul Weber)
* Don't discard PROPPATCH on empty collections (Markus Unterwaditzer)
* Write the path of the collection in the git message (Matthew Monaco)
* Tests launched on Travis

As explained in a previous [mail](http://librelist.com/browser//radicale/2015/8/21/radicale-1-0-is-coming-what-s-next/),
this version is called 1.0 because:

- there are no big changes since 0.10 but some small changes are really useful,
- simple tests are now automatically launched on Travis, and more can be added
  in the future (https://travis-ci.org/Kozea/Radicale).

This version will be maintained with only simple bug fixes on a separate git
branch called ``1.0.x``.

Now that this milestone is reached, it's time to think about the future. When
Radicale has been created, it was just a proof-of-concept. The main goal was to
write a small, stupid and simple CalDAV server working with Lightning, using no
external libraries. That's how we created a piece of code that's (quite) easy
to understand, to use and to hack.

The first lines have been added to the SVN (!) repository as I was drinking
beers at the very end of 2008. It's now packaged for a growing number of Linux
distributions.

And that was fun going from here to there thanks to you. So… **Thank you,
you're amazing**. I'm so glad I've spent endless hours fixing stupid bugs,
arguing about databases and meeting invitations, reading incredibly interesting
RFCs and debugging with the fabulous clients from Apple. I mean: that really,
really was really, really cool :).

During these years, a lot of things have changed and many users now rely on
Radicale in production. For example, I use it to manage medical calendars, with
thousands requests per day.  Many people are happy to install Radicale on their
small home servers, but are also frustrated by performance and unsupported
specifications when they're trying to use it seriously.

So, now is THE FUTURE! I think that Radicale 2.0 should:

- rely on a few external libraries for simple critical points (dealing with
  HTTP and iCal for example),
- be thread-safe,
- be small,
- be documented in a different way (for example by splitting the client part
  from the server part, and by adding use cases),
- let most of the "auth" modules outside in external modules,
- have more and more tests,
- have reliable and faster filesystem and database storage mechanisms,
- get a new design :).

I'd also secretly love to drop the Python 2.x support.

These ideas are not all mine (except from the really, really, really important
"design" point :p), they have been proposed by many developers and users. I've
just tried to gather them and keep points that seem important to me.

Other points have been discussed with many users and contibutors, including:

- support of other clients, including Windows and BlackBerry phones,
- server-side meeting invitations,
- different storage system as default (or even unique?).

I'm not a huge fan of these features, either because I can't do anything about
them, or because I think that they're Really Bad Ideas®™. But I'm ready to talk
about them, because, well, I may not be always right!

Need to talk about this? You know how to [contact us](#contribute)!

## January 12, 2015 - Radicale 0.10

Radicale 0.10 is out!

### 0.10 - Lovely Endless Grass

* Support well-known URLs (by Mathieu Dupuy)
* Fix collection discovery (by Markus Unterwaditzer)
* Reload logger config on SIGHUP (by Élie Bouttier)
* Remove props files when deleting a collection (by Vincent Untz)
* Support salted SHA1 passwords (by Marc Kleine-Budde)
* Don't spam the logs about non-SSL IMAP connections to localhost (by Giel van Schijndel)

This version should bring some interesting discovery and auto-configuration
features, mostly with Apple clients.

Lots of love and kudos for the people who have spent hours to test features and
report issues, that was long but really useful (and some of you have been
really patient :p).

Issues are welcome, I'm sure that you'll find horrible, terrible, crazy bugs
faster than me. I'll release a version 0.10.1 if needed.

What's next? It's time to fix and improve the storage methods. A real API for
the storage modules is a good beginning, many pull requests are already ready
to be discussed and merged, and we will probably get some good news about
performance this time. Who said "databases, please"?

## July 12, 2013 - Radicale 0.8

Radicale 0.8 is out!

### 0.8 - Rainbow

* New authentication and rights management modules (by Matthias Jordan)
* Experimental database storage
* Command-line option for custom configuration file (by Mark Adams)
* Root URL not at the root of a domain (by Clint Adams, Fabrice Bellet, Vincent Untz)
* Improved support for iCal, CalDAVSync, CardDAVSync, CalDavZAP and CardDavMATE
* Empty PROPFIND requests handled (by Christoph Polcin)
* Colon allowed in passwords
* Configurable realm message

This version brings some of the biggest changes since Radicale's creation,
including an experimental support of database storage, clean authentication
modules, and rights management finally designed for real users.

So, dear user, be careful: **this version changes important things in the
configuration file, so check twice that everything is OK when you update to
0.8, or you can have big problems**.

More and more clients are supported, as a lot of bug fixes and features have
been added for this purpose. And before you ask: yes, 2 web-based clients,
[CalDavZAP and CardDavMATE](http://www.inf-it.com/open-source/clients/), are
now supported!

Even if there has been a lot of time to test these new features, I am pretty
sure that some really annoying bugs have been left in this version. We will
probably release minor versions with bugfixes during the next weeks, and it
will not take one more year to reach 0.8.1.

The documentation has been updated, but some parts are missing and some may be
out of date. You can [report bugs](https://github.com/Kozea/Radicale/issues)
or even [write documentation directly on GitHub](https://github.com/Kozea/Radicale/blob/website/pages/user_documentation.rst)
if you find something strange (and you probably will).

If anything is not clear, or if the way rights work is a bit complicated to
understand, or if you are so happy because everything works so well, you can
[share your thoughts](#contribute)!

It has been a real pleasure to work on this version, with brilliant ideas and
interesting bug reports from the community. I'd really like to thank all the
people reporting bugs, chatting on IRC, sending mails and proposing pull
requests: you are awesome.

## August 3, 2012 - Radicale 0.7.1

Radicale 0.7.1 is out!

### 0.7.1 - Waterfalls

* Many address books fixes
* New IMAP ACL (by Daniel Aleksandersen)
* PAM ACL fixed (by Daniel Aleksandersen)
* Courier ACL fixed (by Benjamin Frank)
* Always set display name to collections (by Oskari Timperi)
* Various DELETE responses fixed

It's been a long time since the last version… As usual, many people have
contributed to this new version, that's a pleasure to get these pull requests.

Most of the commits are bugfixes, especially about ACL backends and address
books. Many clients (including aCal and SyncEvolution) will be much happier
with this new version than with the previous one.

By the way, one main new feature has been added: a new IMAP ACL backend, by
Daniel. And about authentication, exciting features are coming soon, stay
tuned!

Next time, as many mails have come from angry and desperate coders, tests will
be *finally* added to help them to add features and fix bugs. And after that,
who knows, it may be time to release Radicale 1.0…

## March 22, 2012 - Radicale 0.7

Radicale 0.7 is out, at least!

### 0.7 - Eternal Sunshine

* Repeating events
* Collection deletion
* Courier and PAM authentication methods
* CardDAV support
* Custom LDAP filters supported

**A lot** of people have reported bugs, proposed new features, added useful
code and tested many clients. Thank you Lynn, Ron, Bill, Patrick, Hidde,
Gerhard, Martin, Brendan, Vladimir, and everybody I've forgotten.

## January 5, 2012 - Radicale 0.6.4, News from Calypso

New year, new release. Radicale 0.6.4 has a really short changelog:

### 0.6.4 - Tulips

* Fix the installation with Python 3.1

The bug was in fact caused by a
[bug in Python 3.1](http://bugs.python.org/issue9561), everything should be OK
now.

### Calypso

After a lot of changes in Radicale, Keith Packard has decided to launch a fork
called [Calypso](http://keithp.com/blogs/calypso/), with nice features such
as a Git storage mechanism and a CardDAV support.

There are lots of differences between the two projects, but the final goal for
Radicale is to provide these new features as soon as possible. Thanks to the
work of Keith and other people on GitHub, a basic CardDAV support has been
added in the [carddav branch](https://github.com/Kozea/Radicale/tree/carddav)
and already works with Evolution. Korganizer also works with existing address
books, and CardDAV-Sync will be tested soon. If you want to test other clients,
please let us know!

## November 3, 2011 - Radicale 0.6.3

Radicale version 0.6.3 has been released, with bugfixes that could be
interesting for you!

### 0.6.3 - Red Roses

* MOVE requests fixed
* Faster REPORT answers
* Executable script moved into the package

### What's New Since 0.6.2?

The MOVE requests were suffering a little bug that is fixed now. These requests
are only sent by Apple clients, Mac users will be happy.

The REPORT request were really, really slow (several minutes for large
calendars). This was caused by an awful algorithm parsing the entire calendar
for each event in the calendar. The calendar is now only parsed three times,
and the events are found in a Python list, turning minutes into seconds! Much
better, but far from perfection…

Finally, the executable script parsing the command line options and starting
the HTTP servers has been moved from the ``radicale.py`` file into the
``radicale`` package. Two executable are now present in the archive: the good
old ``radicale.py``, and ``bin/radicale``. The second one is only used by
``setup.py``, where the hack used to rename ``radicale.py`` into ``radicale``
has therefore been removed. As a consequence, you can now launch Radicale with
the simple ``python -m radicale`` command, without relying on an executable.

### Time for a Stable Release!

The next release may be a stable release, symbolically called 1.0. Guess what's
missing? Tests, of course!

A non-regression testing suite, based on the clients' requests, will soon be
added to Radicale. We're now thinking about a smart solution to store the
tests, to represent the expected answers and to launch the requests. We've got
crazy ideas, so be prepared: you'll definitely *want* to write tests during the
next weeks!

Repeating events, PAM and Courier authentication methods have already been
added in master. You'll find them in the 1.0 release!

### What's Next?

Being stable is one thing, being cool is another one. If you want some cool new
features, you may be interested in:

- WebDAV and CardDAV support
- Filters and rights management
- Multiple storage backends, such as databases and git
- Freebusy periods
- Email alarms

Issues have been reported in the bug tracker, you can follow there the latest
news about these features. Your beloved text editor is waiting for you!

## September 27, 2011 - Radicale 0.6.2

0.6.2 is out with minor bugfixes.

### 0.6.2 - Seeds

* iPhone and iPad support fixed
* Backslashes replaced by slashes in PROPFIND answers on Windows
* PyPI archive set as default download URL

## August 28, 2011 - Radicale 0.6.1, Changes, Future

As previously imagined, a new 0.6.1 version has been released, mainly fixing
obvious bugs.

### 0.6.1 - Growing Up

* Example files included in the tarball
* htpasswd support fixed
* Redirection loop bug fixed
* Testing message on GET requests

The changelog is really small, so there should be no real new problems since
0.6. The example files for logging, FastCGI and WSGI are now included in the
tarball, for the pleasure of our dear packagers!

A new branch has been created for various future bug fixes. You can expect to
get more 0.6.x versions, making this branch a kind of "stable" branch with no
big changes.

### GitHub, Mailing List, New Website

A lot of small changes occurred during the last weeks.

If you're interested in code and new features, please note that we moved the
project from Gitorious to GitHub. Being hosted by Gitorious was a
nice experience, but the service was not that good and we were missing some
useful features such as git hooks. Moreover, GitHub is really popular, we're
sure that we'll meet a lot of kind users and coders there.

We've also created a mailing-list on Librelist to keep a public
trace of the mails we're receiving. It a bit empty now, but we're sure that
you'll soon write us some kind words. For example, you can tell us what you
think of our new website!

### Future Features

In the next weeks, new exciting features are coming in the master branch! Some
of them are almost ready:

- Henry-Nicolas has added the support for the PAM and Courier-Authdaemon
  authentication mechanisms.
- An anonymous called Keith Packard has prepared some small changes, such as
  one file per event, cache and git versioning. Yes. Really.

As you can find in the [Radicale Roadmap](http://redmine.kozea.fr/versions/),
tests, rights and filters are expected for 0.7.

## August 1, 2011 - Radicale 0.6 Released

Time for a new release with **a lot** of new exciting features!

### 0.6 - Sapling

* WSGI support
* IPv6 support
* Smart, verbose and configurable logs
* Apple iCal 4 and iPhone support (by Łukasz Langa)
* CalDAV-Sync support (by Marten Gajda)
* aCal support
* KDE KOrganizer support
* LDAP auth backend (by Corentin Le Bail)
* Public and private calendars (by René Neumann)
* PID file
* MOVE requests management
* Journal entries support
* Drop Python 2.5 support

Well, it's been a little longer than expected, but for good reasons: a lot of
features have been added, and a lot of clients are known to work with Radicale,
thanks to kind contributors. That's definitely good news! But…

Testing all the clients is really painful, moreover for the ones from Apple (I
have no Mac nor iPhone of my own). We should seriously think of automated
tests, even if it's really hard to maintain, and maybe not that useful. If
you're interested in tests, you can look at
[the wonderful regression suite of DAViCal](http://repo.or.cz/w/davical.git/tree/HEAD:/testing/tests/regression-suite).

The new features, for example the WSGI support, are also poorly documented. If
you have some Apache or lighttpd configuration working with Radicale, you can
make the world a little bit better by writing a paragraph or two in the
[Radicale documentation](https://gitorious.org/radicale/website). It's simple
plain text, don't be afraid!

Because of all these changes, Radicale 0.6 may be a little bit buggy; a 0.6.1
will probably be released soon, fixing small problems with clients and
features. Get ready to report bugs, I'm sure that you can find one (and fix
it)!

## July 2, 2011 - Feature Freeze for 0.6

According to the [roadmap](http://redmine.kozea.fr/projects/radicale/roadmap),
a lot of features have been added since Radicale 0.5, much more than
expected. It's now time to test Radicale with your favourite client and to
report bugs before we release the next stable version!

Last week, the iCal and iPhone support written by Łukasz has been fixed in
order to restore the broken Lightning support. After two afternoons of tests
with Rémi, we managed to access the same calendar with Lightning, iCal, iPhone
and Evolution, and finally discovered that CalDAV could also be a perfect
instant messaging protocol between a Mac, a PC and a phone.

After that, we've had the nice surprise to see events displayed without a
problem (but after some strange steps of configuration) by aCal on Salem's
Android phone.

It was Friday, fun fun fun fun.

So, that's it: Radicale supports Lightning, Evolution, Kontact, aCal for
Android, iPhone and iCal. Of course, before releasing a new tarball:

- [documentation](1.1.html#documentation/user-documentation/simple-usage/starting-the-client) is needed for the
  new clients that are not documented yet (Kontact, aCal and iPhone);
- tests are welcome, particularly for the Apple clients that I can't test
  anymore;
- no more features will be added, they'll wait in separate branches for the 0.7
  development.

Please [report bugs](http://redmine.kozea.fr/projects/radicale/issues) if
anything goes wrong during your tests, or just let us know
[by Jabber or by mail](#contribute) if everything is OK.

## May 1, 2011 - Ready for WSGI

Here it is! Radicale is now ready to be launched behind your favourite HTTP
server (Apache, Lighttpd, Nginx or Tomcat for example). That's really good
news, because:

- Real HTTP servers are much more efficient and reliable than the default
  Python server used in Radicale;
- All the authentication backends available for your server will be available
  for Radicale;
- Thanks to [flup](http://trac.saddi.com/flup), Radicale can be interfaced
  with all the servers supporting CGI, AJP, FastCGI or SCGI;
- Radicale works very well without any additional server, without any
  dependencies, without configuration, just as it was working before;
- This one more feature removes useless code, less is definitely more.

The WSGI support has only be tested as a stand-alone executable and behind
Lighttpd, you should definitely try if it works with you favourite server too!

No more features will be added before (quite) a long time, because a lot of
documentation and test is waiting for us. If you want to write tutorials for
some CalDAV clients support (iCal, Android, iPhone), HTTP servers support or
logging management, feel free to fork the documentation git repository and ask
for a merge. It's plain text, I'm sure you can do it!

## April 30, 2011 - Apple iCal Support

After a long, long work, the iCal support has finally been added to Radicale!
Well, this support is only for iCal 4 and is highly experimental, but you can
test it right now with the git master branch. Bug reports are welcome!

Dear MacOS users, you can thank all the gentlemen who sended a lot of debugging
iformation. Special thanks to Andrew from DAViCal, who helped us a lot with his
tips and his tests, and Rémi Hainaud who lent his laptop for the final tests.

The default server address is ``localhost:5232/user/``, where calendars can be
added. Multiple calendars and owner-less calendars are not tested yet, but they
should work quite well. More documentation will be added during the next
days. It will then be time to release the Radicale 0.6 version, and work on the
WSGI support.

## April 25, 2011 - Two Features and One New Roadmap

Two features have just reached the master branch, and the roadmap has been
refreshed.

### LDAP Authentication

Thanks to Corentin, the LDAP authentication is now included in Radicale. The
support is experimental and may suffer unstable connexions and security
problems. If you are interested in this feature (a lot of people seem to be),
you can try it and give some feedback.

No SSL support is included yet, but this may be quite easy to add. By the way,
serious authentication methods will rely on a "real" HTTP server, as soon as
Radicale supports WSGI.

### Journal Entries

Mehmet asked for the journal entries (aka. notes or memos) support, that's
done! This also was an occasion to clean some code in the iCal parser, and to
add a much better management of multi-lines entries. People experiencing crazy
`X-RADICALE-NAME` entries can now clean their files, Radicale won't pollute
them again.

### New Roadmap

Except from htpasswd and LDAP, most of the authentication backends (database,
SASL, PAM, user groups) are not really easy to include in Radicale. The easiest
solution to solve this problem is to give Radicale a CGI support, to put it
behind a solid server such as Apache. Of course, CGI is not enough: a WSGI
support is quite better, with the FastCGI, AJP and SCGI backends offered by
[flup](http://trac.saddi.com/flup/). Quite exciting, isn't it?

That's why it was important to add new versions on the roadmap. The 0.6 version
is now waiting for the Apple iCal support, and of course for some tests to kill
the last remaining bugs. The only 0.7 feature will be WSGI, allowing many new
authentication methods and a real multithread support.

After that, 0.8 may add CalDAV rights and filters, while 1.0 will draw
thousands of rainbows and pink unicorns (WebDAV sync, CardDAV, Freebusy). A lot
of funky work is waiting for you, hackers!

### Bugs

Many bugs have also been fixed, most of them due to the owner-less calendars
support. Radicale 0.6 may be out in a few weeks, you should spend some time
testing the master branch and filling the bug tracker.

## April 10, 2011 - New Features

Radicale 0.5 was released only 8 days ago, but 3 new features have already been
added to the master branch:

- IPv6 support, with multiple addresses/ports support
- Logs and debug mode
- Owner-less calendars

Most of the code has been written by Necoro and Corentin, and that was not easy
at all: Radicale is now multithreaded! For sure, you can find many bugs and
report them on the
[bug tracker](http://redmine.kozea.fr/projects/radicale/issues). And if you're
fond of logging, you can even add a default configuration file and more debug
messages in the source.

## April 2, 2011 - Radicale 0.5 Released

Radicale 0.5 is out! Here is what's new:

### 0.5 - Historical Artifacts

* Calendar depth
* iPhone support
* MacOS and Windows support
* HEAD requests management
* htpasswd user from calendar path

iPhone support, but no iCal support for 0.5, despite our hard work, sorry!
After 1 month with no more activity on the dedicated bug, it was time to forget
it and hack on new awesome features. Thanks for your help, dear Apple users, I
keep the hope that one day, Radicale will work with you!

So, what's next? As promised, some cool git branches will soon be merged, with
LDAP support, logging, IPv6 and anonymous calendars. Sounds pretty cool, heh?
Talking about new features, more and more people are asking for a CardDAV
support in Radicale. A git branch and a feature request are open, feel free to
hack and discuss.

## February 3, 2011 - Jabber Room and iPhone Support

After a lot of help and testing work from Andrew, Björn, Anders, Dorian and
Pete (and other ones we could have forgotten), a simple iPhone support has been
added in the git repository. If you are interested, you can test this feature
*right now* by
[downloading the latest git version](#download//git-repository)
(a tarball is even available too if you don't want or know how to use git).

No documentation has been written yet, but using the right URL in the
configuration should be enough to synchronize your calendars. If you have any
problems, you can ask by joining our new Jabber room:
radicale@room.jabber.kozea.fr.

Radicale 0.5 will be released as soon as the iCal support is ready. If you have
an Apple computer, Python skills and some time to spend, we'd be glad to help
you debugging Radicale.

## October 21, 2010 - News from Radicale

During the last weeks, Radicale has not been idle, even if no news have been
posted since August. Thanks to Pete, Pierre-Philipp and Andrew, we're trying to
add a better support on MacOS, Windows and mobile devices like iPhone and
Android-based phones.

All the tests on Windows have been successful: launching Radicale and using
Lightning as client works without any problems. On Android too, some testers
have reported clients working with Radicale. These were the good news.

The bad news come from Apple: both iPhone and MacOS default clients are not
working yet, despite the latest enhancements given to the PROPFIND
requests. The problems are quite hard to debug due to our lack of Apple
hardware, but Pete is helping us in this difficult quest! Radicale 0.5 will be
out as soon as these two clients are working.

Some cool stuff is coming next, with calendar collections and groups, and a
simple web-based CalDAV client in early development. Stay tuned!

## August 8, 2010 - Radicale 0.4 Released

Radicale 0.4 is out! Here is what's new:

### 0.4 - Hot Days Back

* Personal calendars
* HEAD requests
* Last-Modified HTTP header
* ``no-ssl`` and ``foreground`` options
* Default configuration file

This release has mainly been released to help our dear packagers to include a default configuration file and to write init scripts. Big thanks to Necoro for his work on the new Gentoo ebuild!

## July 4, 2010 - Three Features Added Last Week

Some features have been added in the git repository during the last weeks,
thanks to Jerome and Mariusz!

Personal Calendars
  Calendars accessed through the htpasswd ACL module can now be
  personal. Thanks to the ``personal`` option, a user called ``bob`` can access
  calendars at ``/bob/*`` but not to the ``/alice/*`` ones.

HEAD Requests
  Radicale can now answer HEAD requests. HTTP headers can be retrieved thanks
  to this request, without getting contents given by the GET requests.

Last-Modified HTTP header
  The Last-Modified header gives the last time when the calendar has been
  modified. This is used by some clients to cache the calendars and not
  retrieving them if they have not been modified.

## June 14, 2010 - Radicale 0.3 Released

Radicale 0.3 is out! Here is what’s new:

### 0.3 - Dancing Flowers

* Evolution support
* Version management

The website changed a little bit too, with some small HTML5 and CSS3 features
such as articles, sections, transitions, opacity, box shadows and rounded
corners. If you’re reading this website with Internet Explorer, you should
consider using a standard-compliant browser!

Radicale is now included in Squeeze, the testing branch of Debian. A
[Radicale ebuild for Gentoo](http://bugs.gentoo.org/show_bug.cgi?id=322811) has
been proposed too. If you want to package Radicale for another distribution,
you’re welcome!

Next step is 0.5, with calendar collections, and Windows and MacOS support.

## May 31, 2010 - May News
### News from contributors

Jonas Smedegaard packaged Radicale for Debian last week. Two packages, called
``radicale`` for the daemon and ``python-radicale`` for the module, have been
added to Sid, the unstable branch of Debian. Thank you, Jonas!

Sven Guckes corrected some of the strange-English-sentences present on this
website. Thank you, Sven!

### News from software

A simple ``VERSION`` has been added in the library: you can now play with
``radicale.VERSION`` and ``$radicale --version``.

After playing with the version (should not be too long), you may notice that
the next version is called 0.3, and not 0.5 as previously decided. The 0.3 main
goal is to offer the support for Evolution as soon as possible, without waiting
for the 0.5. After more than a month of test, we corrected all the bugs we
found and everything seems to be fine; we can imagine that a brand new tarball
will be released during the first days of June.

## April 19, 2010 - Evolution Supported

Radicale now supports another CalDAV client:
[Evolution, the default mail, addressbook and calendaring client for Gnome](http://projects.gnome.org/evolution/).
This feature was quite easy to add, as it required less than 20 new lines of
code in the requests handler.

If you are interested, just clone the
[git repository](http://www.gitorious.org/radicale/radicale).

## April 13, 2010 - Radicale 0.2 Released

Radicale 0.2 is out! Here is what’s new:

### 0.2 - Snowflakes

* Sunbird pre-1.0 support
* SSL connection
* Htpasswd authentication
* Daemon mode
* User configuration
* Twisted dependency removed
* Python 3 support
* Real URLs for PUT and DELETE
* Concurrent modification reported to users
* Many bugs fixed by Roger Wenham

First of all, we would like to thank Roger Wenham for his bugfixes and his
supercool words.

You may have noticed that Sunbird 1.0 has not been released, but according to
the Mozilla developers, 1.0pre is something like a final version.

You may have noticed too that Radicale can be
[downloaded from PyPI](http://pypi.python.org/pypi/Radicale/0.2). Of course, it
is also available on the [download page](#download).

## January 21, 2010 - HTTPS and Authentication

HTTPS connections and authentication have been added to Radicale this
week. Command-line options and personal configuration files are also ready for
test. According to the TODO file included in the package, the next version will
finally be 0.2, when sunbird 1.0 is out. Go, Mozilla hackers, go!

HTTPS connection
  HTTPS connections are now available using the standard TLS mechanisms. Give
  Radicale a private key and a certificate, and your data are now safe.

Authentication
  A simple authentication architecture is now available, allowing different
  methods thanks to different modules. The first two modules are ``fake`` (no
  authentication) and ``htpasswd`` (authentication with an ``htpasswd`` file
  created by the Apache tool). More methods such as LDAP are coming soon!

## January 15, 2010 - Ready for Python 3

Dropping Twisted dependency was the first step leading to another big feature:
Radicale now works with Python 3! The code was given a small cleanup, with some
simplifications mainly about encoding. Before the 0.1.1 release, feel free to
test the git repository, all Python versions from 2.5 should be OK.

## January 11, 2010 - Twisted no Longer Required

Good news! Radicale 0.1.1 will support Sunbird 1.0, but it has another great
feature: it has no external dependency! Twisted is no longer required for the
git version, removing about 50 lines of code.

## December 31, 2009 - Lightning and Sunbird 1.0b2pre Support

Lightning/Sunbird 1.0b2pre is out, adding minor changes in CalDAV support. A
[new commit](http://www.gitorious.org/radicale/radicale/commit/330283e) makes
Radicale work with versions 0.9, 1.0b1 et 1.0b2. Moreover, etags are now quoted
according to the RFC 2616.

## December 9, 2009 - Thunderbird 3 released

[Thunderbird 3 is out](http://www.mozillamessaging.com/thunderbird/3.0/releasenotes/),
and Lightning/Sunbird 1.0 should be released in a few days. The
[last commit in git](http://gitorious.org/radicale/radicale/commit/6545bc8)
should make Radicale work with versions 0.9 and 1.0b1pre. Radicale 0.1.1 will
soon be released adding support for version 1.0.

## September 1, 2009 - Radicale 0.1 Released

First Radicale release! Here is the changelog:

### 0.1 - Crazy Vegetables

* First release
* Lightning/Sunbird 0.9 compatibility
* Easy installer

You can download this version on the [download page](#download).

## July 28, 2009 - Radicale on Gitorious

Radicale code has been released on Gitorious! Take a look at the
[Radicale main page on Gitorious](http://www.gitorious.org/radicale) to view
and download source code.

## July 27, 2009 - Radicale Ready to Launch

The Radicale Project is launched. The code has been cleaned up and will be
available soon…
