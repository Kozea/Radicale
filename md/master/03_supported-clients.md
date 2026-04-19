## Supported Clients

Radicale has been tested with:

* [Android](https://android.com/) with
  [DAVx⁵](https://www.davx5.com/) (formerly DAVdroid),
* [OneCalendar](https://www.onecalendar.nl/)
* [GNOME Calendar](https://wiki.gnome.org/Apps/Calendar),
  [Contacts](https://wiki.gnome.org/Apps/Contacts) and
  [Evolution](https://wiki.gnome.org/Apps/Evolution)
* [KDE PIM Applications](https://kontact.kde.org/),
  [KDE Merkuro](https://apps.kde.org/de/merkuro/)
* [Mozilla Thunderbird](https://www.mozilla.org/thunderbird/) ([Thunderbird/Radicale](https://github.com/Kozea/Radicale/wiki/Client-Thunderbird)) with
  [CardBook](https://addons.mozilla.org/thunderbird/addon/cardbook/) and
  [Lightning](https://www.mozilla.org/projects/calendar/)
* [InfCloud](https://www.inf-it.com/open-source/clients/infcloud/) ([InfCloud/Radicale](https://github.com/Kozea/Radicale/wiki/Client-InfCloud)),
  [CalDavZAP](https://www.inf-it.com/open-source/clients/caldavzap/),
  [CardDavMATE](https://www.inf-it.com/open-source/clients/carddavmate/) and
  [Open Calendar](https://github.com/algoo/open-calendar/)
* [pimsync](https://pimsync.whynothugo.nl/) ([pimsync/Radicale](https://github.com/Kozea/Radicale/wiki/Client-pimsync))

Many clients do not support the creation of new calendars and address books.
You can use Radicale's web interface
(e.g. <http://localhost:5232>) to create and manage address books and calendars.

In some clients, it is sufficient to simply enter the URL of the Radicale server
(e.g. `http://localhost:5232`) and your username. In others, you have to
enter the URL of the collection directly (e.g. `http://localhost:5232/user/calendar`).

Some clients (notably macOS's Calendar.app) may silently refuse to include
account credentials over unsecured HTTP, leading to unexpected authentication
failures. In these cases, you want to make sure the Radicale server is
[accessible over HTTPS](#ssl).

#### DAVx⁵

Enter the URL of the Radicale server (e.g. `http://localhost:5232`) and your
username. DAVx⁵ will show all existing calendars and address books and you
can create new ones.

#### OneCalendar

When adding account, select CalDAV account type, then enter username, password and the
Radicale server (e.g. `https://yourdomain:5232`). OneCalendar will show all
existing calendars and (FIXME: address books), you need to select which ones
you want to see. OneCalendar supports many other server types too.

#### GNOME Calendar, Contacts

GNOME 46 added CalDAV and CardDAV support to _GNOME Online Accounts_.

Open GNOME Settings, navigate to _Online Accounts_ > _Connect an Account_ > _Calendar, Contacts and Files_.
Enter the URL (e.g. `https://example.com/radicale`) and your credentials then click _Sign In_.
In the pop-up dialog, turn off _Files_. After adding Radicale in _GNOME Online Accounts_,
it should be available in GNOME Contacts and GNOME Calendar.

#### Evolution

In **Evolution** add a new calendar and address book respectively with WebDAV.
Enter the URL of the Radicale server (e.g. `http://localhost:5232`) and your
username. Clicking on the search button will list the existing calendars and
address books.

Adding CalDAV and CardDAV accounts in Evolution will automatically make them
available in GNOME Contacts and GNOME Calendar.

#### KDE PIM Applications

In **Kontact** add a _DAV Groupware resource_ to Akonadi under
_Settings > Configure Kontact > Calendar > General > Calendars_,
select the protocol (CalDAV or CardDAV), add the URL to the Radicale collections
and enter the credentials. After synchronization of the calendar resp.
addressbook items, you can manage them in Kontact.

#### Thunderbird

Add a new calendar on the network. Enter your username and the URL of the
Radicale server (e.g. `http://localhost:5232`). After asking for your password,
it will list the existing calendars.

##### Address books with CardBook add-on

Add a new address book on the network with CardDAV. Enter the URL of the
Radicale server (e.g. `http://localhost:5232`) and your username and password.
It will list your existing address books.

#### InfCloud, CalDavZAP and CardDavMATE

You can integrate InfCloud into Radicale's web interface with by simply
downloading the latest package from [InfCloud](https://www.inf-it.com/open-source/clients/infcloud/)
and extract the content into a folder named `infcloud` in `radicale/web/internal_data/`.

No further adjustments are required as content is adjusted on the fly (tested with 0.13.1).

See also [Wiki/Client InfCloud](https://github.com/Kozea/Radicale/wiki/Client-InfCloud).

#### Command line

This is not the recommended way of creating and managing your calendars and
address books. Use Radicale's web interface or a client with support for it
(e.g. **DAVx⁵**).

To create a new calendar run something like:

```bash
$ curl -u user -X MKCOL 'http://localhost:5232/user/calendar' --data \
'<?xml version="1.0" encoding="UTF-8" ?>
<create xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:I="http://apple.com/ns/ical/">
  <set>
    <prop>
      <resourcetype>
        <collection />
        <C:calendar />
      </resourcetype>
      <C:supported-calendar-component-set>
        <C:comp name="VEVENT" />
        <C:comp name="VJOURNAL" />
        <C:comp name="VTODO" />
      </C:supported-calendar-component-set>
      <displayname>Calendar</displayname>
      <C:calendar-description>Example calendar</C:calendar-description>
      <I:calendar-color>#ff0000ff</I:calendar-color>
    </prop>
  </set>
</create>'
```

To create a new address book run something like:

```bash
$ curl -u user -X MKCOL 'http://localhost:5232/user/addressbook' --data \
'<?xml version="1.0" encoding="UTF-8" ?>
<create xmlns="DAV:" xmlns:CR="urn:ietf:params:xml:ns:carddav">
  <set>
    <prop>
      <resourcetype>
        <collection />
        <CR:addressbook />
      </resourcetype>
      <displayname>Address book</displayname>
      <CR:addressbook-description>Example address book</CR:addressbook-description>
    </prop>
  </set>
</create>'
```

The collection `/USERNAME` will be created automatically, when the user
authenticates to Radicale for the first time. Clients with automatic discovery
of collections will only show calendars and address books that are direct
children of the path `/USERNAME/`.

Delete the collections by running something like:

```bash
curl -u user -X DELETE 'http://localhost:5232/user/calendar'
```

Note: requires config/option `permit_delete_collection = True`
