
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
# 10 Megabyte (>= 3.5.10)
max_resource_size = 10000000
# 30 seconds
timeout = 30

[auth]
# Average delay after failed login attempts in seconds
# Also used for invalid/not-existing/not-enabled share-by-token (>= 3.7.0)
delay = 1
```

### Running as a service

The method to run Radicale as a service depends on your host operating system.
Follow one of the chapters below depending on your operating system and
requirements.

#### Linux with systemd system-wide

Recommendation: check support by [Linux Distribution Packages](#linux-distribution-packages)
instead of manual setup / initial configuration.

Create the **radicale** user and group for the Radicale service by running (as `root`):
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
server.modules += ( "mod_proxy" , "mod_setenv" )

$HTTP["url"] =~ "^/radicale/" {
  proxy.server = ( "" => (( "host" => "127.0.0.1", "port" => "5232" )) )
  setenv.add-request-header = ( "X-Script-Name" => "/radicale" )
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
