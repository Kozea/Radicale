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

In its default configuration Radicale doesn't check user names or passwords.
If the server is reachable over a network, you should change this.

First a `users` file with all user names and passwords must be created.
It can be stored in the same directory as the configuration file.

### The secure way

The secure way uses **bcrypt** to secure the passwords.
Radicale requires additional dependencies for this encryption method:
```shell
$ python3 -m pip install --upgrade radicale[bcrypt]
```

The `users` file can be created and managed with
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

Or without `htpasswd`, hash your password using Python's bcrypt:
```shell
$ python3 -c "import bcrypt, getpass; print(bcrypt.hashpw(getpass.getpass('Password: ').encode(), bcrypt.gensalt()).decode())"
Password:
$2b$12$Hss4bY4v5iResZTtqtNBS.z/Lod9td9.BxSZW5xvaPl1XV0z37nKO
```
And manually add a line to the `users` file containing the user name
followed by the hash separated by `:`. Example:
```
john:$2b$12$Hss4bY4v5iResZTtqtNBS.z/Lod9td9.BxSZW5xvaPl1XV0z37nKO
```

Authentication can be enabled with the following configuration:
```ini
[auth]
type = htpasswd
htpasswd_filename = /path/to/users
# encryption method used in the htpasswd file
htpasswd_encryption = bcrypt
```

### The simple but insecure way

Create the `users` file by hand with lines containing the user name and
password separated by `:`. Example:

```
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
be changed with the following configuration:

```ini
[storage]
filesystem_folder = /path/to/storage
```

**Security:** The storage folder should not be readable by unauthorized users.
Otherwise, they can read the calendar data and lock the storage.
You can find OS dependent instructions in the **Running as a service** section.

## Limits

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
[Logging]({{ site.baseurl }}/logging/).

If you start Radicale now, it will initialize and fork into the background.
The main process exits, after the PID file is written.

**Security:** You can set the **umask** with `umask 0027` before you start the
daemon, to protect your calendar data and log files from other users.
Don't forget to set permissions of files that are already created!


## Windows with "NSSM - the Non-Sucking Service Manager"

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
