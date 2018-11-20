---
layout: page
title: Clients
permalink: /clients/
---

Radicale has been tested with:

  * [Android](https://android.com/) with
    [DAVdroid](https://davdroid.bitfire.at/)
  * [GNOME Calendar](https://wiki.gnome.org/Apps/Calendar),
    [Contacts](https://wiki.gnome.org/Apps/Contacts) and
    [Evolution](https://wiki.gnome.org/Apps/Evolution)
  * [Mozilla Thunderbird](https://www.mozilla.org/thunderbird/) with
    [CardBook](https://addons.mozilla.org/thunderbird/addon/cardbook/) and
    [Lightning](https://www.mozilla.org/projects/calendar/)
  * [InfCloud](https://www.inf-it.com/open-source/clients/infcloud/),
    [CalDavZAP](https://www.inf-it.com/open-source/clients/caldavzap/) and
    [CardDavMATE](https://www.inf-it.com/open-source/clients/carddavmate/)

Many clients do not support the creation of new calendars and address books.
You can use Radicale's web interface
(e.g. [http://localhost:5232](http://localhost:5232)) to create and manage
collections.

In some clients you can just enter the URL of the Radicale server
(e.g. `http://localhost:5232`) and your user name. In others, you have to
enter the URL of the collection directly
(e.g. `http://localhost:5232/user/calendar`).

## Auto Configuration

Some clients can "auto-configure" themselves, but it's not always supported by Radicale.  Here is what seems to work the best.

Setup a hostname just for radicale (say dav.example.com) and have radicale answer at the web root (so SCRIPT_NAME would be empty in your proxy config if using a proxy.)

setup cal and card dav DNS entries(in bind format):

```
_caldavs._tcp 86400 IN SRV 10 20 443 dav.example.com.
_carddavs._tcp 86400 IN SRV 10 20 443 dav.example.com.
```

Which is saying, for service caldavs (secure caldav) talk on port 443 to host dav.example.com.
and for carddavs (secure carddav) talk on port 443 to host dav.example.com 

understanding of these values can be had here: https://en.wikipedia.org/wiki/SRV_record

you have secure and insecure options for the service name, with the s at the end means secure mode (i.e. served over TLS/SSL, which you should always do!)

so your entire DNS setup for dav.example.com would be something like(in bind format):

```
_caldavs._tcp 86400 IN SRV 10 20 443 dav.example.com.
_carddavs._tcp 86400 IN SRV 10 20 443 dav.example.com.
dav 1800 IN A 10.1.1.1
dav 1800 IN AAAA fd2b:72bf:5153:06a4:b576:ca2d:3c87:f9a7
```

Also on your main www.example.com site, setup redirects for the well-known addresses ``` /.well-known/caldav/``` and ````.well-known/carddav ``` to your new dav.example.com host.

in nginx something like:
```
#http://www.example.com/.well-known/caldav -> root of your dav server
        location /.well-known/caldav/ {
                return         301 https://dav.example.com$request_uri;
        }
        #http://www.example.com/.well-known/carddav -> root of your dav server
        location /.well-known/carddav/ {
                return         301 https://dav.example.com$request_uri;
        }
```

So https://www.example.com/.well-known/caldav should redirect to: https://dav.example.com

This should make most clients auto-configure, if they have that option.

## DAVdroid

Enter the URL of the Radicale server (e.g. `http://localhost:5232`) and your
user name. DAVdroid will show all existing calendars and address books and you
can create new.

## GNOME Calendar, Contacts and Evolution

**GNOME Calendar** and **Contacts** do not support adding WebDAV calendars
and address books directly, but you can add them in **Evolution**.

In **Evolution** add a new calendar and address book respectively with WebDAV.
Enter the URL of the Radicale server (e.g. `http://localhost:5232`) and your
user name. Clicking on the search button will list the existing calendars and
address books.

## Thunderbird

### CardBook

Add a new address book on the network with CardDAV. You have to enter the full
URL of the collection (e.g. `http://localhost:5232/user/addressbook`) and
your user name.

### Lightning

Add a new calendar on the network with `CalDAV`. (Don't use `iCalendar (ICS)`!)
You have to enter the full URL of the collection (e.g.
`http://localhost:5232/user/calendar`). If you want to add calendars from
different users on the same server, you can specify the user name in the URL
(e.g. `http://user@localhost...`)

## InfCloud, CalDavZAP and CardDavMATE

You can integrate InfCloud into Radicale's web interface with
[RadicaleInfCloud](https://github.com/Unrud/RadicaleInfCloud). No additional
configuration is required.

Set the URL of the Radicale server in ``config.js``. If **InfCloud** is not
hosted on the same server and port as Radicale, the browser will deny access to
the Radicale server, because of the
[same-origin policy](https://en.wikipedia.org/wiki/Same-origin_policy).
You have to add additional HTTP header in the `headers` section of Radicale's
configuration. The documentation of **InfCloud** has more details on this.

## Manual creation of calendars and address books

This is not the recommended way of creating and managing your calendars and
address books. Use Radicale's web interface or a client with support for it
(e.g. **DAVdroid**).

### Direct editing of the storage

To create a new collection, you have to create the corresponding folder in the
file system storage (e.g. `collection-root/user/calendar`).
To tell Radicale and clients that the collection is a calendar, you have to
create the file ``.Radicale.props`` with the following content in the folder:

```json
{"tag": "VCALENDAR"}
```

The calendar is now available at the URL path ``/user/calendar``.
For address books the file must contain:

```json
{"tag": "VADDRESSBOOK"}
```

Calendar and address book collections must not have any child collections.
Clients with automatic discovery of collections will only show calendars and
addressbooks that are direct children of the path `/USERNAME/`.

Delete collections by deleting the corresponding folders.

### HTTP requests with curl

To create a new calendar run something like:

```shell
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

```shell
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

```shell
$ curl -u user -X DELETE 'http://localhost:5232/user/calendar'
```
