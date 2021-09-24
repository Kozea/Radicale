# Getting started
### About Radicale

Radicale is a small but powerful CalDAV (calendars, to-do lists) and CardDAV
(contacts) server, that:

  * Shares calendars and contact lists through CalDAV, CardDAV and HTTP.
  * Supports events, todos, journal entries and business cards.
  * Works out-of-the-box, no complicated setup or configuration required.
  * Can limit access by authentication.
  * Can secure connections with TLS.
  * Works with many
    [CalDAV and CardDAV clients](#documentation/supported-clients).
  * Stores all data on the file system in a simple folder structure.
  * Can be extended with plugins.
  * Is GPLv3-licensed free software.

### Installation

Radicale is really easy to install and works out-of-the-box.

```bash
$ python3 -m pip install --upgrade https://github.com/Kozea/Radicale/archive/master.tar.gz
$ python3 -m radicale --storage-filesystem-folder=~/.var/lib/radicale/collections
```

When the server is launched, open http://localhost:5232/ in your browser!
You can login with any username and password.

Want more? Check the [tutorials](#tutorials) and the
[documentation](#documentation).

### What's New?

Read the
[changelog on GitHub.](https://github.com/Kozea/Radicale/blob/master/NEWS.md)

# Tutorials
## Simple 5-minute setup

You want to try Radicale but only have 5 minutes free in your calendar? Let's
go right now and play a bit with Radicale!

When everything works, you can get a [client](#documentation/supported-clients)
and start creating calendars and address books. The server **only** binds to
localhost (is **not** reachable over the network) and you can log in with any
user name and password. If Radicale fits your needs, it may be time for
[some basic configuration](#tutorials/basic-configuration).

Follow one of the chapters below depending on your operating system.

### Linux / \*BSD

First, make sure that **python** 3.5 or later (**python** ≥ 3.6 is
recommended) and **pip** are installed. On most distributions it should be
enough to install the package ``python3-pip``.

Then open a console and type:

```bash
# Run the following command as root or
# add the --user argument to only install for the current user
$ python3 -m pip install --upgrade https://github.com/Kozea/Radicale/archive/master.tar.gz
$ python3 -m radicale --storage-filesystem-folder=~/.var/lib/radicale/collections
```

Victory! Open http://localhost:5232/ in your browser!
You can log in with any username and password.

### Windows

The first step is to install Python. Go to
[python.org](https://python.org) and download the latest version of Python 3.
Then run the installer.
On the first window of the installer, check the "Add Python to PATH" box and
click on "Install now". Wait a couple of minutes, it's done!

Launch a command prompt and type:

```powershell
C:\Users\User> python -m pip install --upgrade https://github.com/Kozea/Radicale/archive/master.tar.gz
C:\Users\User> python -m radicale --storage-filesystem-folder=~/radicale/collections
```

Victory! Open http://localhost:5232/ in your browser!
You can log in with any username and password.

## Basic Configuration

Installation instructions can be found in the
[simple 5-minute setup](#tutorials/simple-5-minute-setup) tutorial.

Radicale tries to load configuration files from `/etc/radicale/config` and
`~/.config/radicale/config`.
Custom paths can be specified with the `--config /path/to/config` command
line argument or the `RADICALE_CONFIG` environment variable.
Multiple configuration files can be separated by `:` (resp. `;` on Windows).
Paths that start with `?` are optional.

You should create a new configuration file at the desired location.
(If the use of a configuration file is inconvenient, all options can be
passed via command line arguments.)

All configuration options are described in detail in the
[Configuration](#documentation/configuration) section.

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
$ htpasswd -c /path/to/users user1
New password:
Re-type new password:
# Add another user
$ htpasswd /path/to/users user2
New password:
Re-type new password:
```

Authentication can be enabled with the following configuration:

```ini
[auth]
type = htpasswd
htpasswd_filename = /path/to/users
# encryption method used in the htpasswd file
htpasswd_encryption = md5
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
options (IPv4 and IPv6):

```ini
[server]
hosts = 0.0.0.0:5232, [::]:5232
```

### Storage

Data is stored in the folder `/var/lib/radicale/collections`. The path can
be changed with the following configuration:

```ini
[storage]
filesystem_folder = /path/to/storage
```

> **Security:** The storage folder should not be readable by unauthorized users.
> Otherwise, they can read the calendar data and lock the storage.
> You can find OS dependent instructions in the
> [Running as a service](#tutorials/running-as-a-service) section.

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

## Running as a service

The method to run Radicale as a service depends on your host operating system.
Follow one of the chapters below depending on your operating system and
requirements.

### Linux with systemd system-wide

Create the **radicale** user and group for the Radicale service.
(Run `useradd --system --user-group --home-dir / --shell /sbin/nologin radicale` as root.)
The storage folder must be writable by **radicale**. (Run
`mkdir -p /var/lib/radicale/collections && chown -R radicale:radicale /var/lib/radicale/collections`
as root.)

> **Security:** The storage should not be readable by others.
> (Run `chmod -R o= /var/lib/radicale/collections` as root.)

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

### Linux with systemd as a user

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

### Windows with "NSSM - the Non-Sucking Service Manager"

First install [NSSM](https://nssm.cc/) and start `nssm install` in a command
prompt. Apply the following configuration:

  * Service name: `Radicale`
  * Application
      * Path: `C:\Path\To\Python\python.exe`
      * Arguments: `-m radicale --config C:\Path\To\Config`
  * I/O redirection
      * Error: `C:\Path\To\Radicale.log`

> **Security:** Be aware that the service runs in the local system account,
> you might want to change this. Managing user accounts is beyond the scope of
> this manual. Also, make sure that the storage folder and log file is not
> readable by unauthorized users.

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
    proxy_set_header  Host $http_host;
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
    RequestHeader    set X-Script-Name /radicale
</Location>
```

Example **Apache .htaccess** configuration:

```apache
DirectoryIndex disabled
RewriteEngine On
RewriteRule ^(.*)$ http://localhost:5232/$1 [P,L]

# Set to directory of .htaccess file:
RequestHeader set X-Script-Name /radicale
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
    proxy_set_header     Host $http_host;
    auth_basic           "Radicale - Password Required";
    auth_basic_user_file /etc/nginx/htpasswd;
}
```

Example **Apache** configuration:

```apache
RewriteEngine On
RewriteRule ^/radicale$ /radicale/ [R,L]

<Location "/radicale/">
    AuthType     Basic
    AuthName     "Radicale - Password Required"
    AuthUserFile "/etc/radicale/htpasswd"
    Require      valid-user

    ProxyPass        http://localhost:5232/ retry=0
    ProxyPassReverse http://localhost:5232/
    RequestHeader    set X-Script-Name /radicale
    RequestHeader    set X-Remote-User expr=%{REMOTE_USER}
</Location>
```

Example **Apache .htaccess** configuration:

```apache
DirectoryIndex disabled
RewriteEngine On
RewriteRule ^(.*)$ http://localhost:5232/$1 [P,L]

AuthType     Basic
AuthName     "Radicale - Password Required"
AuthUserFile "/etc/radicale/htpasswd"
Require      valid-user

# Set to directory of .htaccess file:
RequestHeader set X-Script-Name /radicale
RequestHeader set X-Remote-User expr=%{REMOTE_USER}
```

> **Security:** Untrusted clients should not be able to access the Radicale
> server directly. Otherwise, they can authenticate as any user.

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

## WSGI Server

Radicale is compatible with the WSGI specification.

A configuration file can be set with the `RADICALE_CONFIG` environment
variable, otherwise no configuration file is loaded and the default
configuration is used.

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

## Versioning with Git

This tutorial describes how to keep track of all changes to calendars and
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

# Documentation
## Configuration

Radicale can be configured with a configuration file or with
command line arguments.

An example configuration file looks like:

```ini
[server]
# Bind all addresses
hosts = 0.0.0.0:5232, [::]:5232

[auth]
type = htpasswd
htpasswd_filename = ~/.config/radicale/users
htpasswd_encryption = md5

[storage]
filesystem_folder = ~/.var/lib/radicale/collections
```

Radicale tries to load configuration files from `/etc/radicale/config` and
`~/.config/radicale/config`.
Custom paths can be specified with the `--config /path/to/config` command
line argument or the `RADICALE_CONFIG` environment variable.
Multiple configuration files can be separated by `:` (resp. `;` on Windows).
Paths that start with `?` are optional.

The same example configuration via command line arguments looks like:

```bash
python3 -m radicale --server-hosts 0.0.0.0:5232,[::]:5232 --auth-type htpasswd --auth-htpasswd-filename ~/.config/radicale/users --auth-htpasswd-encryption md5
```

Add the argument `--config ""` to stop Radicale from loading the default
configuration files. Run `python3 -m radicale --help` for more information.

In the following, all configuration categories and options are described.

### server

The configuration options in this category are only relevant in standalone
mode. All options are ignored, when Radicale runs via WSGI.

#### hosts

A comma separated list of addresses that the server will bind to.

Default: `localhost:5232`

#### max_connections

The maximum number of parallel connections. Set to `0` to disable the limit.

Default: `8`

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
authentication plugin that extracts the user name from the certificate.

Default:

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

`none`
: Just allows all usernames and passwords.

`htpasswd`
: Use an
  [Apache htpasswd file](https://httpd.apache.org/docs/current/programs/htpasswd.html)
  to store usernames and passwords.

`remote_user`
: Takes the user name from the `REMOTE_USER` environment variable and disables
  HTTP authentication. This can be used to provide the user name from a WSGI
  server.

`http_x_remote_user`
: Takes the user name from the `X-Remote-User` HTTP header and disables HTTP
  authentication. This can be used to provide the user name from a reverse
  proxy.

Default: `none`

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
  The installation of **radicale[bcrypt]** is required for this.

`md5`
: This uses an iterated md5 digest of the password with a salt.

Default: `md5`

#### delay

Average delay after failed login attempts in seconds.

Default: `1`

#### realm

Message displayed in the client when a password is needed.

Default: `Radicale - Password Required`

### rights
#### type

The backend that is used to check the access rights of collections.

The recommended backend is `owner_only`. If access to calendars
and address books outside the home directory of users (that's `/USERNAME/`)
is granted, clients won't detect these collections and will not show them to
the user. Choosing any other method is only useful if you access calendars and
address books directly via URL.

Available backends:

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
[Rights](#documentation/authentication-and-rights) section.

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

#### max_sync_token_age

Delete sync-token that are older than the specified time. (seconds)

Default: `2592000`

#### hook

Command that is run after changes to storage. Take a look at the
[Versioning with Git](#tutorials/versioning-with-git) tutorial for an example.

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
#### level

Set the logging level.

Available levels: **debug**, **info**, **warning**, **error**, **critical**

Default: `warning`

#### mask_passwords

Don't include passwords in logs.

Default: `True`

### headers

In this section additional HTTP headers that are sent to clients can be
specified.

An example to relax the same-origin policy:

```ini
Access-Control-Allow-Origin = *
```

## Supported Clients

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
(e.g. http://localhost:5232) to create and manage address books and calendars.

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

### Command line

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
$ curl -u user -X DELETE 'http://localhost:5232/user/calendar'
```

## Authentication and Rights

This section describes the format of the rights file for the `from_file`
authentication backend. The configuration option `file` in the `rights`
section must point to the rights file.

The recommended rights method is `owner_only`. If access to calendars
and address books outside the home directory of users (that's `/USERNAME/`)
is granted, clients won't detect these collections and will not show them to
the user.
This is only useful if you access calendars and address books directly via URL.

An example rights file:

```ini
# Allow reading root collection for authenticated users
[root]
user: .+
collection:
permissions: R

# Allow reading and writing principal collection (same as user name)
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
user name and the path of the collection. Permissions from the first
matching section are used. If no section matches, access gets denied.

The user name is empty for anonymous users. Therefore, the regex `.+` only
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

## Storage

This document describes the layout and format of the file system storage
(`multifilesystem` backend).

It's safe to access and manipulate the data by hand or with scripts.
Scripts can be invoked manually, periodically (e.g. with
[cron](https://manpages.debian.org/unstable/cron/cron.8.en.html)) or after each
change to the storage with the configuration option `hook` in the `storage`
section (e.g. [Versioning with Git](#tutorials/versioning-with-git)).

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

Caches and sync-tokens are stored in the `.Radicale.cache` folder inside of
collections.
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

### Manually creating collections

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
address books that are direct children of the path `/USERNAME/`.

Delete collections by deleting the corresponding folders.

## Logging

Radicale logs to `stderr`. The verbosity of the log output can be controlled
with `--debug` command line argument or the `level` configuration option in
the `logging` section.

## Architecture

Radicale is a small piece of software, but understanding it is not as
easy as it seems. But don't worry, reading this short section is enough to
understand what a CalDAV/CardDAV server is, and how Radicale's code is
organized.

### Protocol overview

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

  * CalDAV and CardDAV are superset protocols of WebDAV,
  * WebDAV is a superset protocol of HTTP.

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

The ``radicale`` package offers the following modules.

`__init__`
: Contains the entry point for WSGI.

`__main__`
: Provides the entry point for the ``radicale`` executable and
  includes the command line parser. It loads configuration files from
  the default (or specified) paths and starts the internal server.

`app`
: This is the core part of Radicale, with the code for the CalDAV/CardDAV
  server. The code managing the different HTTP requests according to the
  CalDAV/CardDAV specification can be found here.

`auth`
: Used for authenticating users based on username and password, mapping
  usernames to internal users and optionally retrieving credentials from
  the environment.

`config`
: Contains the code for managing configuration and loading settings from files.

`ìtem`
: Internal representation of address book and calendar entries. Based on
  [VObject](https://eventable.github.io/vobject/).

`log`
: The logger for Radicale based on the default Python logging module.

`rights`
: This module is used by Radicale to manage access rights to collections,
  address books and calendars.

`server`
: The integrated HTTP server for standalone use.

`storage`
: This module contains the classes representing collections in Radicale and
  the code for storing and loading them in the filesystem.

`web`
: This module contains the web interface.

`utils`
: Contains general helper functions.

`httputils`
: Contains helper functions for working with HTTP.

`pathutils`
: Helper functions for working with paths and the filesystem.

`xmlutils`
: Helper functions for working with the XML part of CalDAV/CardDAV requests
  and responses. It's based on the ElementTree XML API.

## Plugins

Radicale can be extended by plugins for authentication, rights management and
storage. Plugins are **python** modules.

### Getting started

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

    def login(self, login, password):
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

### Authentication plugins

This plugin type is used to check login credentials.
The module must contain a class `Auth` that extends
`radicale.auth.BaseAuth`. Take a look at the file `radicale/auth/__init__.py`
in Radicale's source code for more information.

### Rights management plugins

This plugin type is used to check if a user has access to a path.
The module must contain a class `Rights` that extends
`radicale.rights.BaseRights`. Take a look at the file
`radicale/rights/__init__.py` in Radicale's source code for more information.

### Web plugins

This plugin type is used to provide the web interface for Radicale.
The module must contain a class `Web` that extends
`radicale.web.BaseWeb`. Take a look at the file `radicale/web/__init__.py` in
Radicale's source code for more information.

### Storage plugins

This plugin is used to store collections and items.
The module must contain a class `Storage` that extends
`radicale.storage.BaseStorage`. Take a look at the file
`radicale/storage/__init__.py` in Radicale's source code for more information.

# Contribute

### Chat with Us on IRC

Want to say something? Join our IRC room: `##kozea` on Freenode.

### Report Bugs

Found a bug? Want a new feature? Report a new issue on the
[Radicale bug-tracker](https://github.com/Kozea/Radicale/issues).

### Hack

Interested in hacking? Feel free to clone the
[git repository on GitHub](https://github.com/Kozea/Radicale) if you want to
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

    $ python3 -m pip install --upgrade https://github.com/Kozea/Radicale/archive/master.tar.gz

You can also download the content of the repository as an
[archive](https://github.com/Kozea/Radicale/tarball/master).

### Source Packages

You can find the source packages of all releases on
[GitHub](https://github.com/Kozea/Radicale/releases).

### Linux Distribution Packages

Radicale has been packaged for:

  * [ArchLinux](https://www.archlinux.org/packages/community/any/radicale/) by
    David Runge
  * [Debian](http://packages.debian.org/radicale) by Jonas Smedegaard
  * [Gentoo](https://packages.gentoo.org/packages/www-apps/radicale)
    by René Neumann, Maxim Koltsov and Manuel Rüger
  * [Fedora/RHEL/CentOS](https://src.fedoraproject.org/rpms/radicale) by Jorti and Peter Bieringer
  * [Mageia](http://madb.mageia.org/package/show/application/0/name/radicale)
    by Jani Välimaa
  * [OpenBSD](http://openports.se/productivity/radicale) by Sergey Bronnikov,
    Stuart Henderson and Ian Darwin
  * [openSUSE](http://software.opensuse.org/package/Radicale?search_term=radicale)
    by Ákos Szőts and Rueckert
  * [PyPM](http://code.activestate.com/pypm/radicale/)
  * [Slackware](http://schoepfer.info/slackware.xhtml#packages-network) by
    Johannes Schöpfer
  * [Trisquel](http://packages.trisquel.info/search?searchon=names&keywords=radicale)
  * [Ubuntu](http://packages.ubuntu.com/radicale) by the MOTU and Jonas
    Smedegaard

Radicale is also
[available on Cloudron](https://cloudron.io/button.html?app=org.radicale.cloudronapp2)
and has a Dockerfile.

If you are interested in creating packages for other Linux distributions, read
the ["Contribute" section](#contribute).

# About

### Main Goals

Radicale is a complete calendar and contact storing and manipulating
solution. It can store multiple calendars and multiple address books.

Calendar and contact manipulation is available from both local and distant
accesses, possibly limited through authentication policies.

It aims to be a lightweight solution, easy to use, easy to install, easy to
configure. As a consequence, it requires few software dependencies and is
preconfigured to work out-of-the-box.

Radicale is written in Python. It runs on most of the UNIX-like platforms
(Linux, \*BSD, macOS) and Windows. It is free and open-source software.

### What Radicale Will Never Be

Radicale is a server, not a client. No interfaces will be created to work with
the server.

CalDAV and CardDAV are not perfect protocols. We think that their main problem
is their complexity, that is why we decided not to implement the whole standard
but just enough to understand some of its client-side implementations.

CalDAV and CardDAV are the best open standards available, and they are quite
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
much more respectful of CalDAV and CardDAV and can be used with many clients.
They are very good choices if you want to develop and test new CalDAV clients,
or if you have a possibly heterogeneous list of user agents.

Even if it tries it best to follow the RFCs, Radicale does not and **will not**
blindly implement the CalDAV and CardDAV standards. It is mainly designed to
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
[tutorial](#tutorials/simple-5-minute-setup).

#### Lazy

The CalDAV RFC defines what must be done, what can be done and what cannot be
done. Many violations of the protocol are totally defined and behaviors are
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
