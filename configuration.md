---
layout: page
title: Configuration
permalink: /configuration/
---

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
```shell
python3 -m radicale --config "" --server-hosts 0.0.0.0:5232 --auth-type htpasswd --htpasswd-filename /path/to/htpasswd --htpasswd-encryption bcrypt
```

The `--config ""` argument is required to stop Radicale from trying
to load configuration files. Run `python3 -m radicale --help` for more information.

In the following, all configuration categories and options are described.

## server
Most configuration options in this category are only relevant in standalone
mode. All options beside `max_content_length` and `realm` are ignored,
when Radicale runs via WSGI.

### hosts
A comma separated list of addresses that the server will bind to.

Default: `127.0.0.1:5555`

### daemon
Daemonize the Radicale process. It does not reset the umask.

Default: `False`

### pid
If daemon mode is enabled, Radicale will write its PID to this file.

Default:

### max_connections
The maximum number of parallel connections. Set to `0` to disable the limit.

Default: `20`

### max_content_length
The maximum size of the request body. (bytes)

Default: `10000000`

### timeout
Socket timeout. (seconds)

Default: `10`

### ssl
Enable transport layer encryption.

Default: `False`

### certificate
Path of the SSL certifcate.

Default: `/etc/ssl/radicale.cert.pem`

### key
Path to the private key for SSL. Only effective if `ssl` is enabled.

Default: `/etc/ssl/radicale.key.pem`

### certificate_authority
Path to the CA certificate for validating client certificates. This can be used
to secure TCP traffic between Radicale and a reverse proxy. If you want to
authenticate users with client-side certificates, you also have to write an
authentication plugin that extracts the user name from the certifcate.

Default:

### protocol
SSL protocol used. See python's ssl module for available values.

Default: `PROTOCOL_TLSv1_2`

### ciphers
Available ciphers for SSL. See python's ssl module for available ciphers.

Default:

### dns_lookup
Reverse DNS to resolve client address in logs.

Default: `True`

### realm
Message displayed in the client when a password is needed.

Default: `Radicale - Password Required`

## encoding
### request
Encoding for responding requests.

Default: `utf-8`

### stock
Encoding for storing local collections

Default: `utf-8`

## auth
### type
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

### htpasswd_filename
Path to the htpasswd file.

Default:

### htpasswd_encryption
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

## rights
### type
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

### file
File for the rights backend `from_file`.  See the
[Rights]({{ site.baseurl }}/rights/) page.

## storage
### type
The backend that is used to store data.

Available backends:

`multifilesystem`
: Stores the data in the filesystem.

Default: `multifilesystem`

### filesystem_folder

Folder for storing local collections, created if not present.

Default: `/var/lib/radicale/collections`

### filesystem_locking
Lock the storage. This must be disabled if locking is not supported by the
underlying file system. Never start multiple instances of Radicale or edit the
storage externally while Radicale is running if disabled.

Default: `True`

### max_sync_token_age
Delete sync-token that are older than the specified time. (seconds)

Default: `2592000`

### filesystem_fsync
Sync all changes to disk during requests. (This can impair performance.)
Disabling it increases the risk of data loss, when the system crashes or
power fails!

Default: `True`

### hook
Command that is run after changes to storage. Take a look at the
[Versioning]({{ site.baseurl }}/versioning/) page for an example.

Default:

## web
### type
The backend that provides the web interface of Radicale.

Available backends:

`none`
: Just shows the message "Radicale works!".

`internal`
: Allows creation and management of address books and calendars.

Default: `internal`

## logging
### debug
Set the default logging level to debug.

Default: `False`

### full_environment
Log all environment variables (including those set in the shell).

Default: `False`

### mask_passwords
Don't include passwords in logs.

Default: `True`

### config
Logging configuration file. See the [Logging]({{ site.baseurl }}/logging/) page.

Default:

## headers
In this section additional HTTP headers that are sent to clients can be
specified.

An example to relax the same-origin policy:
```ini
Access-Control-Allow-Origin = *
```
