This is a list of clients that have been tested successfully and how to set them up.

Test server: radicale-gae.appspot.com
(SSL)

Or, when run locally:

Local development server: localhost:8080
(no SSL, you might get a warning about insecure connection)

=========
MacOS 10.9.4, Contacts 8.0 (1371)
=========

Contacts 
> Add Account 
> Other Contacts Account

then:

CardDAV (default)
user name = test
password = <anything>
server address = <server>

=========
MacOS 10.9.4, Calendar 7.0 (1841.1)
=========

Calendar 
> Add Account 
> Add CalDAV account

then, if no SSL (in the case of the Local Development Server):

account type = Advanced
user name = test
password = <anything>
server address = <server>
server path = / (this is needed, empty won't work)
port = <leave empty, specified in server address)
use SSL = <unchecked>
use Kerberos = <unchecked>

or if SSL (in production):

account type = Manual
user name = test
password = <anything>
server address = <server>

(account type = "Automatic" does not seem to work)

=========
iOS 7.1.2, Contacts
=========

Settings 
> Mail, Contacts, calendar
> Add Account
> Other
> CONTACTS / Add CardDAV Account

then:

server = <server>
user name = test
password = <anything>
description = <anything>

=========
iOS 7.1.2, Calendar
=========

Settings 
> Mail, Contacts, calendar
> Add Account
> Other
> CALENDARS / Add CalDAV Account

then:

server = <server>
user name = test
password = <anything>
description = <anything>

