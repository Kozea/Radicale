=====================
 Project Description
=====================

:Author: Guillaume Ayoub

:Date: 2010-01-22

:Abstract: This document defines the main goals of the Radicale
 Project, what it covers and what it does not.

.. contents::

Main Goals
==========

The Radicale Project is a complete calendar storing and manipulating
solution. It can store multiple calendars.

Calendar manipulation is available from both local and distant
accesses, possibly limited through authentication policies.


What Radicale Is
================

Calendar Server
---------------

The Radicale Project is mainly a calendar server, giving local and
distant accessess for reading, creating, modifying and deleting
multiple calendars through a simplified CalDAV protocol.

Data can be encrypted by SSL, and their access can be restricted thanks to
different authentication methods.


What Radicale Is not and will not Be
====================================

Calendar User Agent
-------------------

Radicale is a server, not a client. No interfaces will be created to work with
the server, as it is a really (really really) much more difficult task [#]_.

.. [#] I repeat: `we are lazy <http://www.radicale.org/technical_choices#lazy>`_.

Original Calendar Store Implementation
--------------------------------------

Radicale stores iCal files, and nothing else. No easy way to store anything
else, as our iCal library does not know anything of the iCal norm: it just
receives iCal strings from the client and stores it after a really minimal
parsing.

Radicale has no idea of most of the iCal semantics. No joke! Dates, timezones,
titles, contents, status, repetitions are never understood, they are just
stored and replied as they are sent by the client. This is why storing anything
but iCal files (databases, Evolution Data Server, etc.) is impossible with
Radicale.

Original Calendar Access Protocol
---------------------------------

CalDAV is not a perfect protocol. We think that its main problem is its
complexity [#]_, that is why we decided not to implement the whole standard but
just enough to understand some of its client-side implementations [#]_.

CalDAV is not a perfect protocol, but it is the best open standard available
and is quite widely used by both clients and servers [#]_. We decided to use it,
and we will not use another one.

.. [#] Try to read :RFC:`4791`. Then try to understand it. Then try to
   implement it. Then try to read it again.
.. [#] Radicale is `oriented to calendar user agents
   <http://www.radicale.org/technical_choices#oriented-to-calendar-user-agents>`_.
.. [#] `Popularity of CalDAV <http://en.wikipedia.org/wiki/CalDAV#Popularity>`_,
   by Wikipedia.
