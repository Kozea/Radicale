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

- iCalendar format (iCal) :RFC:`2445`
- HTTP Extensions for Distributed Authoring (WebDAV) :RFC:`2518`
- HyperText Transfer Protocol (HTTP) :RFC:`2616`
- WebDAV Access Control Protocol (ACL) :RFC:`3744`
- Calendaring Extensions to WebDAV (CalDAV) :RFC:`4791`
- HTTP Extensions for Web Distributed Authoring and Versioning
  (WebDAV) :RFC:`4918`
- Transport Layer Security (TLS) :RFC:`5246`

.. note::
   CalDAV implementation **requires** iCal, ACL, WebDAV, HTTP and TLS. The
   Radicale Server **does not and will not implement correctly** these
   standards, as explained in the `Development Choices`_ part.

Development Choices
-------------------

Important global development choices have been decided before writing
code. They are very useful to understand why the Radicale Project is
different from other CalDAV servers, and why features are included or
not in the code.

Oriented to Calendar User Agents
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Calendar servers work with calendar clients, using a defined protocol. CalDAV
is a good protocol, covering lots of features and use cases, but it is quite
hard to implement fully.

Some calendar servers have been created to follow the CalDAV RFC as much as
possible: Cosmo [#]_ and Darwin Calendar Server [#]_, for example, are much
more respectful of CalDAV and can be used with a large number of clients. They
are very good choices if you want to develop and test new CalDAV clients, or if
you have a possibly heterogeneous list of user agents.

The Radicale Server does not and **will not** support the CalDAV standard. It
supports the CalDAV implementation of different clients (only Sunbird 0.9+
[#]_, Lightning 0.9+ [#]_ and Evolution [#]_ for the moment).

.. [#] `Cosmo <http://chandlerproject.org/Projects/CosmoHome>`_, the web
   contents and calendars sharing server build to support the Chandler Project.

.. [#] `Darwin Calendar Server <http://trac.calendarserver.org/>`_, a
   standards-compliant calendar server mainly developed by Apple.

.. [#] `Mozilla Sunbird <http://www.mozilla.org/projects/calendar/sunbird/>`_,
   a cross-platform calendar client built upon Mozilla Toolkit.

.. [#] `Lightning <http://www.mozilla.org/projects/calendar/lightning/>`_, a
   calendar plugin bringing Sunbird in Mozilla Thunderbird.

.. [#] `Evolution <http://projects.gnome.org/evolution/>`_, the default mail,
   addressbook and calendaring client for Gnome.

Simple
~~~~~~

The Radicale Server is designed to be simple to install, simple to configure,
simple to use.

The installation is very easy, particularly with Linux: no dependencies, no
superuser rights needed, no configuration required. Launching the main script
out-of-the-box, as a normal user, is often the only step to have a simple remote
calendar access.

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
| Server    | Calendar Storage    | iCal                     |
|           +---------------------+--------------------------+
|           | Calendar Server     | CalDAV Server            |
+-----------+---------------------+--------------------------+
| Transfert | Network             | CalDAV (HTTP + TLS)      |
+-----------+---------------------+--------------------------+
| Client    | Calendar Client     | CalDAV Client            |
|           +---------------------+--------------------------+
|           | GUI                 | Terminal, GTK, etc.      |
+-----------+---------------------+--------------------------+

The Radical Project is **only the server part** of this architecture. 

Code Architecture
-----------------

*To be written*
