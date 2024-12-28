# Changelog

## 3.3.3
* Add: display mtime_ns precision of storage folder with condition warning if too less
* Improve: disable fsync during storage verification
* Improve: suppress duplicate log lines on startup
* Contrib: logwatch config and script
* Improve: log precondition result on PUT request

## 3.3.2
* Fix: debug logging in rights/from_file
* Add: option [storage] use_cache_subfolder_for_item for storing 'item' cache outside collection-root
* Fix: ignore empty RRULESET in item
* Add: option [storage] filesystem_cache_folder for defining location of cache outside collection-root
* Add: option [storage] use_cache_subfolder_for_history for storing 'history' cache outside collection-root
* Add: option [storage] use_cache_subfolder_for_synctoken for storing 'sync-token' cache outside collection-root
* Add: option [storage] folder_umask for configuration of umask (overwrite system-default)
* Fix: also remove 'item' from cache on delete
* Improve: avoid automatically invalid cache on upgrade in case no change on cache structure
* Improve: log important module versions on startup
* Improve: auth.ldap config shown on startup, terminate in case no password is supplied for bind user
* Add: option [auth] uc_username for uppercase conversion (similar to existing lc_username)
* Add: option [logging] storage_cache_action_on_debug for conditional logging
* Fix: set PRODID on collection upload (instead of vobject is inserting default one)
* Add: option [storage] use_mtime_and_size_for_item_cache for changing cache lookup from SHA256 to mtime_ns + size
* Fix: buggy cache file content creation on collection upload

## 3.3.1

* Add: option [auth] type=dovecot
* Enhancement: log content in case of multiple main components error
* Fix: expand does not take timezones into account 
* Fix: expand does not support overridden recurring events
* Fix: expand does not honor start and end times
* Add: option [server] protocol + ciphersuite for optional restrictions on SSL socket
* Enhancement: [storage] hook documentation, logging, error behavior (no longer throwing an exception)

## 3.3.0

* Adjustment: option [auth] htpasswd_encryption change default from "md5" to "autodetect"
* Add: option [auth] type=ldap with (group) rights management via LDAP/LDAPS
* Enhancement: permit_delete_collection can be now controlled also per collection by rights 'D' or 'd'
* Add: option [rights] permit_overwrite_collection (default=True) which can be also controlled per collection by rights 'O' or 'o'
* Fix: only expand VEVENT on REPORT request containing 'expand'
* Adjustment: switch from setup.py to pyproject.toml (but keep files for legacy packaging)
* Adjustment: 'rights' file is now read only during startup
* Cleanup: Python 3.7 leftovers

## 3.2.3
* Add: support for Python 3.13
* Fix: Using icalendar's tzinfo on created datetime to fix issue with icalendar
* Fix: typos in code
* Enhancement: Added free-busy report
* Enhancement: Added 'max_freebusy_occurrences` setting to avoid potential DOS on reports
* Enhancement: remove unexpected control codes from uploaded items
* Enhancement: add 'strip_domain' setting for username handling
* Enhancement: add option to toggle debug log of rights rule with doesn't match
* Drop: remove unused requirement "typeguard"
* Improve: Refactored some date parsing code

## 3.2.2
* Enhancement: add support for auth.type=denyall (will be default for security reasons in upcoming releases)
* Enhancement: display warning in case only default config is active
* Enhancement: display warning in case no user authentication is active
* Enhancement: add option to skip broken item to avoid triggering exception (default: enabled)
* Enhancement: add support for predefined collections for new users
* Enhancement: add options to enable several parts in debug log like backtrace, request_header, request_content, response_content (default: disabled)
* Enhancement: rights/from_file: display resulting permission of a match in debug log
* Enhancement: add Apache config file example (see contrib directory)
* Fix: "verify-collection" skips non-collection directories, logging improved

## 3.2.1

* Enhancement: add option for logging bad PUT request content
* Enhancement: extend logging with step where bad PUT request failed
* Fix: support for recurrence "full day"
* Fix: list of web_files related to HTML pages
* Test: update/adjustments for workflows (pytest>=7, typeguard<4.3)

## 3.2.0

* Enhancement: add hook support for event changes+deletion hooks (initial support: "rabbitmq")
* Dependency: pika >= 1.1.0
* Enhancement: add support for webcal subscriptions
* Enhancement: major update of WebUI (design+features)
* Adjust: change default loglevel to "info"
* Enhancement: support "expand-property" on REPORT request
* Drop: support for Python 3.7 (EOSL, can't be tested anymore)
* Fix: allow quoted-printable encoding for vObjects

## 3.1.9

* Add: support for Python 3.11 + 3.12
* Drop: support for Python 3.6
* Fix: MOVE in case listen on non-standard ports or behind reverse proxy
* Fix: stricter requirements of Python 3.11
* Fix: HTML pages
* Fix: Main Component is missing when only recurrence id exists
* Fix: passlib don't support bcrypt>=4.1
* Fix: web login now proper encodes passwords containing %XX (hexdigits)
* Enhancement: user-selectable log formats
* Enhancement: autodetect logging to systemd journal
* Enhancement: test code
* Enhancement: option for global permit to delete collection
* Enhancement: auth type 'htpasswd' supports now 'htpasswd_encryption' sha256/sha512 and "autodetect" for smooth transition
* Improve: Dockerfiles
* Improve: server socket listen code + address format in log
* Update: documentations + examples
* Dependency: limit typegard version < 3
* General: code cosmetics

## 3.1.8

* Fix setuptools requirement if installing wheel
* Tests: Switch from `python setup.py test` to `tox`
* Small changes to build system configuration and tests

## 3.1.7

* Fix random href fallback

## 3.1.6

* Ignore `Not a directory` error for optional config paths
* Fix upload of whole address book/calendar with UIDs that collide on
  case-insensitive filesystem
* Remove runtime dependency on setuptools for Python>=3.9
* Windows: Block ADS paths

## 3.1.5

* Ignore configuration file if access is denied
* Use F_FULLFSYNC with PyPy on MacOS
* Fallback if F_FULLFSYNC is not supported by the filesystem

## 3.1.4

* Fallback if RENAME_EXCHANGE is not supported by the filesystem
* Assume POSIX compatibility if `sys.platform` is not `win32`

## 3.1.3

* Redirect '…/.well-known/caldav' and '…/.well-known/carddav' to base prefix
* Warning instead of error when base prefix ends with '/'

## 3.1.2

* Verify that base prefix starts with '/' but doesn't end with '/'
* Improve base prefix log message
* Never send body for HEAD requests (again)

## 3.1.1

* Workaround for contact photo bug in InfCloud
* Redirect GET and HEAD requests under `/.web` to sanitized path
* Set `Content-Length` header for HEAD requests
* Never send body for HEAD requests
* Improve error messages for `from_file` rights backend
* Don't sanitize WSGI script name

## 3.1.0

* Single `<D:propstat>` element in PROPPATCH response
* Allow multiple `<D:set>` and `<D:remove>` elements
* Improve log messages
* Fix date filter
* Improve sanitization of collection properties
* Cancel mkcalendar request on error
* Use **renameat2** on Linux for atomic overwriting of collections
* Command Line Parser
  * Disallow abbreviated arguments
  * Support backend specific options and HTTP headers
  * Optional argument for boolean options
  * Load no config file for `--config` without argument
* Allow float for server->timeout setting
* Fix **is-not-defined** filter in **addressbook-query** report
* Add python type hints
* Add **multifilesystem_nolock** storage
* Add support for Python 3.9 and 3.10
* Drop support for Python 3.5
* Fix compatibility with Evolution (Exceptions from recurrence rules)

## 3.0.6

* Allow web plugins to handle POST requests

## 3.0.5

* Start storage hook in own process group
* Kill storage hook on error or exit
* Try to kill child processes of storage hook
* Internal Server: Exit immediately when signal is received
  (do not wait for clients or storage hook to finish)

## 3.0.4

* Fix internal server on FreeBSD

## 3.0.3

* Fix internal server on OpenBSD

## 3.0.2

* Use 403 response for supported-report and valid-sync-token errors
* Internal server: Handle missing IPv6 support

## 3.0.1

* Fix XML error messages

## 3.0.0

This release is incompatible with previous releases.
See the upgrade checklist below.

* Parallel write requests
* Support PyPy
* Protect against XML denial-of-service attacks
* Check for duplicated UIDs in calendars/address books
* Only add missing UIDs for uploaded whole calendars/address books
* Switch from md5 to sha256 for UIDs and tokens
* Code cleanup:
  * All plugin interfaces were simplified and are incompatible with
    old plugins
  * Major refactor
  * Never sanitize paths multiple times (check if they are sanitized)
* Config
  * Multiple configuration files separated by `:` (resp. `;`
    on Windows)
  * Optional configuration files by prepending file path with `?`
  * Check validity of every configuration file and command line
    arguments separately
    * Report the source of invalid configuration parameters in
      error messages
  * Code cleanup:
    * Store configuration as parsed values
    * Use Schema that describes configuration and allow plugins to apply
      their own schemas
    * Mark internal settings with `_`
* Internal server
  * Bind to IPv4 and IPv6 address, when both are available for hostname
  * Set default address to `localhost:5232`
  * Remove settings for SSL ciphers and protocol versions (enforce safe
    defaults instead)
  * Remove settings for file locking because they are of little use
  * Remove daemonization (should be handled by service managers)
* Logging
  * Replace complex Python logger configuration with simple
    `logging.level` setting
  * Write PID and `threadName` instead of cryptic id's in log messages
  * Use `wsgi.errors` for logging (as required by the WSGI spec)
  * Code cleanup:
    * Don't pass logger object around (use `logging.getLogger()`
      instead)
* Auth
  * Use `md5` as default for `htpasswd_encryption` setting
  * Move setting `realm` from section `server` to `auth`
* Rights
  * Use permissions `RW` for non-leaf collections and `rw` for
    address books/calendars
  * New permission `i` that only allows access with HTTP method GET
    (CalDAV/CardDAV is susceptible to expensive search requests)
* Web
  * Add upload dialog for calendars/address books from file
  * Show startup loading message
  * Show warning if JavaScript is disabled
  * Pass HTML Validator
* Storage
  * Check for missing UIDs in items
  * Check for child collections in address books and calendars
  * Code cleanup:
    * Split BaseCollection in BaseStorage and BaseCollection

## Upgrade checklist

* Config
  * Some settings were removed
  * The default of `auth.htpasswd_encryption` changed to `md5`
  * The setting `server.realm` moved to `auth.realm`
  * The setting `logging.debug` was replaced by `logging.level`
  * The format of the `rights.file` configuration file changed:
    * Permission `r` replaced by `Rr`
    * Permission `w` replaced by `Ww`
    * New permission `i` added as subset of `r`
    * Replaced variable `%(login)s` by `{user}`
    * Removed variable `%(path)s`
    * `{` must be escaped as `{{` and `}` as `}}` in regexes
* File system storage
  * The storage format is compatible with Radicale 2.x.x
  * Run `radicale --verify-storage` to check for errors
* Custom plugins:
  * `auth` and `web` plugins require minor adjustments
  * `rights` plugins must be adapted to the new permission model
  * `storage` plugins require major changes

## 2.1.10 - Wild Radish

This release is compatible with version 2.0.0.

* Update required versions for dependencies
* Get `RADICALE_CONFIG` from WSGI environ
* Improve HTTP status codes
* Fix race condition in storage lock creation
* Raise default limits for content length and timeout
* Log output from hook

## 2.1.9 - Wild Radish

This release is compatible with version 2.0.0.

* Specify versions for dependencies
* Move WSGI initialization into module
* Check if `REPORT` method is actually supported
* Include `rights` file in source distribution
* Specify `md5` and `bcrypt` as extras
* Improve logging messages
* Windows: Fix crash when item path is a directory

## 2.1.8 - Wild Radish

This release is compatible with version 2.0.0.

* Flush files before fsync'ing

## 2.1.7 - Wild Radish

This release is compatible with version 2.0.0.

* Don't print warning when cache format changes
* Add documentation for `BaseAuth`
* Add `is_authenticated2(login, user, password)` to `BaseAuth`
* Fix names of custom properties in PROPFIND requests with
  `D:propname` or `D:allprop`
* Return all properties in PROPFIND requests with `D:propname` or
  `D:allprop`
* Allow `D:displayname` property on all collections
* Answer with `D:unauthenticated` for `D:current-user-principal` property
  when not logged in
* Remove non-existing `ICAL:calendar-color` and `C:calendar-timezone`
  properties from PROPFIND requests with `D:propname` or `D:allprop`
* Add `D:owner` property to calendar and address book objects
* Remove `D:getetag` and `D:getlastmodified` properties from regular
  collections

## 2.1.6 - Wild Radish

This release is compatible with version 2.0.0.

* Fix content-type of VLIST
* Specify correct COMPONENT in content-type of VCALENDAR
* Cache COMPONENT of calendar objects (improves speed with some clients)
* Stricter parsing of filters
* Improve support for CardDAV filter
* Fix some smaller bugs in CalDAV filter
* Add X-WR-CALNAME and X-WR-CALDESC to calendars downloaded via HTTP/WebDAV
* Use X-WR-CALNAME and X-WR-CALDESC from calendars published via WebDAV

## 2.1.5 - Wild Radish

This release is compatible with version 2.0.0.

* Add `--verify-storage` command-line argument
* Allow comments in the htpasswd file
* Don't strip whitespaces from user names and passwords in the htpasswd file
* Remove cookies from logging output
* Allow uploads of whole collections with many components
* Show warning message if server.timeout is used with Python < 3.5.2

## 2.1.4 - Wild Radish

This release is compatible with version 2.0.0.

* Fix incorrect time range matching and calculation for some edge-cases with
  rescheduled recurrences
* Fix owner property

## 2.1.3 - Wild Radish

This release is compatible with version 2.0.0.

* Enable timeout for SSL handshakes and move them out of the main thread
* Create cache entries during upload of items
* Stop built-in server on Windows when Ctrl+C is pressed
* Prevent slow down when multiple requests hit a collection during cache warm-up

## 2.1.2 - Wild Radish

This release is compatible with version 2.0.0.

* Remove workarounds for bugs in VObject < 0.9.5
* Error checking of collection tags and associated components
* Improve error checking of uploaded collections and components
* Don't delete empty collection properties implicitly
* Improve logging of VObject serialization

## 2.1.1 - Wild Radish Again

This release is compatible with version 2.0.0.

* Add missing UIDs instead of failing
* Improve error checking of calendar and address book objects
* Fix upload of whole address books

## 2.1.0 - Wild Radish

This release is compatible with version 2.0.0.

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
    users when `owner_only` plugin is used (information leakage)
* Authentication plugins can provide the login and password from the
  environment
  * new `remote_user` plugin, that gets the login from the `REMOTE_USER`
    environment variable (for WSGI server)
  * new `http_x_remote_user` plugin, that gets the login from the
    `X-Remote-User` HTTP header (for reverse proxies)

## 2.0.0 - Little Big Radish

This feature is not compatible with the 1.x.x versions. Follow our
[migration guide](https://radicale.org/2.1.html#documentation/migration-from-1xx-to-2xx)
if you want to switch from 1.x.x to 2.0.0.

* Support Python 3.3+ only, Python 2 is not supported anymore
* Keep only one simple filesystem-based storage system
* Remove built-in Git support
* Remove built-in authentication modules
* Keep the WSGI interface, use Python HTTP server by default
* Use a real iCal parser, rely on the "vobject" external module
* Add a solid calendar discovery
* Respect the difference between "files" and "folders", don't rely on slashes
* Remove the calendar creation with GET requests
* Be stateless
* Use a file locker
* Add threading
* Get atomic writes
* Support new filters
* Support read-only permissions
* Allow External plugins for authentication, rights management, storage and
  version control

## 1.1.4 - Fifth Law of Nature

* Use `shutil.move` for `--export-storage`

## 1.1.3 - Fourth Law of Nature

* Add a `--export-storage=FOLDER` command-line argument (by Unrud, see #606)

## 1.1.2 - Third Law of Nature

* **Security fix**: Add a random timer to avoid timing oracles and simple
  bruteforce attacks when using the htpasswd authentication method.
* Various minor fixes.

## 1.1.1 - Second Law of Nature

* Fix the owner_write rights rule

## 1.1 - Law of Nature

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

## 1.0.1 - Sunflower Again

* Update the version because of a **stupid** "feature"™ of PyPI

## 1.0 - Sunflower

* Enhanced performances (by Mathieu Dupuy)
* Add MD5-APR1 and BCRYPT for htpasswd-based authentication (by Jan-Philip Gehrcke)
* Use PAM service (by Stephen Paul Weber)
* Don't discard PROPPATCH on empty collections (by Markus Unterwaditzer)
* Write the path of the collection in the git message (by Matthew Monaco)
* Tests launched on Travis

## 0.10 - Lovely Endless Grass

* Support well-known URLs (by Mathieu Dupuy)
* Fix collection discovery (by Markus Unterwaditzer)
* Reload logger config on SIGHUP (by Élie Bouttier)
* Remove props files when deleting a collection (by Vincent Untz)
* Support salted SHA1 passwords (by Marc Kleine-Budde)
* Don't spam the logs about non-SSL IMAP connections to localhost (by Giel van Schijndel)

## 0.9 - Rivers

* Custom handlers for auth, storage and rights (by Sergey Fursov)
* 1-file-per-event storage (by Jean-Marc Martins)
* Git support for filesystem storages (by Jean-Marc Martins)
* DB storage working with PostgreSQL, MariaDB and SQLite (by Jean-Marc Martins)
* Clean rights manager based on regular expressions (by Sweil)
* Support of contacts for Apple's clients
* Support colors (by Jochen Sprickerhof)
* Decode URLs in XML (by Jean-Marc Martins)
* Fix PAM authentication (by Stepan Henek)
* Use consistent etags (by 9m66p93w)
* Use consistent sorting order (by Daniel Danner)
* Return 401 on unauthorized DELETE requests (by Eduard Braun)
* Move pid file creation in child process (by Mathieu Dupuy)
* Allow requests without base_prefix (by jheidemann)

## 0.8 - Rainbow

* New authentication and rights management modules (by Matthias Jordan)
* Experimental database storage
* Command-line option for custom configuration file (by Mark Adams)
* Root URL not at the root of a domain (by Clint Adams, Fabrice Bellet, Vincent Untz)
* Improved support for iCal, CalDAVSync, CardDAVSync, CalDavZAP and CardDavMATE
* Empty PROPFIND requests handled (by Christoph Polcin)
* Colon allowed in passwords
* Configurable realm message

## 0.7.1 - Waterfalls

* Many address books fixes
* New IMAP ACL (by Daniel Aleksandersen)
* PAM ACL fixed (by Daniel Aleksandersen)
* Courier ACL fixed (by Benjamin Frank)
* Always set display name to collections (by Oskari Timperi)
* Various DELETE responses fixed

## 0.7 - Eternal Sunshine

* Repeating events
* Collection deletion
* Courier and PAM authentication methods
* CardDAV support
* Custom LDAP filters supported

## 0.6.4 - Tulips

* Fix the installation with Python 3.1

## 0.6.3 - Red Roses

* MOVE requests fixed
* Faster REPORT answers
* Executable script moved into the package

## 0.6.2 - Seeds

* iPhone and iPad support fixed
* Backslashes replaced by slashes in PROPFIND answers on Windows
* PyPI archive set as default download URL

## 0.6.1 - Growing Up

* Example files included in the tarball
* htpasswd support fixed
* Redirection loop bug fixed
* Testing message on GET requests

## 0.6 - Sapling

* WSGI support
* IPv6 support
* Smart, verbose and configurable logs
* Apple iCal 4 and iPhone support (by Łukasz Langa)
* KDE KOrganizer support
* LDAP auth backend (by Corentin Le Bail)
* Public and private calendars (by René Neumann)
* PID file
* MOVE requests management
* Journal entries support
* Drop Python 2.5 support

## 0.5 - Historical Artifacts

* Calendar depth
* MacOS and Windows support
* HEAD requests management
* htpasswd user from calendar path

## 0.4 - Hot Days Back

* Personal calendars
* Last-Modified HTTP header
* `no-ssl` and `foreground` options
* Default configuration file

## 0.3 - Dancing Flowers

* Evolution support
* Version management

## 0.2 - Snowflakes

* Sunbird pre-1.0 support
* SSL connection
* Htpasswd authentication
* Daemon mode
* User configuration
* Twisted dependency removed
* Python 3 support
* Real URLs for PUT and DELETE
* Concurrent modification reported to users
* Many bugs fixed (by Roger Wenham)

## 0.1 - Crazy Vegetables

* First release
* Lightning/Sunbird 0.9 compatibility
* Easy installer
