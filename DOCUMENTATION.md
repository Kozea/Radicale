# Documentation

## Getting started

#### About Radicale

Radicale is a small but powerful CalDAV (calendars, to-do lists) and CardDAV
(contacts) server, that:

* Shares calendars and contact lists through CalDAV, CardDAV and HTTP.
* Supports events, todos, journal entries and business cards.
* Works out-of-the-box, no complicated setup or configuration required.
* Offers flexible authentication options.
* Can limit access by authorization.
* Can secure connections with TLS.
* Works with many
  [CalDAV and CardDAV clients](#supported-clients).
* Stores all data on the file system in a simple folder structure.
* Can be extended with plugins.
* Is GPLv3-licensed free software.

#### Installation

Check

* [Tutorials](#tutorials)
* [Documentation](#documentation-1)
* [Wiki on GitHub](https://github.com/Kozea/Radicale/wiki)
* [Discussions on GitHub](https://github.com/Kozea/Radicale/discussions)
* [Open and already Closed Issues on GitHub](https://github.com/Kozea/Radicale/issues?q=is%3Aissue)

#### What's New?

Read the [Changelog on GitHub](https://github.com/Kozea/Radicale/blob/master/CHANGELOG.md).

## Tutorials

### Simple 5-minute setup

You want to try Radicale but only have 5 minutes free in your calendar?
Let's go right now and play a bit with Radicale!

The server, configured with settings from this section, only binds to localhost
(i.e. it is not reachable over the network), and you can log in with any username and password.
When everything works, you may get a local [client](#supported-clients)
and start creating calendars and address books.
If Radicale fits your needs, it may be time for some [basic configuration](#basic-configuration)
to support remote clients and desired authentication type.

Follow one of the chapters below depending on your operating system.

#### Linux / \*BSD

Hint: instead of downloading from PyPI, look for packages provided by your [distribution](#linux-distribution-packages).
They contain also startup scripts integrated into your distributions, that allow Radicale to run daemonized.

First, make sure that **python** 3.9 or later and **pip** are installed. On most distributions it should be
enough to install the package ``python3-pip``.

##### as normal user

Recommended only for testing - open a console and type:

```bash
# Run the following command to only install for the current user
python3 -m pip install --user --upgrade https://github.com/Kozea/Radicale/archive/master.tar.gz
```

If _install_ is not working and instead `error: externally-managed-environment` is displayed,
create and activate a virtual environment in advance.

```bash
python3 -m venv ~/venv
source ~/venv/bin/activate
```

and try to install with

```bash
python3 -m pip install --upgrade https://github.com/Kozea/Radicale/archive/master.tar.gz
```

Start the service manually, data is stored only for the current user

```bash
# Start, data is stored for the current user only
python3 -m radicale --storage-filesystem-folder=~/.var/lib/radicale/collections --auth-type none
```

##### as system user (or as root)

Alternatively, you can install and run as system user or as root (not recommended):

```bash
# Run the following command as root (not recommended) or non-root system user
# (the later may require --user in case dependencies are not available system-wide and/or virtual environment)
python3 -m pip install --upgrade https://github.com/Kozea/Radicale/archive/master.tar.gz
```

Start the service manually, with data stored in a system folder under `/var/lib/radicale/collections`:

```bash
# Start, data is stored in a system folder (requires write permissions to /var/lib/radicale/collections)
python3 -m radicale --storage-filesystem-folder=/var/lib/radicale/collections --auth-type none
```

#### Windows

The first step is to install Python. Go to
[python.org](https://python.org) and download the latest version of Python 3.
Then run the installer.
On the first window of the installer, check the "Add Python to PATH" box and
click on "Install now". Wait a couple of minutes, it's done!

Launch a command prompt and type:

```powershell
python -m pip install --upgrade https://github.com/Kozea/Radicale/archive/master.tar.gz
python -m radicale --storage-filesystem-folder=~/radicale/collections --auth-type none
```

##### Common

Success!!! Open <http://localhost:5232> in your browser!
You can log in with any username and password as no authentication is required by example option `--auth-type none`.
This is **INSECURE**, see [Configuration/Authentication](#auth) for more details.

Just note that default configuration for security reason binds the server to `localhost` (IPv4: `127.0.0.1`, IPv6: `::1`).
See [Addresses](#addresses) and [Configuration/Server](#server) for more details.

### Basic Configuration

Installation instructions can be found in the
[simple 5-minute setup](#simple-5-minute-setup) tutorial.

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
[Configuration](#configuration) section.

#### Authentication

In its default configuration since version 3.5.0, Radicale rejects all
authentication attempts by using config option `type = denyall` (introduced
with 3.2.2) as default until explicitly configured.

Versions before 3.5.0 did not check usernames or passwords at all, unless explicitly configured.
If such a server is reachable over a network, you should change this as soon as possible.

First a `users` file with all usernames and passwords must be created.
It can be stored in the same directory as the configuration file.

##### The secure way

The `users` file can be created and managed with
[htpasswd](https://httpd.apache.org/docs/current/programs/htpasswd.html):

Note: some OSes or distributions contain outdated versions of `htpasswd` (< 2.4.59) without
support for SHA-256 or SHA-512 (e.g. Ubuntu LTS 22).
In these cases, use `htpasswd`'s command line option `-B` for the  `bcrypt` hash method (recommended),
or stay with the insecure (not recommended) MD5 (default) or SHA-1 (command line option `-s`).

Note: support of SHA-256 and SHA-512 was introduced with 3.1.9

```bash
# Create a new htpasswd file with the user "user1" using SHA-512 as hash method
$ htpasswd -5 -c /path/to/users user1
New password:
Re-type new password:
# Add another user
$ htpasswd -5 /path/to/users user2
New password:
Re-type new password:
```

Authentication can be enabled with the following configuration:

```ini
[auth]
type = htpasswd
htpasswd_filename = /path/to/users
htpasswd_encryption = autodetect
```

##### The simple but insecure way

Create the `users` file by hand with lines containing the username and
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

#### Addresses

The default configuration binds the server to localhost. It cannot be reached
from other computers. This can be changed with the following configuration
options (IPv4 and IPv6):

```ini
[server]
hosts = 0.0.0.0:5232, [::]:5232
```

#### Storage

Data is stored in the folder `/var/lib/radicale/collections`. The path can
be changed with the following configuration:

```ini
[storage]
filesystem_folder = /path/to/storage
```

> **Security:** The storage folder shall not be readable by unauthorized users.
> Otherwise, they can read the calendar data and lock the storage.
> You can find OS dependent instructions in the
> [Running as a service](#running-as-a-service) section.

#### Limits

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

#### Linux with systemd system-wide

Recommendation: check support by [Linux Distribution Packages](#linux-distribution-packages)
instead of manual setup / initial configuration.

Create the **radicale** user and group for the Radicale service by running (as `root`:
```bash
useradd --system --user-group --home-dir / --shell /sbin/nologin radicale
```

The storage folder must be made writable by the **radicale** user by running (as `root`):
```bash
mkdir -p /var/lib/radicale/collections && chown -R radicale:radicale /var/lib/radicale/collections
```

If a dedicated cache folder is configured (see option [filesystem_cache_folder](#filesystem_cache_folder)),
it also must be made writable by **radicale**. To achieve that, run (as `root`):
```bash
mkdir -p /var/cache/radicale && chown -R radicale:radicale /var/cache/radicale
````

> **Security:** The storage shall not be readable by others.
> To make sure this is the case, run (as `root`):
> ```bash
> chmod -R o= /var/lib/radicale/collections
> ```

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
ReadWritePaths=/var/lib/radicale/
# Replace with following in case dedicated cache folder should be used
#ReadWritePaths=/var/lib/radicale/ /var/cache/radicale/

[Install]
WantedBy=multi-user.target
```

In this system-wide implementation, Radicale will load the configuration from the file `/etc/radicale/config`.

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

In this user-specific configuration, Radicale will load the configuration from
the file `~/.config/radicale/config`.
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

#### Windows with "NSSM - the Non-Sucking Service Manager"

First install [NSSM](https://nssm.cc/) and start `nssm install` in a command
prompt. Apply the following configuration:

* Service name: `Radicale`
* Application
  * Path: `C:\Path\To\Python\python.exe`
  * Arguments: `--config C:\Path\To\Config`
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

### Reverse Proxy

When a reverse proxy is used, and Radicale should be made available at a path
below the root (such as `/radicale/`), then this path must be provided via
the `X-Script-Name` header (without a trailing `/`). The proxy must remove
the location from the URL path that is forwarded to Radicale. If Radicale
should be made available at the root of the web server (in the nginx case
using `location /`), then the setting of the `X-Script-Name` header should be
removed from the example below.

Example **nginx** configuration extension:

See also for latest examples: https://github.com/Kozea/Radicale/tree/master/contrib/nginx/

```nginx
location /radicale/ { # The trailing / is important!
    proxy_pass        http://localhost:5232;
    proxy_set_header  X-Script-Name /radicale;
    proxy_set_header  X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header  X-Forwarded-Host $host;
    proxy_set_header  X-Forwarded-Port $server_port;
    proxy_set_header  X-Forwarded-Proto $scheme;
    proxy_set_header  Host $http_host;
    proxy_pass_header Authorization;
}
```

Example **Caddy** configuration extension:

See also for latest examples: https://github.com/Kozea/Radicale/tree/master/contrib/caddy/

```
handle_path /radicale/* {
    uri strip_prefix /radicale
    reverse_proxy localhost:5232 {
    }
}
```

Example **Apache** configuration extension:

See also for latest examples: https://github.com/Kozea/Radicale/tree/master/contrib/apache/

```apache
RewriteEngine On
RewriteRule ^/radicale$ /radicale/ [R,L]

<Location "/radicale/">
    ProxyPass        http://localhost:5232/ retry=0
    ProxyPassReverse http://localhost:5232/
    RequestHeader    set X-Script-Name /radicale
    RequestHeader    set X-Forwarded-Port "%{SERVER_PORT}s"
    RequestHeader    set X-Forwarded-Proto expr=%{REQUEST_SCHEME}
    <IfVersion >= 2.4.40>
    Proxy100Continue Off
    </IfVersion>
</Location>
```

Example **Apache .htaccess** configuration:

```apache
DirectoryIndex disabled
RewriteEngine On
RewriteRule ^(.*)$ http://localhost:5232/$1 [P,L]

# Set to directory of .htaccess file:
RequestHeader set X-Script-Name /radicale
RequestHeader set X-Forwarded-Port "%{SERVER_PORT}s"
RequestHeader unset X-Forwarded-Proto
<If "%{HTTPS} =~ /on/">
RequestHeader set X-Forwarded-Proto "https"
</If>
```

Example **lighttpd** configuration:

```lighttpd
server.modules += ( "mod_proxy" , "mod_setenv", "mod_rewrite" )

$HTTP["url"] =~ "^/radicale/" {
  proxy.server = ( "" => (( "host" => "127.0.0.1", "port" => "5232" )) )
  proxy.header = ( "map-urlpath" => ( "/radicale/" => "/" ))

  setenv.add-request-header = (
    "X-Script-Name" => "/radicale",
    "Script-Name" => "/radicale",
  )
  url.rewrite-once = ( "^/radicale/radicale/(.*)" => "/radicale/$1" )
}
```

Be reminded that Radicale's default configuration enforces limits on the
maximum number of parallel connections, the maximum file size and the rate of
incorrect authentication attempts. Connections are terminated after a timeout.

#### Manage user accounts with the reverse proxy

Set the configuration option `type` in the `auth` section to
`http_x_remote_user`.
Radicale uses the username provided in the `X-Remote-User` HTTP header and
disables its internal HTTP authentication.

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

Example **Caddy** configuration:

```
handle_path /radicale/* {
    uri strip_prefix /radicale
    basicauth {
        USER HASH
    }
    reverse_proxy localhost:5232 {
        header_up X-Script-Name /radicale
        header_up X-remote-user {http.auth.user.id}
    }
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
    <IfVersion >= 2.4.40>
    Proxy100Continue Off
    </IfVersion>
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
> server directly. Otherwise, they can authenticate as any user by simply
> setting related HTTP header. This can be prevented by listening to the
> loopback interface only or local firewall rules.

#### Secure connection between Radicale and the reverse proxy

SSL certificates can be used to encrypt and authenticate the connection between
Radicale and the reverse proxy. First you need to generate a certificate for
Radicale and a certificate for the reverse proxy. The following commands
generate self-signed certificates. You will be asked to enter additional
information about the certificate, these values do not really matter, and you can
keep the defaults.

```bash
openssl req -x509 -newkey rsa:4096 -keyout server_key.pem -out server_cert.pem \
        -nodes -days 9999
openssl req -x509 -newkey rsa:4096 -keyout client_key.pem -out client_cert.pem \
        -nodes -days 9999
```

Use the following configuration for Radicale:

```ini
[server]
ssl = True
certificate = /path/to/server_cert.pem
key = /path/to/server_key.pem
certificate_authority = /path/to/client_cert.pem
```

If you are using the Let's Encrypt Certbot, the configuration should look similar to this:

```ini
[server]
ssl = True
certificate = /etc/letsencrypt/live/{Your Domain}/fullchain.pem
key = /etc/letsencrypt/live/{Your Domain}/privkey.pem
```

Example **nginx** configuration:

```nginx
location /radicale/ {
    proxy_pass https://localhost:5232/;
    ...
    # Place the files somewhere nginx is allowed to access (e.g. /etc/nginx/...).
    proxy_ssl_certificate         /path/to/client_cert.pem;
    proxy_ssl_certificate_key     /path/to/client_key.pem;
}
```

### WSGI Server

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
gunicorn --bind '127.0.0.1:5232' --env 'RADICALE_CONFIG=/etc/radicale/config' \
         --workers 8 radicale
```

#### Manage user accounts with the WSGI server

Set the configuration option `type` in the `auth` section to `remote_user`.
This way Radicale uses the username provided by the WSGI server and disables
its internal authentication over HTTP.

### Versioning collections with Git

This tutorial describes how to keep track of all changes to calendars and
address books with **git** (or any other version control system).

The repository must be initialized in the collection base directory
of the user running `radicale` daemon.

```bash
## assuming "radicale" user is starting "radicale" service
# change to user "radicale"
su -l -s /bin/bash radicale

# change to collection base directory defined in [storage] -> filesystem_folder
#  assumed here /var/lib/radicale/collections
cd /var/lib/radicale/collections

# initialize git repository
git init

# set user and e-mail, here minimum example
git config user.name "$USER"
git config user.email "$USER@$HOSTNAME"

# define ignore of cache/lock/tmp files
cat <<'END' >.gitignore
.Radicale.cache
.Radicale.lock
.Radicale.tmp-*
END
```

The configuration option `hook` in the `storage` section must be set to
the following command:

```bash
git add -A && (git diff --cached --quiet || git commit -m "Changes by \"%(user)s\"")
```

The command gets executed after every change to the storage and commits
the changes into the **git** repository.

Log of `git` can be investigated using

```bash
su -l -s /bin/bash radicale
cd /var/lib/radicale/collections
git log
```

In case of problems, make sure you run radicale with ``--debug`` switch and
inspect the log output. For more information, please visit
[section on logging](#logging-overview).

Reason for problems can be
 - SELinux status -> check related audit log
 - problematic file/directory permissions
 - command is not fond or cannot be executed or argument problem

## Documentation

### Configuration

Radicale can be configured with a configuration file or with
command line arguments.

Configuration files have INI-style syntax comprising key-value pairs
grouped into sections with section headers enclosed in brackets.

An example configuration file looks like:

```ini
[server]
# Bind all addresses
hosts = 0.0.0.0:5232, [::]:5232

[auth]
type = htpasswd
htpasswd_filename = ~/.config/radicale/users
htpasswd_encryption = autodetect

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
python3 -m radicale --server-hosts 0.0.0.0:5232,[::]:5232 \
        --auth-type htpasswd --auth-htpasswd-filename ~/.config/radicale/users \
        --auth-htpasswd-encryption autodetect
```

Add the argument `--config ""` to stop Radicale from loading the default
configuration files. Run `python3 -m radicale --help` for more information.

You can also use command-line options in startup scripts as shown in the following examples:

```bash
## simple variable containing multiple options
RADICALE_OPTIONS="--logging-level=debug --config=/etc/radicale/config --logging-request-header-on-debug --logging-rights-rule-doesnt-match-on-debug"
/usr/bin/radicale $RADICALE_OPTIONS

## variable as array method #1
RADICALE_OPTIONS=("--logging-level=debug" "--config=/etc/radicale/config" "--logging-request-header-on-debug" "--logging-rights-rule-doesnt-match-on-debug")
/usr/bin/radicale ${RADICALE_OPTIONS[@]}

## variable as array method #2
RADICALE_OPTIONS=()
RADICALE_OPTIONS+=("--logging-level=debug")
RADICALE_OPTIONS+=("--config=/etc/radicale/config")
/usr/bin/radicale ${RADICALE_OPTIONS[@]}
```

The following describes all configuration sections and options.

#### [server]

The configuration options in this section are only relevant in standalone
mode; they are ignored, when Radicale runs on WSGI.

##### hosts

A comma separated list of addresses that the server will bind to.

Default: `localhost:5232`

##### max_connections

The maximum number of parallel connections. Set to `0` to disable the limit.

Default: `8`

##### max_content_length

The maximum size of the request body. (bytes)

Default: `100000000`

In case of using a reverse proxy in front of check also there related option

##### timeout

Socket timeout. (seconds)

Default: `30`

##### ssl

Enable transport layer encryption.

Default: `False`

##### certificate

Path of the SSL certificate.

Default: `/etc/ssl/radicale.cert.pem`

##### key

Path to the private key for SSL. Only effective if `ssl` is enabled.

Default: `/etc/ssl/radicale.key.pem`

##### certificate_authority

Path to the CA certificate for validating client certificates. This can be used
to secure TCP traffic between Radicale and a reverse proxy. If you want to
authenticate users with client-side certificates, you also have to write an
authentication plugin that extracts the username from the certificate.

Default: (unset)

##### protocol

_(>= 3.3.1)_

Accepted SSL protocol (maybe not all supported by underlying OpenSSL version)
Example for secure configuration: ALL -SSLv3 -TLSv1 -TLSv1.1
Format: Apache SSLProtocol list (from "mod_ssl")

Default: (system default)

##### ciphersuite

_(>= 3.3.1)_

Accepted SSL ciphersuite (maybe not all supported by underlying OpenSSL version)
Example for secure configuration: DHE:ECDHE:-NULL:-SHA
Format: OpenSSL cipher list (see also "man openssl-ciphers")

Default: (system-default)

##### script_name

_(>= 3.5.0)_

Strip script name from URI if called by reverse proxy

Default: (taken from HTTP_X_SCRIPT_NAME or SCRIPT_NAME)

#### [encoding]

##### request

Encoding for responding requests.

Default: `utf-8`

##### stock

Encoding for storing local collections

Default: `utf-8`

#### [auth]

##### type

The method to verify usernames and passwords.

Available types are:

* `none`  
  Just allows all usernames and passwords.

* `denyall`  _(>= 3.2.2)_  
  Just denies all usernames and passwords.

* `htpasswd`  
  Use an
  [Apache htpasswd file](https://httpd.apache.org/docs/current/programs/htpasswd.html)
  to store usernames and passwords.

* `remote_user`  
  Takes the username from the `REMOTE_USER` environment variable and disables
  Radicale's internal HTTP authentication. This can be used to provide the
  username from a WSGI server which authenticated the client upfront.
  Requires validation, otherwise clients can supply the header themselves,
  which then is unconditionally trusted.

* `http_x_remote_user`  
  Takes the username from the `X-Remote-User` HTTP header and disables
  Radicale's internal HTTP authentication. This can be used to provide the
  username from a reverse proxy which authenticated the client upfront.
  Requires validation, otherwise clients can supply the header themselves,
  which then is unconditionally trusted.

* `ldap` _(>= 3.3.0)_  
  Use a LDAP or AD server to authenticate users by relaying credentials from clients and handle results.

* `dovecot` _(>= 3.3.1)_  
  Use a Dovecot server to authenticate users by relaying credentials from clients and handle results.

* `imap` _(>= 3.4.1)_  
  Use an IMAP server to authenticate users by relaying credentials from clients and handle results.

* `oauth2` _(>= 3.5.0)_  
  Use an OAuth2 server to authenticate users by relaying credentials from clients and handle results.
  OAuth2 authentication (SSO) directly on client is not supported. Use herefore `http_x_remote_user`
  in combination with SSO support in reverse proxy (e.g. Apache+mod_auth_openidc).

* `pam` _(>= 3.5.0)_  
  Use local PAM to authenticate users by relaying credentials from client and handle result..

Default: `none` _(< 3.5.0)_ / `denyall` _(>= 3.5.0)_

##### cache_logins

_(>= 3.4.0)_

Cache successful/failed logins until expiration time. Enable this to avoid
overload of authentication backends.

Default: `False`

##### cache_successful_logins_expiry

_(>= 3.4.0)_

Expiration time of caching successful logins in seconds

Default: `15`

##### cache_failed_logins_expiry

_(>= 3.4.0)_

Expiration time of caching failed logins in seconds

Default: `90`

##### htpasswd_filename

Path to the htpasswd file.

Default: `/etc/radicale/users`

##### htpasswd_encryption

The encryption method that is used in the htpasswd file. Use
[htpasswd](https://httpd.apache.org/docs/current/programs/htpasswd.html)
or similar to generate this file.

Available methods:

* `plain`  
  Passwords are stored in plaintext.
  This is not recommended. as it is obviously **insecure!**
  The htpasswd file for this can be created by hand and looks like:

  ```htpasswd
  user1:password1
  user2:password2
  ```

* `bcrypt`  
  This uses a modified version of the Blowfish stream cipher, which is considered very secure.
  The installation of Python's **bcrypt** module is required for this to work.

* `md5`  
  Use an iterated MD5 digest of the password with salt (nowadays insecure).

* `sha256` _(>= 3.1.9)_  
  Use an iterated SHA-256 digest of the password with salt.

* `sha512` _(>= 3.1.9)_  
  Use an iterated SHA-512 digest of the password with salt.

* `argon2` _(>= 3.5.3)_  
  Use an iterated ARGON2 digest of the password with salt.
  The installation of Python's **argon2-cffi** module is required for this to work.

* `autodetect` _(>= 3.1.9)_  
  Automatically detect the encryption method used per user entry.

Default: `md5` _(< 3.3.0)_ / `autodetect` _(>= 3.3.0)_

##### htpasswd_cache

_(>= 3.4.0)_

Enable caching of htpasswd file based on size and mtime_ns

Default: `False`

##### delay

Average delay (in seconds) after failed login attempts.

Default: `1`

##### realm

Message displayed in the client when a password is needed.

Default: `Radicale - Password Required`

##### ldap_uri

_(>= 3.3.0)_

URI to the LDAP server.
Mandatory for auth type `ldap`.

Default: `ldap://localhost`

##### ldap_base

_(>= 3.3.0)_

Base DN of the LDAP server.
Mandatory for auth type `ldap`.

Default: (unset)

##### ldap_reader_dn

_(>= 3.3.0)_

DN of a LDAP user with read access users and - if defined - groups.
Mandatory for auth type `ldap`.

Default: (unset)

##### ldap_secret

_(>= 3.3.0)_

Password of `ldap_reader_dn`.
Mandatory for auth type `ldap` unless `ldap_secret_file` is given.

Default: (unset)

##### ldap_secret_file

_(>= 3.3.0)_

Path to the file containing the password of `ldap_reader_dn`.
Mandatory for auth type `ldap` unless `ldap_secret` is given.

Default: (unset)

##### ldap_filter

_(>= 3.3.0)_

Filter to search for the LDAP entry of the user to authenticate.
It must contain '{0}' as placeholder for the login name.

Default: `(cn={0})`

##### ldap_user_attribute

_(>= 3.4.0)_

LDAP attribute whose value shall be used as the username after successful authentication.

If set, you can use flexible logins in `ldap_filter` and still have consolidated usernames,
e.g. to allow users to login using mail addresses as an alternative to cn, simply set
```ini
ldap_filter = (&(objectclass=inetOrgPerson)(|(cn={0})(mail={0})))
ldap_user_attribute = cn
```
Even for simple filter setups, it is recommended to set it in order to get usernames exactly
as they are stored in LDAP and to avoid inconsistencies in the upper-/lower-case spelling of the
login names.

Default: (unset, in which case the login name is directly used as the username)

##### ldap_use_ssl

_(>= 3.3.0)_

Use ssl on the LDAP connection. **Deprecated!** Use `ldap_security` instead.

##### ldap_security

_(>= 3.5.2)_

Use encryption on the LDAP connection.

One of
* `none`
* `tls`
* `starttls`

Default: `none`

##### ldap_ssl_verify_mode

_(>= 3.3.0)_

Certificate verification mode for tls and starttls.

One of
* `NONE`
* `OPTIONAL`
* `REQUIRED`.

Default: `REQUIRED`

##### ldap_ssl_ca_file

_(>= 3.3.0)_

Path to the CA file in PEM format which is used to certify the server certificate

Default: (unset)

##### ldap_groups_attribute

_(>= 3.4.0)_

LDAP attribute in the authenticated user's LDAP entry to read the group memberships from.

E.g. `memberOf` to get groups on Active Directory and alikes, `groupMembership` on Novell eDirectory, ...

If set, get the user's LDAP groups from the attribute given.

For DN-valued attributes, the value of the RDN is used to determine the group names.
The implementation also supports non-DN-valued attributes: their values are taken directly.

The user's group names can be used later to define rights.
They also give you access to the group calendars, if those exist.
* Group calendars are placed directly under *collection_root_folder*`/GROUPS/`
  with the base64-encoded group name as the calendar folder name.
* Group calendar folders are not created automatically.
  This must be done manually. In the [LDAP-authentication section of Radicale's wiki](https://github.com/Kozea/Radicale/wiki/LDAP-authentication) you can find a script to create a group calendar.

Default: (unset)

##### ldap_group_members_attribute

_(>= 3.5.6)_

Attribute in the group entries to read the group's members from.

E.g. `member` for groups with objectclass `groupOfNames`.

Using `ldap_group_members_attribute`, `ldap_group_base` and `ldap_group_filter` is an alternative
approach to getting the user's groups. Instead of reading them from `ldap_groups_attribute`
in the user's entry, an additional query is performed to seach for those groups beneath `ldap_group_base`,
that have the user's DN in their `ldap_group_members_attribute` and additionally fulfil `ldap_group_filter`.

As with DN-valued `ldap_groups_attribute`, the value of the RDN is used to determine the group names.

Default: (unset)

##### ldap_group_base

_(>= 3.5.6)_

Base DN to search for groups.
Only necessary if `ldap_group_members_attribute` is set, and if the base DN for groups differs from `ldap_base`.

Default: (unset, in which case `ldap_base` is used as fallback)

##### ldap_group_filter

_(>= 3.5.6)_

Search filter to search for groups having the user DN found as member.
Only necessary `ldap_group_members_attribute` is set, and you want the groups returned to be restricted
instead of all groups the user's DN is in.

Default: (unset)

##### ldap_ignore_attribute_create_modify_timestamp

_(>= 3.5.1)_

Quirks for Authentik LDAP server, which violates the LDAP RFCs:
add modifyTimestamp and createTimestamp to the exclusion list of internal ldap3 client
so that these schema attributes are not checked.

Default: `False`

##### dovecot_connection_type

_(>= 3.4.1)_

Connection type for dovecot authentication.

One of:
* `AF_UNIX`
* `AF_INET`
* `AF_INET6`

Note: credentials are transmitted in cleartext

Default: `AF_UNIX`

##### dovecot_socket

_(>= 3.3.1)_

Path to the Dovecot client authentication socket (eg. /run/dovecot/auth-client on Fedora).
Radicale must have read & write access to the socket.

Default: `/var/run/dovecot/auth-client`

##### dovecot_host

_(>= 3.4.1)_

Host of dovecot socket exposed via network

Default: `localhost`

##### dovecot_port

_(>= 3.4.1)_

Port of dovecot socket exposed via network

Default: `12345`

##### remote_ip_source

_(>= 3.5.6)_

For authentication mechanisms that are made aware of the remote IP
(such as dovecot via the `rip=` auth protocol parameter), determine
the source to use. Currently, valid values are

`REMOTE_ADDR` (default)
: Use the REMOTE_ADDR environment variable that captures the remote
  address of the socket connection.

`X-Remote-Addr`
: Use the `X-Remote-Addr` HTTP header value.

In the case of `X-Remote-Addr`, Radicale must be running be running
behind a proxy that you control and that sets/overwrites the
`X-Remote-Addr` header (doesn't pass it) so that the value passed
to dovecot is reliable. For example, for nginx, add

```
    proxy_set_header  X-Remote-Addr $remote_addr;
```

to the configuration sample.

Default: `REMOTE_ADDR`

##### imap_host

_(>= 3.4.1)_

IMAP server hostname.

One of:
* address
* address:port
* [address]:port	(for IPv5 addresses)
* imap.server.tld

Default: `localhost`

##### imap_security

_(>= 3.4.1)_

Secure the IMAP connection:

One of:
* `tls`
* `starttls`
* `none`

Default: `tls`

##### oauth2_token_endpoint

_(>= 3.5.0)_

Endpoint URL for the OAuth2 token

Default: (unset)

##### pam_service

_(>= 3.5.0)_

PAM service name

Default: `radicale`

##### pam_group_membership

_(>= 3.5.0)_

PAM group user should be member of

Default: (unset)

##### lc_username

Сonvert username to lowercase.
Recommended to be `True` for case-insensitive auth providers like ldap, kerberos, ...

Default: `False`

Notes:
* `lc_username` and `uc_username` are mutually exclusive
* for auth type `ldap` the use of `ldap_user_attribute` is preferred over `lc_username`

##### uc_username

_(>= 3.3.2)_

Сonvert username to uppercase.
Recommended to be `True` for case-insensitive auth providers like ldap, kerberos, ...

Default: `False`

Notes:
* `uc_username` and `lc_username` are mutually exclusive
* for auth type `ldap` the use of `ldap_user_attribute` is preferred over `uc_username`

##### strip_domain

_(>= 3.2.3)_

Strip domain from username

Default: `False`

##### urldecode_username

_(>= 3.5.3)_

URL-decode the username.
If the username is an email address, some clients send the username URL-encoded
(notably iOS devices) breaking the authentication process
(user@example.com becomes user%40example.com).
This setting forces decoding the username.

Default: `False`


#### [rights]

##### type

Authorization backend that is used to check the access rights to collections.

The default and recommended backend is `owner_only`. If access to calendars
and address books outside the user's collection directory (that's `/username/`)
is granted, clients will not detect these collections automatically and
will not show them to the users.
Choosing any other authorization backend is only useful if you access
calendars and address books directly via URL.

Available backends are:

* `authenticated`  
  Authenticated users can read and write everything.

* `owner_only`  
  Authenticated users can read and write their own collections under the path
  */USERNAME/*.

* `owner_write`  
  Authenticated users can read everything and write their own collections under
  the path */USERNAME/*.

* `from_file`  
  Load the rules from a file.

Default: `owner_only`

##### file

Name of the file containing the authorization rules for the `from_file` backend.
See the [Rights](#authorization-and-rights) section for details.

Default: `/etc/radicale/rights`

##### permit_delete_collection

_(>= 3.1.9)_

Global permission to delete complete collections.
* If `False` it can be explicitly granted per collection by `permissions: D`
* If `True` it can be explicitly forbidden per collection by `permissions: d`

Default: `True`

##### permit_overwrite_collection

_(>= 3.3.0)_

Global permission to overwrite complete collections.
* If `False` it can be explicitly granted per collection by `permissions: O`
* If `True` it can be explicitly forbidden per collection by `permissions: o`

Default: `True`

#### [storage]

##### type

Backend used to store data.

Available backends are:

* `multifilesystem`  
  Stores the data in the filesystem.

* `multifilesystem_nolock`  
  The `multifilesystem` backend without file-based locking.
  Must only be used with a single process.

Default: `multifilesystem`

##### filesystem_folder

Folder for storing local collections; will be auto-created if not present.

Default: `/var/lib/radicale/collections`

##### filesystem_cache_folder

_(>= 3.3.2)_

Folder for storing cache of local collections; will be auto-created if not present

Default: (filesystem_folder)

Note: only used if use_cache_subfolder_* options are active

Note: can be used on multi-instance setup to cache files on local node (see below)

##### use_cache_subfolder_for_item

_(>= 3.3.2)_

Use subfolder `collection-cache` for cache file structure of 'item' instead of inside collection folders, created if not present

Default: `False`

Note: can be used on multi-instance setup to cache 'item' on local node

##### use_cache_subfolder_for_history

_(>= 3.3.2)_

Use subfolder `collection-cache` for cache file structure of 'history' instead of inside collection folders, created if not present

Default: `False`

Note: only use on single-instance setup: it will break consistency with clients in multi-instance setup

##### use_cache_subfolder_for_synctoken

_(>= 3.3.2)_

Use subfolder `collection-cache` for cache file structure of 'sync-token' instead of inside collection folders, created if not present

Default: `False`

Note: only use on single-instance setup: it will break consistency with clients in multi-instance setup

##### use_mtime_and_size_for_item_cache

_(>= 3.3.2)_

Use last modification time (in nanoseconds) and size (in bytes) for 'item' cache instead of SHA256 (improves speed)

Default: `False`

Notes:
* check used filesystem mtime precision before enabling
* conversion is done on access
* bulk conversion can be done offline using the storage verification option `radicale --verify-storage`

##### folder_umask

_(>= 3.3.2)_

umask to use for folder creation (not applicable for OS Windows)

Default: (system-default, usually `0022`)

Useful values:
* `0077` (user:rw group:- other:-)
* `0027` (user:rw group:r other:-)
* `0007` (user:rw group:rw other:-)
* `0022` (user:rw group:r other:r)

##### max_sync_token_age

Delete sync-tokens that are older than the specified time (in seconds).

Default: `2592000`

##### skip_broken_item

_(>= 3.2.2)_

Skip broken item instead of triggering an exception

Default: `True`

##### hook

Command that is run after changes to storage. See the
[Versioning collections with Git](#versioning-collections-with-git)
tutorial for an example.

Default: (unset)

Supported placeholders:
 - `%(user)s`: logged-in user
 - `%(cwd)s`: current working directory _(>= 3.5.1)_
 - `%(path)s`: full path of item _(>= 3.5.1)_
 - `%(to_path)s`: full path of destination item (only set on MOVE request) _(>= 3.5.5)_
 - `%(request)s`: request method _(>= 3.5.5)_

The command will be executed with base directory defined in `filesystem_folder` (see above)

##### predefined_collections

Create predefined user collections.

Example:
```json
{
  "def-addressbook": {
     "D:displayname": "Personal Address Book",
     "tag": "VADDRESSBOOK"
  },
  "def-calendar": {
     "C:supported-calendar-component-set": "VEVENT,VJOURNAL,VTODO",
     "D:displayname": "Personal Calendar",
     "tag": "VCALENDAR"
  }
}
```
Default: (unset)

#### [web]

##### type

The backend that provides the web interface of Radicale.

Available backends are:

* `none`  
  Simply shows the message "Radicale works!".

* `internal`  
  Allows creation and management of address books and calendars.

Default: `internal`

#### [logging]

##### level

Set the logging level.

Available levels are:
* `debug`
* `info`
* `warning`
* `error`
* `critical`

Default: `warning` _(< 3.2.0)_ / `info` _(>= 3.2.0)_

##### trace_on_debug

_(> 3.5.4)_

Do not filter debug messages starting with 'TRACE'

Default: `False`

##### trace_filter

_(> 3.5.4)_

Filter debug messages starting with 'TRACE/<TOKEN>'

Prerequisite: `trace_on_debug = True`

Default: (empty)

##### mask_passwords

Do not include passwords in logs.

Default: `True`

##### bad_put_request_content

_(>= 3.2.1)_

Log bad PUT request content (for further diagnostics)

Default: `False`

##### backtrace_on_debug

_(>= 3.2.2)_

Log backtrace on `level = debug`

Default: `False`

##### request_header_on_debug

_(>= 3.2.2)_

Log request on `level = debug`

Default: `False`

##### request_content_on_debug

_(>= 3.2.2)_

Log request on `level = debug`

Default: `False`

##### response_content_on_debug

_(>= 3.2.2)_

Log response on `level = debug`

Default: `False`

##### rights_rule_doesnt_match_on_debug

_(>= 3.2.3)_

Log rights rule which doesn't match on `level = debug`

Default: `False`

##### storage_cache_actions_on_debug

_(>= 3.3.2)_

Log storage cache actions on `level = debug`

Default: `False`

#### [headers]

This section can be used to specify additional HTTP headers that will be sent to clients.

An example to relax the same-origin policy:

```ini
Access-Control-Allow-Origin = *
```

#### [hook]

##### type

Hook binding for event changes and deletion notifications.

Available types are:

* `none`  
  Disabled. Nothing will be notified.

* `rabbitmq` _(>= 3.2.0)_  
  Push the message to the rabbitmq server.

* `email` _(>= 3.5.5)_  
  Send an email notification to event attendees.

Default: `none`

##### dryrun

_(> 3.5.4)_

Dry-Run / simulate (i.e. do not really trigger) the hook action.

Default: `False`

##### rabbitmq_endpoint

_(>= 3.2.0)_

End-point address for rabbitmq server.
E.g.: `amqp://user:password@localhost:5672/`

Default: (unset)

##### rabbitmq_topic

_(>= 3.2.0)_

RabbitMQ topic to publish message in.

Default: (unset)

##### rabbitmq_queue_type

_(>= 3.2.0)_

RabbitMQ queue type for the topic.

Default: `classic`

##### smtp_server

_(>= 3.5.5)_

Address of SMTP server to connect to.

Default: (unset)

##### smtp_port

_(>= 3.5.5)_

Port on SMTP server to connect to.

Default:

##### smtp_security

_(>= 3.5.5)_

Use encryption on the SMTP connection.

One of:
* `none`
* `tls`
* `starttls`

Default: `none`

##### smtp_ssl_verify_mode

_(>= 3.5.5)_

The certificate verification mode for tls and starttls.

One of:
* `NONE`
* `OPTIONAL`
* `REQUIRED`

Default: `REQUIRED`

##### smtp_username

_(>= 3.5.5)_

Username to authenticate with SMTP server.
Leave empty to disable authentication (e.g. using local mail server).

Default: (unset)

##### smtp_password

_(>= 3.5.5)_

Password to authenticate with SMTP server.
Leave empty to disable authentication (e.g. using local mail server).

Default: (unset)

##### from_email

_(>= 3.5.5)_

Email address to use as sender in email notifications.

Default: (unset)

##### mass_email

_(>= 3.5.5)_

When enabled, send one email to all attendee email addresses.
When disabled, send one email per attendee email address.

Default: `False`

##### new_or_added_to_event_template

_(>= 3.5.5)_

Template to use for added/updated event email body sent to an attendee when the event is created or they are added to a pre-existing event.

The following placeholders will be replaced:
* `$organizer_name`: Name of the organizer, or "Unknown Organizer" if not set in event
* `$from_email`: Email address the email is sent from
* `$attendee_name`: Name of the attendee (email recipient), or "everyone" if mass email enabled.
* `$event_name`: Name/summary of the event, or "No Title" if not set in event
* `$event_start_time`: Start time of the event in ISO 8601 format
* `$event_end_time`: End time of the event in ISO 8601 format, or "No End Time" if the event has no end time
* `$event_location`: Location of the event, or "No Location Specified" if not set in event

Providing any words prefixed with $ not included in the list above will result in an error.

Default: 
```
Hello $attendee_name,

You have been added as an attendee to the following calendar event.

    $event_title
    $event_start_time - $event_end_time
    $event_location

This is an automated message. Please do not reply.
```

##### deleted_or_removed_from_event_template

_(>= 3.5.5)_

Template to use for deleted/removed event email body sent to an attendee when the event is deleted or they are removed from the event.

The following placeholders will be replaced:
* `$organizer_name`: Name of the organizer, or "Unknown Organizer" if not set in event
* `$from_email`: Email address the email is sent from
* `$attendee_name`: Name of the attendee (email recipient), or "everyone" if mass email enabled.
* `$event_name`: Name/summary of the event, or "No Title" if not set in event
* `$event_start_time`: Start time of the event in ISO 8601 format
* `$event_end_time`: End time of the event in ISO 8601 format, or "No End Time" if the event has no end time
* `$event_location`: Location of the event, or "No Location Specified" if not set in event

Providing any words prefixed with $ not included in the list above will result in an error.

Default:
```
Hello $attendee_name,

The following event has been deleted.

    $event_title
    $event_start_time - $event_end_time
    $event_location

This is an automated message. Please do not reply.
```

##### updated_event_template

_(>= 3.5.5)_

Template to use for updated event email body sent to an attendee when non-attendee-related details of the event are updated.

Existing attendees will NOT be notified of a modified event if the only changes are adding/removing other attendees.

The following placeholders will be replaced:
* `$organizer_name`: Name of the organizer, or "Unknown Organizer" if not set in event
* `$from_email`: Email address the email is sent from
* `$attendee_name`: Name of the attendee (email recipient), or "everyone" if mass email enabled.
* `$event_name`: Name/summary of the event, or "No Title" if not set in event
* `$event_start_time`: Start time of the event in ISO 8601 format
* `$event_end_time`: End time of the event in ISO 8601 format, or "No End Time" if the event has no end time
* `$event_location`: Location of the event, or "No Location Specified" if not set in event

Providing any words prefixed with $ not included in the list above will result in an error.

Default:
```
Hello $attendee_name,
            
The following event has been updated.

    $event_title
    $event_start_time - $event_end_time
    $event_location
    
This is an automated message. Please do not reply.
```

#### [reporting]

##### max_freebusy_occurrence

_(>= 3.2.3)_

When returning a free-busy report, a list of busy time occurrences are
generated based on a given time frame. Large time frames could
generate a lot of occurrences based on the time frame supplied. This
setting limits the lookup to prevent potential denial of service
attacks on large time frames. If the limit is reached, an HTTP error
is thrown instead of returning the results.

Default: 10000

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

##### Adress books with CardBook add-on

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
* **O:** allow overwriting a collection in case `permit_overwrite_collection=False`
* **o:** deny overwriting a collection in case `permit_overwrite_collection=True`

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

## Contribute

#### Report Bugs

Found a bug? Want a new feature? Report a new issue on the
[Radicale bug-tracker](https://github.com/Kozea/Radicale/issues).

#### Hack

Interested in hacking? Feel free to clone the
[git repository on GitHub](https://github.com/Kozea/Radicale) if you want to
add new features, fix bugs or update the documentation.

#### Documentation

To change or complement the documentation create a pull request to
[DOCUMENTATION.md](https://github.com/Kozea/Radicale/blob/master/DOCUMENTATION.md).

## Download

#### PyPI

Radicale is [available on PyPI](https://pypi.python.org/pypi/Radicale/). To
install, just type as superuser:

```bash
python3 -m pip install --upgrade radicale
```

#### Git Repository

If you want the development version of Radicale, take a look at the
[git repository on GitHub](https://github.com/Kozea/Radicale/), or install it
directly with:

```bash
python3 -m pip install --upgrade https://github.com/Kozea/Radicale/archive/master.tar.gz
```

You can also download the content of the repository as an
[archive](https://github.com/Kozea/Radicale/tarball/master).

#### Source Packages

You can find the source packages of all releases on
[GitHub](https://github.com/Kozea/Radicale/releases).

#### Docker

Radicale is available as a [Docker image](https://github.com/Kozea/Radicale/pkgs/container/radicale) for platforms `linux/amd64` and `linux/arm64`. To install the latest version, run:

```bash
docker pull ghcr.io/kozea/radicale:latest
```

An example `docker-compose.yml` and detailed instructions will soon be updated.


#### Linux Distribution Packages

Radicale has been packaged for:

* [ArchLinux](https://www.archlinux.org/packages/community/any/radicale/) by
  David Runge
* [Debian](https://packages.debian.org/radicale) by Jonas Smedegaard
* [Gentoo](https://packages.gentoo.org/packages/www-apps/radicale)
  by René Neumann, Maxim Koltsov and Manuel Rüger
* [Fedora/EnterpriseLinux](https://src.fedoraproject.org/rpms/radicale) by Jorti
  and Peter Bieringer
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
[available on Cloudron](https://cloudron.io/button.html?app=org.radicale.cloudronapp2).

If you are interested in creating packages for other Linux distributions, read
the ["Contribute" section](#contribute).

## About

#### Main Goals

Radicale is a complete calendar and contact storing and manipulating
solution. It can store multiple calendars and multiple address books.

Calendar and contact manipulation is available from both local and distant
accesses, possibly limited through authentication policies.

It aims to be a lightweight solution, easy to use, easy to install, easy to
configure. As a consequence, it requires few software dependencies and is
preconfigured to work out-of-the-box.

Radicale is written in Python. It runs on most of the UNIX-like platforms
(Linux, \*BSD, macOS) and Windows. It is free and open-source software.

#### What Radicale Will Never Be

Radicale is a server, not a client. No interfaces will be created to work with
the server.

CalDAV and CardDAV are not perfect protocols. We think that their main problem
is their complexity, that is why we decided not to implement the whole standard
but just enough to understand some of its client-side implementations.

CalDAV and CardDAV are the best open standards available, and they are quite
widely used by both clients and servers. We decided to use it, and we will not
use another one.

#### Technical Choices

Important global development choices have been decided before writing
code. They are very useful to understand why the Radicale Project is different
from other CalDAV and CardDAV servers, and why features are included or not in
the code.

##### Oriented to Calendar and Contact User Agents

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

##### Simple

Radicale is designed to be simple to install, simple to configure, simple to
use.

The installation is very easy, particularly with Linux: one dependency, no
superuser rights needed, no configuration required, no database. Installing and
launching the main script out-of-the-box, as a normal user, are often the only
steps to have a simple remote calendar and contact access.

Contrary to other servers that are often complicated, require high privileges
or need a strong configuration, the Radicale Server can (sometimes, if not
often) be launched in a couple of minutes, if you follow the
[tutorial](#simple-5-minute-setup).

##### Lazy

The CalDAV RFC defines what must be done, what can be done and what cannot be
done. Many violations of the protocol are totally defined and behaviors are
given in such cases.

Radicale often assumes that the clients are perfect and that protocol
violations do not exist. That is why most of the errors in client requests have
undetermined consequences for the lazy server that can reply good answers, bad
answers, or even no answer.

#### History

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
