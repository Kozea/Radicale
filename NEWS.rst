======
 News
======


0.9 - *Not released yet*
========================

* Custom handlers for auth, storage and rights (by Sergey Fursov)
* Add support for current-user-principal (by Christoph Polcin)
* 1-file-per-event storage (by Jean-Marc Martins)
* Git support for filesystem storages (by Jean-Marc Martins)
* DB storage working with PostgreSQL, MariaDB and SQLite (by Jean-Marc Martins)
* Clean rights manager based on regular expressions (by Sweil)
* Support of contacts for Apple's clients
* Support colors (by Jochen Sprickerhof)
* Decode URLs in XML (by Jean-Marc Martins)
* Fix PAM authentication (by Stepan Henek)
* Use consistent etags (by 9m66p93w)


0.8 - Rainbow
=============

* New authentication and rights management modules (by Matthias Jordan)
* Experimental database storage
* Command-line option for custom configuration file (by Mark Adams)
* Root URL not at the root of a domain (by Clint Adams, Fabrice Bellet, Vincent Untz)
* Improved support for iCal, CalDAVSync, CardDAVSync, CalDavZAP and CardDavMATE
* Empty PROPFIND requests handled (by Christoph Polcin)
* Colon allowed in passwords
* Configurable realm message


0.7.1 - Waterfalls
==================

* Many address books fixes
* New IMAP ACL (by Daniel Aleksandersen)
* PAM ACL fixed (by Daniel Aleksandersen)
* Courier ACL fixed (by Benjamin Frank)
* Always set display name to collections (by Oskari Timperi)
* Various DELETE responses fixed


0.7 - Eternal Sunshine
======================

* Repeating events
* Collection deletion
* Courier and PAM authentication methods
* CardDAV support
* Custom LDAP filters supported


0.6.4 - Tulips
==============

* Fix the installation with Python 3.1


0.6.3 - Red Roses
=================

* MOVE requests fixed
* Faster REPORT answers
* Executable script moved into the package


0.6.2 - Seeds
=============

* iPhone and iPad support fixed
* Backslashes replaced by slashes in PROPFIND answers on Windows
* PyPI archive set as default download URL


0.6.1 - Growing Up
==================

* Example files included in the tarball
* htpasswd support fixed
* Redirection loop bug fixed
* Testing message on GET requests


0.6 - Sapling
=============

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


0.5 - Historical Artifacts
==========================

* Calendar depth
* MacOS and Windows support
* HEAD requests management
* htpasswd user from calendar path


0.4 - Hot Days Back
===================

* Personal calendars
* Last-Modified HTTP header
* ``no-ssl`` and ``foreground`` options
* Default configuration file


0.3 - Dancing Flowers
=====================

* Evolution support
* Version management


0.2 - Snowflakes
================

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


0.1 - Crazy Vegetables
======================

* First release
* Lightning/Sunbird 0.9 compatibility
* Easy installer
