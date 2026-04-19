## Getting started

#### About Radicale

Radicale is a small but powerful CalDAV (calendars, todo-lists) and CardDAV
(contacts) server, that:

  * Shares calendars through CalDAV, WebDAV and HTTP.
  * Shares contacts through CardDAV, WebDAV and HTTP.
  * Supports events, todos, journal entries and business cards.
  * Works out-of-the-box, no installation nor configuration required.
  * Can warn users on concurrent editing.
  * Can limit access by authentication.
  * Can secure connections.
  * Works with many CalDAV and CardDAV clients.
  * Is GPLv3-licensed free software.

#### Installation

Radicale is really easy to install and works out-of-the-box.

```bash
$ python3 -m pip install --upgrade radicale==2.1.*
$ python3 -m radicale --config "" --storage-filesystem-folder=~/.var/lib/radicale/collections
```

When your server is launched, you can check that everything's OK by going
to http://localhost:5232/ with your browser!
You can login with any username and password.

Want more? Why don't you check our wonderful
[documentation](#documentation-1)?

#### What's New?

Latest version of Radicale is 2.1.12,
released on May 19, 2020
([changelog](https://github.com/Kozea/Radicale/blob/2.1.12/NEWS.md)).

[Read latest news…](#news)
