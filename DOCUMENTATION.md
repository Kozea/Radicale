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

[Read the latest news](https://github.com/Kozea/Radicale/blob/master/NEWS.md)

# Documentation

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

- [ArchLinux (AUR)](https://aur.archlinux.org/packages/radicale/) by
  Guillaume Bouchard
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
