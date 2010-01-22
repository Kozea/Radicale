======
 News
======

Thursday, January 21, 2010
==========================

HTTPS connections and authentication have been added to Radicale this
week. Command-line options and personal configuration files are also ready for
test. According to the TODO file included in the package, the next version will
finally be 0.2, when sunbird 1.0 is out. Go, Mozilla hackers, go!

HTTPS connection
  HTTPS connections are now available using the standard TLS mechanisms. Give
  Radicale a private key and a certificate, and your data are now safe.

Authentication
  A simple authentication architecture is now available, allowing different
  methods thanks to different modules. The first two modules are ``fake`` (no
  authentication) and ``htpasswd`` (authentication with an ``htpasswd`` file
  created by the Apache tool). More methods such as LDAP are coming soon!

Friday, January 15, 2010
========================

Dropping Twisted dependency was the first step leading to another big feature:
Radicale now works with Python 3! The code was given a small cleanup, with some
simplifications mainly about encoding. Before the 0.1.1 release, feel free to
test the git repository, all Python versions from 2.5 should be OK.

Monday, January 11, 2010
========================

Good news! Radicale 0.1.1 will support Sunbird 1.0, but it has another great
feature: it has no external dependency! Twisted is no longer required for the
git version, removing about 50 lines of code.

Thursday, December 31, 2009
===========================

Lightning/Sunbird 1.0b2pre is out, adding minor changes in CalDAV support. A
`new commit <http://www.gitorious.org/radicale/radicale/commit/330283e>`_ makes
Radicale work with versions 0.9, 1.0b1 et 1.0b2. Moreover, etags are now quoted
according to the :RFC:`2616`.

Wednesday, December 9, 2009
===========================

`Thunderbird 3 is out
<http://www.mozillamessaging.com/thunderbird/3.0/releasenotes/>`_, and
Lightning/Sunbird 1.0 should be released in a few days. The `last commit in git
<http://gitorious.org/radicale/radicale/commit/6545bc8>`_ should make Radicale
work with versions 0.9 and 1.0b1pre. Radicale 0.1.1 will soon be released
adding support for version 1.0.

Tuesday, September 1, 2009
==========================

First Radicale release! Here is the changelog:

0.1 - Crazy Vegetables
----------------------

* First release
* Lightning/Sunbird 0.9 compatibility
* Easy installer

You can download this version on the `download page </download>`_.


Tuesday, July 28, 2009
======================

Radicale code has been released on Gitorious! Take a look at the `Radicale main
page on Gitorious <http://www.gitorious.org/radicale>`_ to view and download
source code.

Monday, July 27, 2009
=====================

The Radicale Project is launched. The code has been cleaned up and will be
available soon…
