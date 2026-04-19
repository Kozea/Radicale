## Documentation

### Options

#### General Options

##### --version

Print version

##### --verify-storage

Verification of local collections storage

##### --verify-item <file>

_(>= 3.6.0)_

Verification of a particular item file

##### --verify-sharing

_(>= 3.7.0)_

Verification of local sharing database

##### -C|--config <file>

Load one or more specified config file(s)

##### -D|--debug

Turns log level to debug

#### Configuration Options

Each supported option from config file can be provided/overridden by command line
replacing `_` with `-` and prepending the section followed by a `-`, e.g.

```
[logging]
backtrace_on_debug = False
```

can be enabled using `--logging-backtrace-on-debug=true` on command line.

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

##### delay_on_error

_(>= 3.7.0)_

Base delay in case of error 5xx response (seconds)

Default: `1`

##### max_content_length

The maximum size of the request body. (bytes)

Default: `100000000` (100 Mbyte)

In case of using a reverse proxy in front of check also there related option.

##### max_resource_size

_(>= 3.5.10)_

The maximum size of a resource. (bytes)

Default: `10000000` (10 Mbyte)

Limited to 80% of max_content_length to cover plain base64 encoded payload.

Announced to clients requesting "max-resource-size" via PROPFIND.

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

* `http_remote_user` _(>= 3.5.9)_
  Takes the username from the Remote-User HTTP header `HTTP_REMOTE_USER` and disables
  Radicale's internal HTTP authentication. This can be used to provide the
  username from a reverse proxy which authenticated the client upfront.
  Requires validation, otherwise clients can supply the header themselves,
  which then is unconditionally trusted.

* `http_x_remote_user`  
  Takes the username from the X-Remote-User HTTP header `HTTP_X_REMOTE_USER` and disables
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
  Also consider version of passlib(libpass): bcrypt >= 5.0.0 requires passlib(libpass) >= 1.9.3

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

Average delay (in seconds) after failed or missing login attempts or denied access.

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
in the user's entry, an additional query is performed to search for those groups beneath `ldap_group_base`,
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

##### oauth2_client_id

_(>= 3.7.0)_

Client ID used to request the Auth2 token

Default: `radicale`

##### oauth2_client_secret

_(>= 3.7.0)_

Client secret used to request the Auth2 token

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
* If `False` it can be explicitly granted per collection by *rights* permissions: `D`
* If `True` it can be explicitly forbidden per collection by *rights* permissions: `d`

Default: `True`

##### permit_overwrite_collection

_(>= 3.3.0)_

Global permission to overwrite complete collections.
* If `False` it can be explicitly granted per collection by *rights* permissions: `O`
* If `True` it can be explicitly forbidden per collection by *rights* permissions: `o`

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

##### strict_preconditions

_(>= 3.5.8)_

Strict preconditions check on PUT in case item already exists [RFC6352#9.2](https://www.rfc-editor.org/rfc/rfc6352#section-9.2)

Default: `False`

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
* `trace` _(>= 3.7.1)_
* `debug`
* `info`
* `notice` _(>= 3.7.1)_
* `warning`
* `error`
* `critical`
* `alert` _(>= 3.7.1)_

Default: `warning` _(< 3.2.0)_ / `info` _(>= 3.2.0)_

##### limit_content

_(>= 3.7.0)_

Limit content of wrapped text (chars)

Default: `3000`

##### trace_on_debug

_(> 3.5.4)_ && _(< 3.7.1)_

Do not filter debug messages starting with 'TRACE'

Default: `False`

##### trace_filter

_(> 3.5.4)_ && _(< 3.7.1)_

Filter debug messages starting with 'TRACE/<TOKEN>'

Prerequisite: `trace_on_debug = True`

_(>= 3.7.1)_

Filter trace messages starting with '<TOKEN>'

Prerequisite: `level = trace`

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

Log request header on `level = debug`

Default: `False`

##### request_content_on_debug

_(>= 3.2.2)_

Log request content (body) on `level = debug`

Default: `False`

##### response_header_on_debug

_(>= 3.5.10)_

Log response header on `level = debug`

Default: `False`

##### response_content_on_debug

_(>= 3.2.2)_

Log response content (body) on `level = debug`

Default: `False`

##### rights_rule_doesnt_match_on_debug

_(>= 3.2.3)_

Log rights rule which doesn't match on `level = debug`

Default: `False`

##### storage_cache_actions_on_debug

_(>= 3.3.2)_

Log storage cache actions on `level = debug`

Default: `False`

##### profiling_per_request

_(>= 3.5.10)_

Log profiling data on level=info

Default: `none`

One of
* `none` (disabled)
* `per_request` (above minimum duration)
* `per_request_method` (regular interval)

##### profiling_per_request_min_duration

_(>= 3.5.10)_

Log profiling data per request minimum duration (seconds) before logging, otherwise skip

Default: `3`

##### profiling_per_request_header

_(>= 3.5.10)_

Log profiling request header (if passing minimum duration)

Default: `False`

##### profiling_per_request_xml

_(>= 3.5.10)_

Log profiling request XML (if passing minimum duration)

Default: `False`

##### profiling_per_request_method_interval

_(>= 3.5.10)_

Log profiling data per method interval (seconds)
Triggered by request, not active on idle systems

Default: `600`

##### profiling_top_x_functions

_(>= 3.5.10)_

Log profiling top X functions (limit)

Default: `10`

#### [headers]

This section can be used to specify additional HTTP headers that will be sent to clients.

An example to relax the same-origin policy:

```ini
Access-Control-Allow-Origin = *
```

An example to set CSP to disallow execution of unknown javascript:

```ini
Content-Security-Policy = default-src 'self'; object-src 'none'
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

#### [sharing]

_(>= 3.7.0)_

See also [Collection Sharing](https://github.com/Kozea/Radicale/blob/master/SHARING.md).

##### type

_(>= 3.7.0)_

Sharing database type

One of:
 * `none`
 * `csv`
 * `files`

Default: `none` (implicit disabling the feature)

##### database_path

_(>= 3.7.0)_

Sharing database path

Default:
 * type `csv`: `(filesystem_folder)/collection-db/sharing.csv`
 * type `files`: `(filesystem_folder)/collection-db/files`

##### collection_by_token

_(>= 3.7.0)_

Share collection by token

Default: `false`

##### collection_by_map

_(>= 3.7.0)_

Share collection by map

Default: `false`

##### permit_create_token

_(>= 3.7.0)_

Permit create of token-based sharing

Default: `false`

* If `False` it can be explicitly granted by *rights* permissions: `T`
* If `True` it can be explicitly forbidden by *rights* permissions: `t`

##### permit_create_map

_(>= 3.7.0)_

Permit create of map-based sharing

Default: `false`

* If `False` it can be explicitly granted by *rights* permissions: `M`
* If `True` it can be explicitly forbidden by *rights* permissions: `m`

##### permit_properties_overlay

_(>= 3.7.0)_

Permit (limited) properties overlay by user of shared collection

Default: `false`

* If `False` it can be explicitly granted by *share* permissions: `P`
* If `True` it can be explicitly forbidden by *share* permissions: `p`

##### enforce_properties_overlay

_(>= 3.7.0)_

Enforce properties overlay even on write access

Default: `true`

* If `False` it can be explicitly enforced by *share* permissions: `E`
* If `True` it can be explicitly forbidden by *share* permissions: `e`

##### default_permissions_create_token

Default permissions for create token-based sharing

Default: `r`

Supported: `rwEePp`

##### default_permissions_create_map

Default permissions for map-based sharing

Default: `r`

Supported: `rwEePp`
