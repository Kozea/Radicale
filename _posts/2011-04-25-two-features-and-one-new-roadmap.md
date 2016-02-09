---
layout: page
title: Two Features and One New Roadmap
---

Two features have just reached the master branch, and the roadmap has been
refreshed.

### LDAP Authentication

Thanks to Corentin, the LDAP authentication is now included in Radicale. The
support is experimental and may suffer unstable connexions and security
problems. If you are interested in this feature (a lot of people seem to be),
you can try it and give some feedback.

No SSL support is included yet, but this may be quite easy to add. By the way,
serious authentication methods will rely on a "real" HTTP server, as soon as
Radicale supports WSGI.

### Journal Entries

Mehmet asked for the journal entries (aka. notes or memos) support, that's
done! This also was an occasion to clean some code in the iCal parser, and to
add a much better management of multi-lines entries. People experiencing crazy
`X-RADICALE-NAME` entries can now clean their files, Radicale won't pollute
them again.

### New Roadmap

Except from htpasswd and LDAP, most of the authentication backends (database,
SASL, PAM, user groups) are not really easy to include in Radicale. The easiest
solution to solve this problem is to give Radicale a CGI support, to put it
behind a solid server such as Apache. Of course, CGI is not enough: a WSGI
support is quite better, with the FastCGI, AJP and SCGI backends offered by
[flup](http://trac.saddi.com/flup/). Quite exciting, isn't it?

That's why it was important to add new versions on the roadmap. The 0.6 version
is now waiting for the Apple iCal support, and of course for some tests to kill
the last remaining bugs. The only 0.7 feature will be WSGI, allowing many new
authentication methods and a real multithread support.

After that, 0.8 may add CalDAV rights and filters, while 1.0 will draw
thousands of rainbows and pink unicorns (WebDAV sync, CardDAV, Freebusy). A lot
of funky work is waiting for you, hackers!

### Bugs

Many bugs have also been fixed, most of them due to the owner-less calendars
support. Radicale 0.6 may be out in a few weeks, you should spend some time
testing the master branch and filling the bug tracker.
