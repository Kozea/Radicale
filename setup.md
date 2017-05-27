---
layout: page
title: Basic Setup
permalink: /setup/
---

Installation instructions can be found on the
[Tutorial]({{ site.baseurl }}/tutorial/) page.

## Configuration

Radicale tries to load configuration files from `/etc/radicale/config`,
`~/.config/radicale/config` and the `RADICALE_CONFIG` environment variable.
A custom path can be specified with the `--config /path/to/config` command
line argument.

You should create a new configuration file at the desired location.
(If the use of a configuration file is inconvenient, all options can be
passed via command line arguments.)

All configuration options are described in detail on the
[Configuration]({{ site.baseurl }}/configuration/) page.

## Authentication

In it's default configuration Radicale doesn't check user names or passwords.
If the server is reachable over a network, you should change this.

First a `users` file with all user names and passwords must be created.
It can be stored in the same directory as the configuration file.

The file can be created and managed with
[htpasswd](https://httpd.apache.org/docs/current/programs/htpasswd.html):
```shell
# Create a new htpasswd file with the user "user1"
$ htpasswd -B -c /path/to/users user1
New password:
Re-type new password:
# Add another user
$ htpasswd -B /path/to/users user2
New password:
Re-type new password:
```
**bcrypt** is used to secure the passwords. Radicale required additional
dependencies for this encryption method:
```shell
$ python3 -m pip install --upgrade passlib
$ python3 -m pip install --upgrade bcrypt
```

Authentication can be enabled with the following configuration:
```ini
[auth]
type = htpasswd
htpasswd_filename = /path/to/users
htpasswd_encryption = bcrypt  # encryption method used in the htpasswd file
```

## Addresses

The default configuration binds the server to localhost. It can't be reached
from other computers. This can be changed with the following configuration
options:

```ini
[server]
hosts = 0.0.0.0:5232
```

More addresses can be added (separated by commas).

## Storage

Data is stored in the folder `/var/lib/radicale/collections`. The path can
be changed with the foloowing configuration:

```ini
[storage]
filesystem_folder = /path/to/storage
```

## Limits

Radicale enforces limits on the maximum number of parallel connections,
the maximum file size (important for contacts with big photos) and the rate of
incorrect authentication attempts. Connections are terminated after a timeout.
The default values should be fine for most scenarios.

```ini
[server]
max_connections = 20
max_content_length = 10000000  # 1 Megabyte
timeout = 10  # seconds
[auth]
delay = 1  # Average delay after failed login attempts in seconds
```

## Running as a service

The method to run Radicale as a service depends on your host operating system.
Follow one of the chapters below depending on your operating system and
requirements.

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
You may have to add addition command line arguments to Radicale for the
configuration file, etc.

To enable and manage the service run:
```shell
# Enable the service
$ systemctl --user enable radicale
# Start the service
$ systemctl --user start radicale
# Check the status of the service
$ systemctl --user status radicale
# View all log messages
$ journalctl --user --unit radicale.service
```

### Linux with systemd system-wide

Create the **radicale** user and group for the Radicale service.
The configuration files must be readable by this user and the storage folder
must be writable.

Create the file `/etc/systemd/system/radicale.service`:
```ini
[Unit]
Description=A simple CalDAV (calendar) and CardDAV (contact) server

[Service]
ExecStart=/usr/bin/env python3 -m radicale
Restart=on-failure
User=radicale

[Install]
WantedBy=multi-user.target
```
You may have to add addition command line arguments to Radicale for the
configuration file, etc.

To enable and manage the service run:
```shell
# Enable the service
$ systemctl enable radicale
# Start the service
$ systemctl start radicale
# Check the status of the service
$ systemctl status radicale
# View all log messages
$ journalctl --unit radicale.service
```

## MacOS with launchd

*To be written.*

## Classic daemonization

Set the configuration option `daemon` in the section `server` to `True`.
You may want to set the option `pid` to the path of a PID file.

After daemonization the server will not log anything. You have to configure
[Logging]({{ site.baseurl }}/tutorial/).

If you start Radicale now, it will initialize and fork into the background.
The main process exits, after the PID file is written.

## Windows with "NSSM - the Non-Sucking Service Manager"

First install [NSSM](https://nssm.cc/) and start `nssm install` in a command
prompt. Apply the following configuration:

* Service name: `Radicale`
* Application
  * Path: `C:\Path\To\Python\python.exe`
  * Arguments: `-m radicale --config C:\Path\To\Config`
* I/O redirection
  * Error: `C:\Path\To\Radicale.log`

Be aware that the service runs in the local system account, you might want to change this. Managing user accounts is beyond the scope of this manual.

The log file might grow very big over time, you can configure file rotation
in **NSSM** to prevent this.

The service is configured to start automatically when the computer starts.
To start the service manually open **Services** in **Computer Management** and
start the **Radicale** service.
