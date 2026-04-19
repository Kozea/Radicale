## News


### May 19, 2020 - Radicale 1.1.7

Radicale 1.1.7 is out\!

#### 1.1.7 - Third Law of Nature

  - Fix error in `--export-storage`
  - Include documentation in source archive

### Jul 24, 2017 - Radicale 1.1.6

Radicale 1.1.6 is out\!

#### 1.1.6 - Third Law of Nature

  - Improve logging for `--export-storage`

### Jul 24, 2017 - Radicale 1.1.5

Radicale 1.1.5 is out\!

#### 1.1.5 - Third Law of Nature

  - Improve logging for `--export-storage`

### Jun 25, 2017 - Radicale 1.1.4

Radicale 1.1.4 is out\!

#### 1.1.4 - Third Law of Nature

  - Use shutil.move for `--export-storage`

### May 27, 2017 - Radicale 1.1.3

Radicale 1.1.3 is out\!

#### 1.1.3 - Third Law of Nature

  - Add a `--export-storage=FOLDER` command-line argument (by Unrud, see
    [#606](https://github.com/Kozea/Radicale/pull/606))

### April 19, 2017 - Radicale 1.1.2

Radicale 1.1.2 is out\!

#### 1.1.2 - Third Law of Nature

  - Security fix: Add a random timer to avoid timing oracles and simple
    bruteforce attacks when using the htpasswd authentication method.
  - Various minor fixes.

### December 31, 2015 - Radicale 1.1

Radicale 1.1 is out\!

#### 1.1 - Law of Nature

One feature in this release is **not backward compatible**:

  - Use the first matching section for rights (inspired from daald)

Now, the first section matching the path and current user in your custom
rights file is used. In the previous versions, the most permissive
rights of all the matching sections were applied. This new behaviour
gives a simple way to make specific rules at the top of the file
independant from the generic ones.

Many **improvements in this release are related to security**, you
should upgrade Radicale as soon as possible:

  - Improve the regex used for well-known URIs (by Unrud)
  - Prevent regex injection in rights management (by Unrud)
  - Prevent crafted HTTP request from calling arbitrary functions (by
    Unrud)
  - Improve URI sanitation and conversion to filesystem path (by Unrud)
  - Decouple the daemon from its parent environment (by Unrud)

Some bugs have been fixed and little enhancements have been added:

  - Assign new items to corret key (by Unrud)
  - Avoid race condition in PID file creation (by Unrud)
  - Improve the docker version (by cdpb)
  - Encode message and commiter for git commits
  - Test with Python 3.5

### September 14, 2015 - Radicale 1.0, what's next?

Radicale 1.0 is out\!

#### 1.0 - Sunflower

  - Enhanced performances (by Mathieu Dupuy)
  - Add MD5-APR1 and BCRYPT for htpasswd-based authentication (by
    Jan-Philip Gehrcke)
  - Use PAM service (by Stephen Paul Weber)
  - Don't discard PROPPATCH on empty collections (Markus Unterwaditzer)
  - Write the path of the collection in the git message (Matthew Monaco)
  - Tests launched on Travis

As explained in a previous
[mail](http://librelist.com/browser//radicale/2015/8/21/radicale-1-0-is-coming-what-s-next/),
this version is called 1.0 because:

  - there are no big changes since 0.10 but some small changes are
    really useful,
  - simple tests are now automatically launched on Travis, and more can
    be added in the future (<https://travis-ci.org/Kozea/Radicale>).

This version will be maintained with only simple bug fixes on a separate
git branch called `1.0.x`.

Now that this milestone is reached, it's time to think about the future.
When Radicale has been created, it was just a proof-of-concept. The main
goal was to write a small, stupid and simple CalDAV server working with
Lightning, using no external libraries. That's how we created a piece of
code that's (quite) easy to understand, to use and to hack.

The first lines have been added to the SVN (\!) repository as I was
drinking beers at the very end of 2008. It's now packaged for a growing
number of Linux distributions.

And that was fun going from here to there thanks to you. So… **Thank
you, you're amazing**. I'm so glad I've spent endless hours fixing
stupid bugs, arguing about databases and meeting invitations, reading
incredibly interesting RFCs and debugging with the fabulous clients from
Apple. I mean: that really, really was really, really cool :).

During these years, a lot of things have changed and many users now rely
on Radicale in production. For example, I use it to manage medical
calendars, with thousands requests per day. Many people are happy to
install Radicale on their small home servers, but are also frustrated by
performance and unsupported specifications when they're trying to use it
seriously.

So, now is THE FUTURE\! I think that Radicale 2.0 should:

  - rely on a few external libraries for simple critical points (dealing
    with HTTP and iCal for example),
  - be thread-safe,
  - be small,
  - be documented in a different way (for example by splitting the
    client part from the server part, and by adding use cases),
  - let most of the "auth" modules outside in external modules,
  - have more and more tests,
  - have reliable and faster filesystem and database storage mechanisms,
  - get a new design :).

I'd also secretly love to drop the Python 2.x support.

These ideas are not all mine (except from the really, really, really
important "design" point :p), they have been proposed by many developers
and users. I've just tried to gather them and keep points that seem
important to me.

Other points have been discussed with many users and contibutors,
including:

  - support of other clients, including Windows and BlackBerry phones,
  - server-side meeting invitations,
  - different storage system as default (or even unique?).

I'm not a huge fan of these features, either because I can't do anything
about them, or because I think that they're Really Bad Ideas®™. But I'm
ready to talk about them, because, well, I may not be always right\!

Need to talk about this? You know how to [contact us](#contribute)\!

### January 12, 2015 - Radicale 0.10

Radicale 0.10 is out\!

#### 0.10 - Lovely Endless Grass

  - Support well-known URLs (by Mathieu Dupuy)
  - Fix collection discovery (by Markus Unterwaditzer)
  - Reload logger config on SIGHUP (by Élie Bouttier)
  - Remove props files when deleting a collection (by Vincent Untz)
  - Support salted SHA1 passwords (by Marc Kleine-Budde)
  - Don't spam the logs about non-SSL IMAP connections to localhost (by
    Giel van Schijndel)

This version should bring some interesting discovery and
auto-configuration features, mostly with Apple clients.

Lots of love and kudos for the people who have spent hours to test
features and report issues, that was long but really useful (and some of
you have been really patient :p).

Issues are welcome, I'm sure that you'll find horrible, terrible, crazy
bugs faster than me. I'll release a version 0.10.1 if needed.

What's next? It's time to fix and improve the storage methods. A real
API for the storage modules is a good beginning, many pull requests are
already ready to be discussed and merged, and we will probably get some
good news about performance this time. Who said "databases, please"?

### July 12, 2013 - Radicale 0.8

Radicale 0.8 is out\!

#### 0.8 - Rainbow

  - New authentication and rights management modules (by Matthias
    Jordan)
  - Experimental database storage
  - Command-line option for custom configuration file (by Mark Adams)
  - Root URL not at the root of a domain (by Clint Adams, Fabrice
    Bellet, Vincent Untz)
  - Improved support for iCal, CalDAVSync, CardDAVSync, CalDavZAP and
    CardDavMATE
  - Empty PROPFIND requests handled (by Christoph Polcin)
  - Colon allowed in passwords
  - Configurable realm message

This version brings some of the biggest changes since Radicale's
creation, including an experimental support of database storage, clean
authentication modules, and rights management finally designed for real
users.

So, dear user, be careful: **this version changes important things in
the configuration file, so check twice that everything is OK when you
update to 0.8, or you can have big problems**.

More and more clients are supported, as a lot of bug fixes and features
have been added for this purpose. And before you ask: yes, 2 web-based
clients, [CalDavZAP and
CardDavMATE](http://www.inf-it.com/open-source/clients/), are now
supported\!

Even if there has been a lot of time to test these new features, I am
pretty sure that some really annoying bugs have been left in this
version. We will probably release minor versions with bugfixes during
the next weeks, and it will not take one more year to reach 0.8.1.

The documentation has been updated, but some parts are missing and some
may be out of date. You can [report
bugs](https://github.com/Kozea/Radicale/issues) or even [write
documentation directly on
GitHub](https://github.com/Kozea/Radicale/blob/website/pages/user_documentation.rst)
if you find something strange (and you probably will).

If anything is not clear, or if the way rights work is a bit complicated
to understand, or if you are so happy because everything works so well,
you can [share your thoughts](#contribute)\!

It has been a real pleasure to work on this version, with brilliant
ideas and interesting bug reports from the community. I'd really like to
thank all the people reporting bugs, chatting on IRC, sending mails and
proposing pull requests: you are awesome.

### August 3, 2012 - Radicale 0.7.1

Radicale 0.7.1 is out\!

#### 0.7.1 - Waterfalls

  - Many address books fixes
  - New IMAP ACL (by Daniel Aleksandersen)
  - PAM ACL fixed (by Daniel Aleksandersen)
  - Courier ACL fixed (by Benjamin Frank)
  - Always set display name to collections (by Oskari Timperi)
  - Various DELETE responses fixed

It's been a long time since the last version… As usual, many people have
contributed to this new version, that's a pleasure to get these pull
requests.

Most of the commits are bugfixes, especially about ACL backends and
address books. Many clients (including aCal and SyncEvolution) will be
much happier with this new version than with the previous one.

By the way, one main new feature has been added: a new IMAP ACL backend,
by Daniel. And about authentication, exciting features are coming soon,
stay tuned\!

Next time, as many mails have come from angry and desperate coders,
tests will be *finally* added to help them to add features and fix bugs.
And after that, who knows, it may be time to release Radicale 1.0…

### March 22, 2012 - Radicale 0.7

Radicale 0.7 is out, at least\!

#### 0.7 - Eternal Sunshine

  - Repeating events
  - Collection deletion
  - Courier and PAM authentication methods
  - CardDAV support
  - Custom LDAP filters supported

**A lot** of people have reported bugs, proposed new features, added
useful code and tested many clients. Thank you Lynn, Ron, Bill, Patrick,
Hidde, Gerhard, Martin, Brendan, Vladimir, and everybody I've forgotten.

### January 5, 2012 - Radicale 0.6.4, News from Calypso

New year, new release. Radicale 0.6.4 has a really short changelog:

#### 0.6.4 - Tulips

  - Fix the installation with Python 3.1

The bug was in fact caused by a [bug in
Python 3.1](http://bugs.python.org/issue9561), everything should be OK
now.

#### Calypso

After a lot of changes in Radicale, Keith Packard has decided to launch
a fork called [Calypso](http://keithp.com/blogs/calypso/), with nice
features such as a Git storage mechanism and a CardDAV support.

There are lots of differences between the two projects, but the final
goal for Radicale is to provide these new features as soon as possible.
Thanks to the work of Keith and other people on GitHub, a basic CardDAV
support has been added in the [carddav
branch](https://github.com/Kozea/Radicale/tree/carddav) and already
works with Evolution. Korganizer also works with existing address books,
and CardDAV-Sync will be tested soon. If you want to test other clients,
please let us know\!

### November 3, 2011 - Radicale 0.6.3

Radicale version 0.6.3 has been released, with bugfixes that could be
interesting for you\!

#### 0.6.3 - Red Roses

  - MOVE requests fixed
  - Faster REPORT answers
  - Executable script moved into the package

#### What's New Since 0.6.2?

The MOVE requests were suffering a little bug that is fixed now. These
requests are only sent by Apple clients, Mac users will be happy.

The REPORT request were really, really slow (several minutes for large
calendars). This was caused by an awful algorithm parsing the entire
calendar for each event in the calendar. The calendar is now only parsed
three times, and the events are found in a Python list, turning minutes
into seconds\! Much better, but far from perfection…

Finally, the executable script parsing the command line options and
starting the HTTP servers has been moved from the `radicale.py` file
into the `radicale` package. Two executable are now present in the
archive: the good old `radicale.py`, and `bin/radicale`. The second one
is only used by `setup.py`, where the hack used to rename `radicale.py`
into `radicale` has therefore been removed. As a consequence, you can
now launch Radicale with the simple `python -m radicale` command,
without relying on an executable.

#### Time for a Stable Release\!

The next release may be a stable release, symbolically called 1.0. Guess
what's missing? Tests, of course\!

A non-regression testing suite, based on the clients' requests, will
soon be added to Radicale. We're now thinking about a smart solution to
store the tests, to represent the expected answers and to launch the
requests. We've got crazy ideas, so be prepared: you'll definitely
*want* to write tests during the next weeks\!

Repeating events, PAM and Courier authentication methods have already
been added in master. You'll find them in the 1.0 release\!

#### What's Next?

Being stable is one thing, being cool is another one. If you want some
cool new features, you may be interested in:

  - WebDAV and CardDAV support
  - Filters and rights management
  - Multiple storage backends, such as databases and git
  - Freebusy periods
  - Email alarms

Issues have been reported in the bug tracker, you can follow there the
latest news about these features. Your beloved text editor is waiting
for you\!

### September 27, 2011 - Radicale 0.6.2

0.6.2 is out with minor bugfixes.

#### 0.6.2 - Seeds

  - iPhone and iPad support fixed
  - Backslashes replaced by slashes in PROPFIND answers on Windows
  - PyPI archive set as default download URL

### August 28, 2011 - Radicale 0.6.1, Changes, Future

As previously imagined, a new 0.6.1 version has been released, mainly
fixing obvious bugs.

#### 0.6.1 - Growing Up

  - Example files included in the tarball
  - htpasswd support fixed
  - Redirection loop bug fixed
  - Testing message on GET requests

The changelog is really small, so there should be no real new problems
since 0.6. The example files for logging, FastCGI and WSGI are now
included in the tarball, for the pleasure of our dear packagers\!

A new branch has been created for various future bug fixes. You can
expect to get more 0.6.x versions, making this branch a kind of "stable"
branch with no big changes.

#### GitHub, Mailing List, New Website

A lot of small changes occurred during the last weeks.

If you're interested in code and new features, please note that we moved
the project from Gitorious to `GitHub`. Being hosted by Gitorious was a
nice experience, but the service was not that good and we were missing
some useful features such as git hooks. Moreover, GitHub is really
popular, we're sure that we'll meet a lot of kind users and coders
there.

We've also created a `mailing-list on Librelist` to keep a public trace
of the mails we're receiving. It a bit empty now, but we're sure that
you'll soon write us some kind words. For example, you can tell us what
you think of our new website\!

#### Future Features

In the next weeks, new exciting features are coming in the master
branch\! Some of them are almost ready:

  - Henry-Nicolas has added the support for the PAM and
    Courier-Authdaemon authentication mechanisms.
  - An anonymous called Keith Packard has prepared some small changes,
    such as one file per event, cache and git versioning. Yes. Really.

As you can find in the [Radicale
Roadmap](http://redmine.kozea.fr/versions/), tests, rights and filters
are expected for 0.7.

### August 1, 2011 - Radicale 0.6 Released

Time for a new release with **a lot** of new exciting features\!

#### 0.6 - Sapling

  - WSGI support
  - IPv6 support
  - Smart, verbose and configurable logs
  - Apple iCal 4 and iPhone support (by Łukasz Langa)
  - CalDAV-Sync support (by Marten Gajda)
  - aCal support
  - KDE KOrganizer support
  - LDAP auth backend (by Corentin Le Bail)
  - Public and private calendars (by René Neumann)
  - PID file
  - MOVE requests management
  - Journal entries support
  - Drop Python 2.5 support

Well, it's been a little longer than expected, but for good reasons: a
lot of features have been added, and a lot of clients are known to work
with Radicale, thanks to kind contributors. That's definitely good
news\! But…

Testing all the clients is really painful, moreover for the ones from
Apple (I have no Mac nor iPhone of my own). We should seriously think of
automated tests, even if it's really hard to maintain, and maybe not
that useful. If you're interested in tests, you can look at [the
wonderful regression suite of
DAViCal](http://repo.or.cz/w/davical.git/tree/HEAD:/testing/tests/regression-suite).

The new features, for example the WSGI support, are also poorly
documented. If you have some Apache or lighttpd configuration working
with Radicale, you can make the world a little bit better by writing a
paragraph or two in the [Radicale
documentation](https://gitorious.org/radicale/website). It's simple
plain text, don't be afraid\!

Because of all these changes, Radicale 0.6 may be a little bit buggy; a
0.6.1 will probably be released soon, fixing small problems with clients
and features. Get ready to report bugs, I'm sure that you can find one
(and fix it)\!

### July 2, 2011 - Feature Freeze for 0.6

According to the
[roadmap](http://redmine.kozea.fr/projects/radicale/roadmap), a lot of
features have been added since Radicale 0.5, much more than expected.
It's now time to test Radicale with your favourite client and to report
bugs before we release the next stable version\!

Last week, the iCal and iPhone support written by Łukasz has been fixed
in order to restore the broken Lightning support. After two afternoons
of tests with Rémi, we managed to access the same calendar with
Lightning, iCal, iPhone and Evolution, and finally discovered that
CalDAV could also be a perfect instant messaging protocol between a Mac,
a PC and a phone.

After that, we've had the nice surprise to see events displayed without
a problem (but after some strange steps of configuration) by aCal on
Salem's Android phone.

It was Friday, fun fun fun fun.

So, that's it: Radicale supports Lightning, Evolution, Kontact, aCal for
Android, iPhone and iCal. Of course, before releasing a new tarball:

  - [documentation](#starting-the-client)
    is needed for the new clients that are not documented yet (Kontact,
    aCal and iPhone);
  - tests are welcome, particularly for the Apple clients that I can't
    test anymore;
  - no more features will be added, they'll wait in separate branches
    for the 0.7 development.

Please [report bugs](http://redmine.kozea.fr/projects/radicale/issues)
if anything goes wrong during your tests, or just let us know [by Jabber
or by mail](#contribute) if everything is OK.

### May 1, 2011 - Ready for WSGI

Here it is\! Radicale is now ready to be launched behind your favourite
HTTP server (Apache, Lighttpd, Nginx or Tomcat for example). That's
really good news, because:

  - Real HTTP servers are much more efficient and reliable than the
    default Python server used in Radicale;
  - All the authentication backends available for your server will be
    available for Radicale;
  - Thanks to [flup](http://trac.saddi.com/flup), Radicale can be
    interfaced with all the servers supporting CGI, AJP, FastCGI or
    SCGI;
  - Radicale works very well without any additional server, without any
    dependencies, without configuration, just as it was working before;
  - This one more feature removes useless code, less is definitely more.

The WSGI support has only be tested as a stand-alone executable and
behind Lighttpd, you should definitely try if it works with you
favourite server too\!

No more features will be added before (quite) a long time, because a lot
of documentation and test is waiting for us. If you want to write
tutorials for some CalDAV clients support (iCal, Android, iPhone), HTTP
servers support or logging management, feel free to fork the
[documentation git repository](https://gitorious.org/radicale/website)
and ask for a merge. It's plain text, I'm sure you can do it\!

### April 30, 2011 - Apple iCal Support

After a long, long work, the iCal support has finally been added to
Radicale\! Well, this support is only for iCal 4 and is highly
experimental, but you can test it right now with the git master branch.
Bug reports are welcome\!

Dear MacOS users, you can thank all the gentlemen who sended a lot of
debugging iformation. Special thanks to Andrew from DAViCal, who helped
us a lot with his tips and his tests, and Rémi Hainaud who lent his
laptop for the final tests.

The default server address is `localhost:5232/user/`, where calendars
can be added. Multiple calendars and owner-less calendars are not tested
yet, but they should work quite well. More documentation will be added
during the next days. It will then be time to release the Radicale 0.6
version, and work on the WSGI support.

### April 25, 2011 - Two Features and One New Roadmap

Two features have just reached the master branch, and the roadmap has
been refreshed.

#### LDAP Authentication

Thanks to Corentin, the LDAP authentication is now included in Radicale.
The support is experimental and may suffer unstable connexions and
security problems. If you are interested in this feature (a lot of
people seem to be), you can try it and give some feedback.

No SSL support is included yet, but this may be quite easy to add. By
the way, serious authentication methods will rely on a "real" HTTP
server, as soon as Radicale supports WSGI.

#### Journal Entries

Mehmet asked for the journal entries (aka. notes or memos) support,
that's done\! This also was an occasion to clean some code in the iCal
parser, and to add a much better management of multi-lines entries.
People experiencing crazy `X-RADICALE-NAME` entries can now clean their
files, Radicale won't pollute them again.

#### New Roadmap

Except from htpasswd and LDAP, most of the authentication backends
(database, SASL, PAM, user groups) are not really easy to include in
Radicale. The easiest solution to solve this problem is to give Radicale
a CGI support, to put it behind a solid server such as Apache. Of
course, CGI is not enough: a WSGI support is quite better, with the
FastCGI, AJP and SCGI backends offered by
[flup](http://trac.saddi.com/flup/). Quite exciting, isn't it?

That's why it was important to add new versions on the roadmap. The 0.6
version is now waiting for the Apple iCal support, and of course for
some tests to kill the last remaining bugs. The only 0.7 feature will be
WSGI, allowing many new authentication methods and a real multithread
support.

After that, 0.8 may add CalDAV rights and filters, while 1.0 will draw
thousands of rainbows and pink unicorns (WebDAV sync, CardDAV,
Freebusy). A lot of funky work is waiting for you, hackers\!

#### Bugs

Many bugs have also been fixed, most of them due to the owner-less
calendars support. Radicale 0.6 may be out in a few weeks, you should
spend some time testing the master branch and filling the bug tracker.

### April 10, 2011 - New Features

Radicale 0.5 was released only 8 days ago, but 3 new features have
already been added to the master branch:

  - IPv6 support, with multiple addresses/ports support
  - Logs and debug mode
  - Owner-less calendars

Most of the code has been written by Necoro and Corentin, and that was
not easy at all: Radicale is now multithreaded\! For sure, you can find
many bugs and report them on the [bug
tracker](http://redmine.kozea.fr/projects/radicale/issues). And if
you're fond of logging, you can even add a default configuration file
and more debug messages in the source.

### April 2, 2011 - Radicale 0.5 Released

Radicale 0.5 is out\! Here is what's new:

#### 0.5 - Historical Artifacts

  - Calendar depth
  - iPhone support
  - MacOS and Windows support
  - HEAD requests management
  - htpasswd user from calendar path

iPhone support, but no iCal support for 0.5, despite our hard work,
sorry\! After 1 month with no more activity on the dedicated bug, it was
time to forget it and hack on new awesome features. Thanks for your
help, dear Apple users, I keep the hope that one day, Radicale will work
with you\!

So, what's next? As promised, some cool git branches will soon be
merged, with LDAP support, logging, IPv6 and anonymous calendars. Sounds
pretty cool, heh? Talking about new features, more and more people are
asking for a CardDAV support in Radicale. [A git
branch](https://www.gitorious.org/~deepdiver/radicale/deepdivers-radicale)
and [a feature request](http://redmine.kozea.fr/issues/247) are open,
feel free to hack and discuss.

### February 3, 2011 - Jabber Room and iPhone Support

After a lot of help and testing work from Andrew, Björn, Anders, Dorian
and Pete (and other ones we could have forgotten), a simple iPhone
support has been added in the git repository. If you are interested, you
can test this feature *right now* by [downloading the latest git
version](#git-repository) (a tarball is even
available too if you don't want or know how to use git).

No documentation has been written yet, but using the right URL in the
configuration should be enough to synchronize your calendars. If you
have any problems, you can ask by joining our new Jabber room:
<radicale@room.jabber.kozea.fr>.

Radicale 0.5 will be released as soon as the iCal support is ready. If
you have an Apple computer, Python skills and some time to spend, we'd
be glad to help you debugging Radicale.

### October 21, 2010 - News from Radicale

During the last weeks, Radicale has not been idle, even if no news have
been posted since August. Thanks to Pete, Pierre-Philipp and Andrew,
we're trying to add a better support on MacOS, Windows and mobile
devices like iPhone and Android-based phones.

All the tests on Windows have been successful: launching Radicale and
using Lightning as client works without any problems. On Android too,
some testers have reported clients working with Radicale. These were the
good news.

The bad news come from Apple: both iPhone and MacOS default clients are
not working yet, despite the latest enhancements given to the PROPFIND
requests. The problems are quite hard to debug due to our lack of Apple
hardware, but Pete is helping us in this difficult quest\! Radicale 0.5
will be out as soon as these two clients are working.

Some cool stuff is coming next, with calendar collections and groups,
and a simple web-based CalDAV client in early development. Stay tuned\!

### August 8, 2010 - Radicale 0.4 Released

Radicale 0.4 is out\! Here is what's new:

#### 0.4 - Hot Days Back

  - Personal calendars
  - HEAD requests
  - Last-Modified HTTP header
  - `no-ssl` and `foreground` options
  - Default configuration file

This release has mainly been released to help our dear packagers to
include a default configuration file and to write init scripts. Big
thanks to Necoro for his work on the new Gentoo ebuild\!

### July 4, 2010 - Three Features Added Last Week

Some features have been added in the git repository during the last
weeks, thanks to Jerome and Mariusz\!

  - Personal Calendars  
    Calendars accessed through the htpasswd ACL module can now be
    personal. Thanks to the `personal` option, a user called `bob` can
    access calendars at `/bob/*` but not to the `/alice/*` ones.

  - HEAD Requests  
    Radicale can now answer HEAD requests. HTTP headers can be retrieved
    thanks to this request, without getting contents given by the GET
    requests.

  - Last-Modified HTTP header  
    The Last-Modified header gives the last time when the calendar has
    been modified. This is used by some clients to cache the calendars
    and not retrieving them if they have not been modified.

### June 14, 2010 - Radicale 0.3 Released

Radicale 0.3 is out\! Here is what’s new:

#### 0.3 - Dancing Flowers

  - Evolution support
  - Version management

The website changed a little bit too, with some small HTML5 and CSS3
features such as articles, sections, transitions, opacity, box shadows
and rounded corners. If you’re reading this website with Internet
Explorer, you should consider using a standard-compliant browser\!

Radicale is now included in Squeeze, the testing branch of Debian. A
[Radicale ebuild for
Gentoo](http://bugs.gentoo.org/show_bug.cgi?id=322811) has been proposed
too. If you want to package Radicale for another distribution, you’re
welcome\!

Next step is 0.5, with calendar collections, and Windows and MacOS
support.

### May 31, 2010 - May News

#### News from contributors

Jonas Smedegaard packaged Radicale for Debian last week. Two packages,
called `radicale` for the daemon and `python-radicale` for the module,
have been added to Sid, the unstable branch of Debian. Thank you,
Jonas\!

Sven Guckes corrected some of the strange-English-sentences present on
this website. Thank you, Sven\!

#### News from software

A simple `VERSION` has been added in the library: you can now play with
`radicale.VERSION` and `$radicale --version`.

After playing with the version (should not be too long), you may notice
that the next version is called 0.3, and not 0.5 as previously decided.
The 0.3 main goal is to offer the support for Evolution as soon as
possible, without waiting for the 0.5. After more than a month of test,
we corrected all the bugs we found and everything seems to be fine; we
can imagine that a brand new tarball will be released during the first
days of June.

### April 19, 2010 - Evolution Supported

Radicale now supports another CalDAV client: [Evolution, the default
mail, addressbook and calendaring client for
Gnome](http://projects.gnome.org/evolution/). This feature was quite
easy to add, as it required less than 20 new lines of code in the
requests handler.

If you are interested, just clone the [git
repository](http://www.gitorious.org/radicale/radicale).

### April 13, 2010 - Radicale 0.2 Released

Radicale 0.2 is out\! Here is what’s new:

#### 0.2 - Snowflakes

  - Sunbird pre-1.0 support
  - SSL connection
  - Htpasswd authentication
  - Daemon mode
  - User configuration
  - Twisted dependency removed
  - Python 3 support
  - Real URLs for PUT and DELETE
  - Concurrent modification reported to users
  - Many bugs fixed by Roger Wenham

First of all, we would like to thank Roger Wenham for his bugfixes and
his supercool words.

You may have noticed that Sunbird 1.0 has not been released, but
according to the Mozilla developers, 1.0pre is something like a final
version.

You may have noticed too that Radicale can be [downloaded from
PyPI](http://pypi.python.org/pypi/Radicale/0.2). Of course, it is also
available on the [download page](#download).

### January 21, 2010 - HTTPS and Authentication

HTTPS connections and authentication have been added to Radicale this
week. Command-line options and personal configuration files are also
ready for test. According to the TODO file included in the package, the
next version will finally be 0.2, when sunbird 1.0 is out. Go, Mozilla
hackers, go\!

  - HTTPS connection  
    HTTPS connections are now available using the standard TLS
    mechanisms. Give Radicale a private key and a certificate, and your
    data are now safe.

  - Authentication  
    A simple authentication architecture is now available, allowing
    different methods thanks to different modules. The first two modules
    are `fake` (no authentication) and `htpasswd` (authentication with
    an `htpasswd` file created by the Apache tool). More methods such as
    LDAP are coming soon\!

### January 15, 2010 - Ready for Python 3

Dropping Twisted dependency was the first step leading to another big
feature: Radicale now works with Python 3\! The code was given a small
cleanup, with some simplifications mainly about encoding. Before the
0.1.1 release, feel free to test the git repository, all Python versions
from 2.5 should be OK.

### January 11, 2010 - Twisted no Longer Required

Good news\! Radicale 0.1.1 will support Sunbird 1.0, but it has another
great feature: it has no external dependency\! Twisted is no longer
required for the git version, removing about 50 lines of code.

### December 31, 2009 - Lightning and Sunbird 1.0b2pre Support

Lightning/Sunbird 1.0b2pre is out, adding minor changes in CalDAV
support. A [new
commit](http://www.gitorious.org/radicale/radicale/commit/330283e) makes
Radicale work with versions 0.9, 1.0b1 et 1.0b2. Moreover, etags are now
quoted according to the
[RFC 2616](http://www.faqs.org/rfcs/rfc2616.html "RFC 2616").

### December 9, 2009 - Thunderbird 3 released

[Thunderbird 3 is
out](http://www.mozillamessaging.com/thunderbird/3.0/releasenotes/), and
Lightning/Sunbird 1.0 should be released in a few days. The [last commit
in git](http://gitorious.org/radicale/radicale/commit/6545bc8) should
make Radicale work with versions 0.9 and 1.0b1pre. Radicale 0.1.1 will
soon be released adding support for version 1.0.

### September 1, 2009 - Radicale 0.1 Released

First Radicale release\! Here is the changelog:

#### 0.1 - Crazy Vegetables

  - First release
  - Lightning/Sunbird 0.9 compatibility
  - Easy installer

You can download this version on the [download page](#download).

### July 28, 2009 - Radicale on Gitorious

Radicale code has been released on Gitorious\! Take a look at the
[Radicale main page on Gitorious](http://www.gitorious.org/radicale) to
view and download source code.

### July 27, 2009 - Radicale Ready to Launch

The Radicale Project is launched. The code has been cleaned up and will
be available soon…
