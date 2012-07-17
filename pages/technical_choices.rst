===================
 Technical Choices
===================

:Author: Guillaume Ayoub

:Date: 2010-01-22

:Abstract: This document describes the global technical choices of the
 Radicale Project and the global architectures of its different parts.

.. contents::

Global Technical Choices
========================

General Description
-------------------

The Radicale Project aims to be a light solution, easy to use, easy to
install, easy to configure. As a consequence, it requires few software
dependencies and is pre-configured to work out-of-the-box.

The Radicale Project runs on most of the UNIX-like platforms (Linux,
\*BSD, MacOS X) and Windows. It is free and open-source software.

Language
--------

The different parts of the Radicale Project are written in
Python. This is a high-level language, fully object-oriented,
available for the main operating systems and released with a lot of
useful libraries.

Protocols and Formats
---------------------

The main protocols and formats fully or partially implemented in the
Radicale Project are described by RFCs:

- HyperText Transfer Protocol (HTTP) :RFC:`2616`
- WebDAV Access Control Protocol (ACL) :RFC:`3744`
- Calendaring Extensions to WebDAV (CalDAV) :RFC:`4791`
- HTTP Extensions for Web Distributed Authoring and Versioning
  (WebDAV) :RFC:`4918`
- Transport Layer Security (TLS) :RFC:`5246`
- iCalendar format (iCal) :RFC:`5545`
- vCard Format Specification :RFC:`6350`
- vCard Extensions to Web Distributed Authoring and Versioning (CardDAV)
  :RFC:`6352`

.. note::
   CalDAV and CardDAV implementations **require** iCal, vCard, ACL, WebDAV,
   HTTP and TLS. The Radicale Server **does not and will not implement
   correctly** these standards, as explained in the `Development Choices`_
   part.

Development Choices
-------------------

Important global development choices have been decided before writing
code. They are very useful to understand why the Radicale Project is different
from other CalDAV and CardDAV servers, and why features are included or not in
the code.

Oriented to Calendar and Contact User Agents
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Calendar and contact servers work with calendar and contact clients, using a
defined protocol. CalDAV and CardDAV are good protocols, covering lots of
features and use cases, but it is quite hard to implement fully.

Some calendar servers have been created to follow the CalDAV and CardDAV RFCs
as much as possible: Davical [#]_, Cosmo [#]_ and Darwin Calendar Server [#]_,
for example, are much more respectful of CalDAV and CardDAV and can be used
with a large number of clients. They are very good choices if you want to
develop and test new CalDAV clients, or if you have a possibly heterogeneous
list of user agents.

The Radicale Server does not and **will not** support the CalDAV and CardDAV
standards. It supports the CalDAV and CardDAV implementations of different
clients (Lightning, Evolution, Android, iPhone and iCal, more are coming [#]_).

.. [#] `Davical <http://www.davical.org/>`_, a standards-compliant calendar
   server.

.. [#] `Cosmo <http://chandlerproject.org/Projects/CosmoHome>`_, the web
   contents and calendars sharing server build to support the Chandler Project.

.. [#] `Darwin Calendar Server <http://trac.calendarserver.org/>`_, a
   standards-compliant calendar server mainly developed by Apple.

.. [#] A feature request called `Support for additional clients
   <http://redmine.kozea.fr/issues/55>`_ is open to follow the work done to
   support more clients.

Simple
~~~~~~

The Radicale Server is designed to be simple to install, simple to configure,
simple to use.

The installation is very easy, particularly with Linux: no dependencies, no
superuser rights needed, no configuration required. Launching the main script
out-of-the-box, as a normal user, is often the only step to have a simple remote
calendar and contact access.

Contrary to other servers that are often complicated, require high privileges
or need a strong configuration, the Radicale Server can (sometimes, if not
often) be launched in a couple of minutes, if you follow the `User
Documentation <http://www.radicale.org/user_documentation>`_.

Lazy
~~~~

We, Radicale Project developers, are lazy. That is why we have chosen Python:
no more ``;`` or ``{}`` [#]_. This is also why our server is lazy.

The CalDAV RFC defines what must be done, what can be done and what cannot be
done. Many violations of the protocol are totally defined and behaviours are
given in such cases.

The Radicale Server assumes that the clients are perfect and that protocol
violations do not exist. That is why most of the errors in client requests have
undetermined consequences for the lazy server that can reply good answers, bad
answers, or even no answer.

.. [#] Who says "Ruby is even less verbose!" should read the
   :PEP:`20`.

Architectures
=============

General Architecture
--------------------

Here is a simple overview of the global architecture for reaching a 
calendar through network:

+-----------+---------------------+--------------------------+
|   Part    |        Layer        |    Protocol or Format    |
+===========+=====================+==========================+
| Server    | Calendar/Contact    | iCal/vCard               |
|           | Storage             |                          |
|           +---------------------+--------------------------+
|           | Calendar/Contact    | CalDAV/CardDAV Server    |
|           | Server              |                          |
+-----------+---------------------+--------------------------+
| Transfer  | Network             | CalDAV/CardDAV           |
|           |                     | (HTTP + TLS)             |
+-----------+---------------------+--------------------------+
| Client    | Calendar/Contact    | CalDAV/CardDAV Client    |
|           | Client              |                          |
|           +---------------------+--------------------------+
|           | GUI                 | Terminal, GTK, etc.      |
+-----------+---------------------+--------------------------+

The Radicale Project is **only the server part** of this architecture. 

Code Architecture
-----------------

The package offers 8 modules.

``__main__``
  The main module provides a simple function called ``run``. Its main work is
  to read the configuration from the configuration file and from the options
  given in the command line; then it creates a server, according to the
  configuration.

``__init__``
  This is the core part of the module, with the code for the CalDAV server. The
  server inherits from a HTTP or HTTPS server class, which relies on the
  default HTTP server class given by Python. The code managing the different
  HTTP requests according to the CalDAV normalization is written here.

``config``
  This part gives a dict-like access to the server configuration, read from
  the configuration file. The configuration can be altered when launching the
  executable with some command line options.

``ical``
  In this module are written the classes to represent collections and items in
  Radicale. The simple iCalendar and vCard readers and writers are included in
  this file. The readers and writers are small and stupid: they do not fully
  understand the iCalendar format and do not know at all what a date is.

``xmlutils``
  The functions defined in this module are mainly called by the CalDAV server
  class to read the XML part of the request, read or alter the calendars, and
  create the XML part of the response. The main part of this code relies on
  ElementTree.

``log``
  The ``start`` function provided by this module starts a logging mechanism
  based on the default Python logging module. Logging options can be stored in
  a logging configuration file.

``acl``
  This module is a set of Access Control Lists, a set of methods used by
  Radicale to manage rights to access the calendars. When the CalDAV server is
  launched, an Access Control List is chosen in the set, according to the
  configuration. The HTTP requests are then filtered to restrict the access
  using a list of login/password-based access controls.

``storage``
  This folder is a set of storage modules able to read and write
  collections. The only one is now ``filesystem``, storing each collection into
  one flat plain-text file.
