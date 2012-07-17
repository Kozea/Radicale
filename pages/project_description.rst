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

The Radicale Project is a complete calendar and contact storing and
manipulating solution. It can store multiple calendars and multiple address
books.

Calendar and contact manipulation is available from both local and distant
accesses, possibly limited through authentication policies.


What Radicale Is
================

Calendar and Contact Server
---------------------------

The Radicale Project is mainly a calendar and contact server, giving local and
distant access for reading, creating, modifying and deleting multiple
calendars through simplified CalDAV and CardDAV protocols.

Data can be encrypted by SSL, and their access can be restricted using 
different authentication methods.


What Radicale Is not and will not Be
====================================

Calendar or Contact User Agent
------------------------------

Radicale is a server, not a client. No interfaces will be created to work with
the server, as it is a really (really really) much more difficult task [#]_.

.. [#] I repeat: `we are lazy <http://www.radicale.org/technical_choices#lazy>`_.

Original Calendar or Contact Access Protocol
--------------------------------------------

CalDAV and CardDAV are not perfect protocols. We think that their main problem is
their complexity [#]_, that is why we decided not to implement the whole
standard but just enough to understand some of its client-side implementations
[#]_.

CalDAV and CardDAV are the best open standards available and they are quite widely 
used by both clients and servers[#]_. We decided to use it, and we will not use 
another one.

.. [#] Try to read :RFC:`4791`. Then try to understand it. Then try to
   implement it. Then try to read it again.
.. [#] Radicale is `oriented to calendar user agents
   <http://www.radicale.org/technical_choices#oriented-to-calendar-user-agents>`_.
.. [#] `CalDAV implementations
   <http://en.wikipedia.org/wiki/CalDAV#Implementations>`_,
   by Wikipedia.
