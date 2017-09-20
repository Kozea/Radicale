---
layout: page
title: Architecture
permalink: /architecture/
---

Radicale is a really small piece of software, but understanding it is not as
easy as it seems. But don't worry, reading this short page is enough to
understand what a CalDAV/CardDAV server is, and how Radicale's code is
organized.


## General Architecture

Here is a simple overview of the global architecture for reaching a calendar or
an address book through network:

<table>
  <thead>
    <tr>
      <th>Part</th>
      <th>Layer</th>
      <th>Protocol or Format</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td rowspan="2">Server</td>
      <td>Calendar/Contact Storage</td>
      <td>iCal/vCard</td>
    </tr>
    <tr>
      <td>Calendar/Contact Server</td>
      <td>CalDAV/CardDAV Server</td>
    </tr>
    <tr>
      <td>Transfer</td>
      <td>Network</td>
      <td>CalDAV/CardDAV (HTTP + TLS)</td>
    </tr>
    <tr>
      <td rowspan="2">Client</td>
      <td>Calendar/Contact Client</td>
      <td>CalDAV/CardDAV Client</td>
    </tr>
    <tr>
      <td>GUI</td>
      <td>Terminal, GTK, Web interface, etc.</td>
    </tr>
  </tbody>
</table>

Radicale is **only the server part** of this architecture.

Please note that:

- CalDAV and CardDAV are superset protocols of WebDAV,
- WebDAV is a superset protocol of HTTP.

Radicale being a CalDAV/CardDAV server, it also can be seen as a special WebDAV
and HTTP server.

Radicale is **not the client part** of this architecture. It means that
Radicale never draws calendars, address books, events and contacts on the
screen. It only stores them and give the possibility to share them online with
other people.

If you want to see or edit your events and your contacts, you have to use
another software called a client, that can be a "normal" applications with
icons and buttons, a terminal or another web application.


## Code Architecture

The ``radicale`` package offers 9 modules.

`__main__`
: The main module provides a simple function called run. Its main work is to
  read the configuration from the configuration file and from the options given
  in the command line; then it creates a server, according to the configuration.

`__init__`
: This is the core part of the module, with the code for the CalDAV/CardDAV
  server. The server inherits from a WSGIServer server class, which relies on
  the default HTTP server class given by Python. The code managing the
  different HTTP requests according to the CalDAV/CardDAV normalization is
  written here.

`config`
: This part gives a dict-like access to the server configuration, read from the
  configuration file. The configuration can be altered when launching the
  executable with some command line options.

`xmlutils`
: The functions defined in this module are mainly called by the CalDAV/CardDAV
  server class to read the XML part of the request, read or alter the
  calendars, and create the XML part of the response. The main part of this
  code relies on ElementTree.

`log`
: The start function provided by this module starts a logging mechanism based
  on the default Python logging module. Logging options can be stored in a
  logging configuration file.

`auth`
: This module provides a default authentication manager equivalent to Apache's
  htpasswd. Login + password couples are stored in a file and used to
  authenticate users. Passwords can be encrypted using various methods. Other
  authentication methods can inherit from the base class in this file and be
  provided as plugins.

`rights`
: This module is a set of Access Control Lists, a set of methods used by
  Radicale to manage rights to access the calendars. When the CalDAV/CardDAV
  server is launched, an Access Control List is chosen in the set, according to
  the configuration. The HTTP requests are then filtered to restrict the access
  depending on who is authenticated. Other configurations can be written using
  regex-based rules. Other rights managers can also inherit from the base class
  in this file and be provided as plugins.

`storage`
: In this module are written the classes representing collections and items in
  Radicale, and the class storing these collections and items in your
  filesystem. Other storage classes can inherit from the base class in this
  file and be provided as plugins.

`web`
: This module contains the web interface.
