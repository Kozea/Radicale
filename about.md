---
layout: page
title: About
permalink: /about/
---

## Main Goals

Radicale is a complete calendar and contact storing and manipulating
solution. It can store multiple calendars and multiple address books.

Calendar and contact manipulation is available from both local and distant
accesses, possibly limited through authentication policies.

It aims to be a lightweight solution, easy to use, easy to install, easy to
configure. As a consequence, it requires few software dependencies and is
pre-configured to work out-of-the-box.

Radicale is written in Python. It runs on most of the UNIX-like platforms
(Linux, \*BSD, macOS) and Windows. It is free and open-source software.

## What Radicale Will Never Be

Radicale is a server, not a client. No interfaces will be created to work with
the server, as it is a really (really really) much more difficult task.

CalDAV and CardDAV are not perfect protocols. We think that their main problem
is their complexity, that is why we decided not to implement the whole standard
but just enough to understand some of its client-side implementations.

CalDAV and CardDAV are the best open standards available and they are quite
widely used by both clients and servers. We decided to use it, and we will not
use another one.

## Technical Choices

Important global development choices have been decided before writing
code. They are very useful to understand why the Radicale Project is different
from other CalDAV and CardDAV servers, and why features are included or not in
the code.

### Oriented to Calendar and Contact User Agents

Calendar and contact servers work with calendar and contact clients, using a
defined protocol. CalDAV and CardDAV are good protocols, covering lots of
features and use cases, but it is quite hard to implement fully.

Some calendar servers have been created to follow the CalDAV and CardDAV RFCs
as much as possible: [Davical](http://www.davical.org/),
[Baïkal](http://sabre.io/baikal/) and
[Darwin Calendar Server](http://trac.calendarserver.org/), for example, are
much more respectful of CalDAV and CardDAV and can be used with a large number
of clients. They are very good choices if you want to develop and test new
CalDAV clients, or if you have a possibly heterogeneous list of user agents.

Even if it tries it best to follow the RFCs, Radicale does not and **will not**
blindly implements the CalDAV and CardDAV standards. It is mainly designed to
support the CalDAV and CardDAV implementations of different clients.

### Simple

Radicale is designed to be simple to install, simple to configure, simple to
use.

The installation is very easy, particularly with Linux: one dependency, no
superuser rights needed, no configuration required, no database. Installing and
launching the main script out-of-the-box, as a normal user, are often the only
steps to have a simple remote calendar and contact access.

Contrary to other servers that are often complicated, require high privileges
or need a strong configuration, the Radicale Server can (sometimes, if not
often) be launched in a couple of minutes, if you follow the
[tutorial]({{ site.baseurl }}/tutorial/).

### Lazy

The CalDAV RFC defines what must be done, what can be done and what cannot be
done. Many violations of the protocol are totally defined and behaviours are
given in such cases.

Radicale often assumes that the clients are perfect and that protocol
violations do not exist. That is why most of the errors in client requests have
undetermined consequences for the lazy server that can reply good answers, bad
answers, or even no answer.

## History

Radicale has been started as a (free topic) stupid school project replacing
another (assigned topic) even more stupid school project.

At the beginning, it was just a proof-of-concept. The main goal was to write a
small, dirty and simple CalDAV server working with Lightning, using no external
libraries. That's how we created a piece of code that's (quite) easy to
understand, to use and to hack.

The [first lines](https://github.com/Kozea/Radicale/commit/b1591aea) have been
added to the SVN (!) repository as I was drinking (many) beers at the very end
of 2008 (Python 2.6 and 3.0 were just released). It's now packaged for a
growing number of Linux distributions.

And that was fun going from here to there thanks to you!
