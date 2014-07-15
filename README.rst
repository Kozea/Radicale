=========
 Goal of this project
=========

The goal of this project is to patch Radicale so that it can run on Google AppEngine.

See this discussion thread on the Radicale mailing list: `Radicale on GoogleAppengine <http://librelist.com/browser//radicale/2014/6/21/radicale-on-googleappengine/>`_

=========
 What works
=========

Tested very quickly abut creating / updating and deleting items appear to work fine.

Feel free to try this test server:

.. code-block:: bash

	https://radicale-gae.appspot.com
	username = test
	password = <anything>

=========
 About Radicale
=========

Radicale is a free and open-source CalDAV and CardDAV server.

For complete documentation, please visit the `Radicale online documentation
<http://www.radicale.org/documentation>`_

=========
 Client setup
=========

You should be able to use any CalDAV/CardDAV that works with Radicale

Test server: radicale-gae.appspot.com
(SSL)

Or, when run locally:

Local development server: localhost:8080
(no SSL, you might get a warning about insecure connection)

credentials:

.. code-block:: bash
	username = test
	password = <anything>

---------
MacOS 10.9.4, Contacts 8.0 (1371)
---------

* Contacts 
* Add Account 
* Other Contacts Account

then:

.. code-block:: bash
	CardDAV (default)
	user name = test
	password = <anything>
	server address = <server>

---------
MacOS 10.9.4, Calendar 7.0 (1841.1)
---------

* Calendar 
* Add Account 
* Add CalDAV account

then, if no SSL (in the case of the Local Development Server):

.. code-block:: bash
	account type = Advanced
	user name = test
	password = <anything>
	server address = <server>
	server path = / (this is needed, empty won't work)
	port = <leave empty, specified in server address)
	use SSL = <unchecked>
	use Kerberos = <unchecked>

or if SSL (in production):

.. code-block:: bash
	account type = Manual
	user name = test
	password = <anything>
	server address = <server>

(account type = "Automatic" does not seem to work)

---------
iOS 7.1.2, Contacts
---------

* Settings 
* Mail, Contacts, calendar
* Add Account
* Other
* CONTACTS / Add CardDAV Account

then:

.. code-block:: bash
	server = <server>
	user name = test
	password = <anything>
	description = <anything>

---------
iOS 7.1.2, Calendar
---------

* Settings 
* Mail, Contacts, calendar
* Add Account
* Other
* CALENDARS / Add CalDAV Account

then:

.. code-block:: bash
	server = <server>
	user name = test
	password = <anything>
	description = <anything>

=========
Server setup
=========

The first time you run the server, create empty collections by directing you browser to:

.. code-block:: bash
	/collections/create

-----------
Local development server
-----------

Install the Google AppEngine SDK for python (https://developers.google.com/appengine/downloads).

* GoogleAppEnginelauncher
* File
* Add Exiting Application

Then:

.. code-block:: bash
	path = <is the root of the project, where the app.yaml is>
	admin port = 8000 <or whatever you like>
	port = 8080 <or whatever you like>

You can then run the project using:

* Control
* Run

Your server is running at:

.. code-block:: bash
	http://localhost:8080

Notes:
* remember to create empty collections, see at top

-----------
Production
-----------

Create a Google AppEngine account.

Go to: https://appengine.google.com/

* Create Application

Then,

.. code-block:: bash
	Application identifier = radicale-gae <choose something else that's available, make sure it matches your application name in app.yaml>
	Application Title = Radicale AppEngine <does not matter>
	leave auth options as is

* Create Application

then use GoogleAppEnginelauncher (instructions above) to deploy:

* Control
* Deploy
 
Your server is running at:

.. code-block:: bash
	https://radicale-gae.appspot.com

Notes:
* remember to create empty collections, see at top
* http requests will be automatically redirected to https
