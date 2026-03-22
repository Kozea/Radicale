
# Collection Sharing

Static collection sharing without permissions filter using soft-links (Unix-only) is supported since storage type `multifilesystem` was implemented, see [Wiki: Sharing Collections](https://github.com/Kozea/Radicale/wiki/Sharing-Collections)

With _3.7.0_ major extension was implemented
 * added internal mapping with configuration stored in a database
 * added management API
 * WebUI extension using the management API

## Sharing Implementation

Implemenation of sharing collections is done by using a database to lookup the URI and in case entry exists by mapping to target URI and replacing provided data on request and adjust if required data in response.

Permissions are filtered by provided `Permissions`.

## Sharing Configuration

New section `[sharing]` controls sharing configuration, see [DOCUMENTATION:Sharing](DOCUMENTATION.md#sharing) for details

## Sharing Configuration Store

Types of supported sharing configuration:

 * *csv* (_>= 3.7.0_)
 * *files* (_>= 3.7.0_)

### Sharing Configuration Entry Data

 * `ShareType`: type of share
    * `token`: token-based share (do not require user authentication)
    * `map`: map-based share (requires user authentication)
    * `bday`: map-based share (requires user authentication) with on-the-fly auto-conversion
 * `PathOrToken`: token or "virtual" collection, has to be unique (PRIMARY KEY)
 * `PathMapped`: target collection
 * `Owner`: owner of the share
 * `User`: user of the share
 * `Permissions`: effective permission of the share (*bday* is always read-only)
 * `EnabledByOwner`: control by owner
 * `EnabledByUser`: control by user
 * `HiddenByOwner`: control by owner 
 * `HiddenByUser`: control by user
 * `TimestampCreated`: unixtime of creation
 * `TimestampUpdated`: unixtime of last update
 * `Properties`: overlay properties (limited set whitelisted)
 * `Conversion`: conversion method
 * `Actions`: (reserved for future usage)
 
`Enabled*`: owner AND user have to enable a share to become usable

`Hidden*`: owner AND user have to disable a share to become visible in PROPFIND

### Sharing Configuration Entry Storage

#### CSV

One CSV file containing one row per sharing config, separated by `;` and containing header with columns from above.

If given, properties are stored in JSON format in CSV.

#### Files

File-based configuration store is using encoded `PathOrToken` as filename for each config. File contains the data stored as "dict" in binary Python "pickle" format (same is also used for item cache files).

## Sharing Request Handling

### CxDAV requests

#### CxDav request "(DELETE|GET|HEAD|PUT)"

  * Actions
    * map
  * Lookup by
    * `path` (provided in request)
    * `user` (authenticated)
  * Replace
   * `path` by `PathMapped`
   * `user` by `Owner`
  * Activate
   * `permissions_filter` by `Permissions`

#### CxDav request "REPORT"

  * Actions
    * map
    * back-map response
  * Lookup by
    * `path` (provided in request)
    * `user` (authenticated)
  * Replace
   * `path` by `PathMapped`
   * `user` by `Owner`
  * Activate
   * `permissions_filter` by `Permissions`

#### CxDav request "PROPFIND" without HTTP_DEPTH=1

  * Actions
    * map
    * back-map response
    * overwrite `Properties` if provided
  * Lookup by
    * `path` (provided in request)
    * `user` (authenticated)
  * Replace
   * `path` by `PathMapped`
   * `user` by `Owner`
  * Overlay
   * `Properties` if provided
  * Activate
   * `permissions_filter` by `Permissions`

#### CxDav request "PROPFIND" with HTTP_DEPTH=1

  * Actions
    * extend list
  * Lookup for active shares for `user` in sharing database
  * Extend list if conditions are met
   * `permissions_filter` by `Permissions`

#### CxDav request "PROPPATCH"

  * Actions
    * map
    * adjust properties of a collection
  * Lookup by
    * `path` (provided in request)
    * `user` (authenticated)
  * Replace
   * `path` by `PathMapped`
   * `user` by `Owner`
  * Activate
   * `permissions_filter` by `Permissions`
  * Depending on `permissions_filter`, global options and `Permissions`
    * adjust properties of collection
    * adjust whitelisted properties in `Properties` for overlay (see OVERLAY_PROPERTIES_WHITELIST)

#### CxDav request "(MKCALENDAR|MKCOL)"

  * Action
    * check for conflicts
  * Lookup by
    * `user` (authenticated)
  * Verify for non-existence as `PathOrToken` in sharing database
    * `path` (provided in request)

#### CxDav request "(MOVE)"

  * Action
    * map source
    * map destination
  * Lookup by
    * `path` (provided in request)
    * `user` (authenticated)
    * `to_path` (provided in request)
    * `to_user` (same as `user`)
  * Replace
   * `path` by `PathMapped` (of path)
   * `user` by `Owner` (of `path`)
   * `to_path` by `PathMapped` (of `to_path`)
   * `to_user` by `Owner` (of `to_path`)
  * Activate
   * `permissions_filter` by `Permissions` (of `to_path`)
   * `to_permissions_filter` by `Permissions` (of `to_path`)

## Sharing Access

### Sharing Access via Maps

Map-based sharing can be accessed as usual after authentication and authorization.

 * *map* is a standard sharing of one collection to another user
 * *bday* is special sharing auto-mapping on-the-fly a VADDRESSBOOK to a VCALENDAR of all entries containing a `BDAY`

#### Permission Control

 * `permit_create_map`
   * supported *rights* permissions: `Mm`
 * `permit_create_bday`
   * supported *rights* permissions: `Bb`

#### Workflow

* create map as owner
* enable map as owner (can be combined with "create")
* enable map as user (explicit required to avoid sudden available share)

In case share should be visible using PROPFIND

* unhide map as owner (can be combined with "create")
* unhide map as user (explicit required to avoid sudden visible share)

### Sharing Access via Tokens

Token-based sharing can be accessed after retrieving the token via

Token-URI: `/.token/<Token>`

Note: requests to not enabled or not even defined tokens will resul tin _401 Not Authorized_

#### Permission Control

 * `permit_create_token`
   * supported *rights* permissions: `Tt`

#### Workflow

* create token as owner
* enable token as owner (can be combined with "create")
* handover URI with token to client

## Sharing Configuration Management API

### Sharing Configuration Management API version 1

Type: POST API

Base-URI: `/.sharing/v1/<ShareType>/<Hook>`

See also test cases in `radicale/tests/test_sharing.py`

#### Data Format

##### Input Data Format

Parsing be controlled by `CONTENT_TYPE`

 * application/x-www-form-urlencoded
 * application/json
 
##### Output Data Format

Can be selected by `HTTP_ACCEPT` - default is equal to provided `CONTENT_TYPE`

 * text/plain
 * text/csv (only for "list")
 * application/json
 
##### Accepted Input Data Fields

 * `PathOrToken`: token or "virtual" collection
 * `PathMapped`: target collection
 * `Owner`: owner of the share
 * `User`: user of the share
 * `Permissions`: effective permission of the share
 * `Enabled`: owner/user selected by authentication
 * `Hidden`: owner/user selected by authentication
 * `Properties`: properties to overlay
 
#### API Hooks

##### API Hook "info"

Shows what kind of ShareTypes are supported

 * Output: text/plain|application/json

 * Examples

  * form->text

```bash
curl -u user:$userpw -H "accept: text/plain" -d "" http://localhost:5232/.sharing/v1/all/info
ApiVersion=1
Status='success'
FeatureEnabledCollectionByMap=True
PermittedCreateCollectionByMap=True
FeatureEnabledCollectionByToken=True
PermittedCreateCollectionByToken=True  
```

  * json->json, parsed with `jq`

```
bash
curl -u user:$userpw --silent -H "accept: application/json" -d "" http://localhost:5232/.sharing/v1/all/info | jq
{
  "ApiVersion": 1,
  "Status": "success",
  "FeatureEnabledCollectionByMap": true,
  "PermittedCreateCollectionByMap": true,
  "FeatureEnabledCollectionByToken": true,
  "PermittedCreateCollectionByToken": true,
  "FeatureEnabledCollectionByBday": true,
  "PermittedCreateCollectionByBday": true
}
```

##### API Hook "(token|map|bday)/create"

 * Authorization
   * Authenticated user is `Owner`

###### API Hook "token/create"

Create a share by mapping a collection of an `Owner` to a token.

 * Authorization
  * `PathMapped` is existing and a collection
  * Authenticated user as `Owner` has at least read access to `PathMapped`
  * Global permitted by `permit_create_token = True` or `rights` permission `t`
  * Global denied by `permit_create_token = False` or `rights` permission `T`

 * Input

| Parameter | Type | Requirement |
| - | - | - |
| PathMapped | str | mandatory |
| User | str | optional(default:owner) |
| Permissions | str | optional(default:r) |
| Enabled | bool | optional(owner/default:False) |
| Hidden | bool | optional(owner/default:True) |
| Properties | str | optional |

 * Output: text/plain|application/json

| Parameter | Type | Value |
| - | - |
| PathOrToken | str | (autogenerated token) |

 * Examples:
  * form->text

```bash
curl -u user:$userpw -d "PathMapped=/user/testcalendar1/" -d "Enabled=True" -d "Hidden=False" http://localhost:5232/.sharing/v1/token/create
ApiVersion=1
Status='success'
PathOrToken='/.token/v1/VQR7AmsVRi2ZlFj_JwGpFx-ES5Goyku-gP_YkLh1zUw0/'
```

  * json->json

```bash
curl -u user:$userpw -H "Content-Type: application/json" -d '{ "PathMapped": "/user/testcalendar1/", "Enabled": true, "Hidden": false}' http://localhost:5232/.sharing/v1/token/create
{"ApiVersion": 1, "Status": "success", "PathOrToken": "/.token/v1/aMsmGqOsRwSH-2-6tEa8EMr4RMYzMU7WvPmjnp5qDnw0/"}
```

###### API Hook "(map|bday)/create"

Create a share by mapping a collection of an `Owner` to an `User`.

 * Authorization
  * `PathMapped` is existing and a collection
  * `PathMapped` is not existing already as a share target for same `User`
  * Authenticated user as `Owner` has at least read access to `PathMapped`
  * Provided `User` has at least read access to `PathOrToken`
  * *map*
      * Global permitted by `permit_create_map = True` or `rights` permission `m`
      * Global denied by `permit_create_map = False` or `rights` permission `M`
  * *bday*
      * Global permitted by `permit_create_map = True` or `rights` permission `b`
      * Global denied by `permit_create_map = False` or `rights` permission `B`
      * `PathMapped` is a VCALENDAR collection

 * Input

| Parameter | Type | Requirement |
| - | - |
| PathOrToken | str | mandatory |
| PathMapped | str | mandatory |
| User | str | mandatory |
| Permissions | str | optional(default:r) |
| Enabled | bool | optional(owner/default:False) |
| Hidden | bool | optional(owner/default:True) |
| Properties | optional |

 * Output: text/plain|application/json

 * Examples:
  * form->text

```bash
curl -u owner:$ownerpw -d "PathOrToken=/user/cal1-from-owner/" -d "PathMapped=/owner/testcalendar1/" -d "User=user" -d "Enabled=True" -d "Hidden=False" http://localhost:5232/.sharing/v1/map/create
ApiVersion=1
Status='success'
```

  * json->json

```bash
curl -u owner:$ownerpw -H "Content-Type: application/json" -d '{ "PathOrToken": "/user/cal1-from-owner/", "PathMapped": "/owner/testcalendar1/", "User" : "user", "Enabled": true, "Hidden": false}' http://localhost:5232/.sharing/v1/map/create
{"ApiVersion": 1, "Status": "success"}
```

##### API Hook "(all|token|map|bday)/list"

List shares (optional with filter) either owned or assigned as user.

 * Authorization
  * Authenticated user as `Owner` or `User`

 * Input

| Parameter | Type | Used for |
| - | - | - |
| PathOrToken | str | optional |
| PathMapped | str | optional |

 * Output: text/plain|text/csv|application/json

 * Examples

  * form->text ("all")

```bash
curl -u user:$userpw -d "" http://localhost:5232/.sharing/v1/map/list://localhost:5232/.sharing/v1/map/list
ApiVersion=1
Lines=1
Status='success'
Fields="ShareType;PathOrToken;PathMapped;Owner;User;Permissions;EnabledByOwner;EnabledByUser;HiddenByOwner;HiddenByUser;TimestampCreated;TimestampUpdated;Properties"
Content[0]="map;/user/cal1-from-owner/;/owner/testcalendar1/;owner;user;r;True;True;False;False;1772748001;1772748163;
```

  * form->csv ("map" only)
 
```bash
curl -H "accept: text/csv" -u user:$userpw -d "" http://localhost:5232/.sharing/v1/map/list://localhost:5232/.sharing/v1/map/list
ShareType;PathOrToken;PathMapped;Owner;User;Permissions;EnabledByOwner;EnabledByUser;HiddenByOwner;HiddenByUser;TimestampCreated;TimestampUpdated;Properties
map;/user/cal1-from-owner/;/owner/testcalendar1/;owner;user;r;True;False;False;True;1772747277;1772747277;
```

  * json->json ("all"), parsed with `jq`

```bash
curl -s -H "Content-Type: application/json" -u user:$userpw -d "{}" http://localhost:5232/.sharing/v1/all/list | jq
{
  "ApiVersion": 1,
  "Lines": 2,
  "Status": "success",
  "Content": [
    {
      "ShareType": "map",
      "PathOrToken": "/user/cal1-from-owner/",
      "PathMapped": "/owner/testcalendar1/",
      "Owner": "owner",
      "User": "user",
      "Permissions": "r",
      "EnabledByOwner": true,
      "EnabledByUser": false,
      "HiddenByOwner": false,
      "HiddenByUser": true,
      "TimestampCreated": 1772747277,
      "TimestampUpdated": 1772747277,
      "Properties": ""
    },
    {
      "ShareType": "token",
      "PathOrToken": "v1/DUSl_J5rRlWx3fy8YRXpH22FFllplkOTpcSwfGtpvkc=",
      "PathMapped": "/user/testcalendar1/",
      "Owner": "user",
      "User": "user",
      "Permissions": "r",
      "EnabledByOwner": true,
      "EnabledByUser": false,
      "HiddenByOwner": false,
      "HiddenByUser": true,
      "TimestampCreated": 1772747371,
      "TimestampUpdated": 1772747371,
      "Properties": ""
    }
  7]
}
```


##### API Hook "(token|map|bday)/delete"

Delete a share selected by `PathOrToken`.

 * Authorization
  * Authenticated user is `Owner`
  * Share is existing and owned

 * Input

| Parameter | Type | Used for | as Owner | as User |
| - | - | - | - | - |
| PathOrToken | str | selection | mandatory | not-permitted |

 * Output: text/plain|application/json

 * Examples:

  * form->text

```bash
curl -u owner:$ownerpw -d "PathOrToken=/user/cal1-from-owner/" http://localhost:5232/.sharing/v1/map/delete
ApiVersion=1
Status='success'
```

  * json->json

```bash
curl -u user:$userpw -H "Content-Type: application/json" -d '{ "PathOrToken": "v1/DUSl_J5rRlWx3fy8YRXpH22FFllplkOTpcSwfGtpvkc="}' http://localhost:5232/.sharing/v1/token/delete
{"ApiVersion": 1, "Status": "success"}
```

##### API Hook "(token|map|bday)/update"

Update a share selected by `PathOrToken`.

Execute delete+create in case `PathOrToken` needs to be changed.

 * Authorization
   * Authenticated user is `Owner` or `User`

 * Input

| Parameter | Type | Used for | Owner | User |
| - | - | - | - | - |
| PathOrToken | str | selection | mandatory | mandatory |
| PathMapped | str | adjust | optional | not-permitted |
| User | str | adjust | optional | not-permitted |
| Permissions | str | adjust | optional | not-permitted |
| Enabled | bool | adjust | optional(owner) | optional(user) |
| Hidden | bool | adjust | optional(owner) | optional(user) |
| Properties | str | adjust | optional | optional |

 * Output: text/plain|application/json

 * Examples:

   * form->text

```bash
curl -u user:$userpw -d "PathOrToken=/user/cal1-from-owner/" -d "Enabled=True" -d "Hidden=False" http://localhost:5232/.sharing/v1/map/update
ApiVersion=1
Status='success'
```

  * json->json

```bash
curl -u user:$userpw -H "Content-Type: application/json" -d '{ "PathOrToken": "/user/cal1-from-owner/", "Enabled": true, "Hidden": false}' http://localhost:5232/.sharing/v1/map/update
{"ApiVersion": 1, "Status": "success"}
```

##### API Hooks "(token|map|bday)/(enable|disable|hide|unhide)"

Toggle enable|disable|hide|unhide of `Owner` or `User` of a share selected by `PathOrToken`

 * Authorization
   * Authenticated user is `Owner` or `User`
   * `PathOrToken` is existing and either owned or assigned to user

 * Input

| Parameter | Type | Used for | Owner | User |
| - | - | - | - | - |
| PathOrToken | selection | mandatory | mandatory |

 * Output: text/plain|application/json
  
  * form->text

```bash
curl -u user:$userpw -d "PathOrToken=/user/cal1-from-owner/" http://localhost:5232/.sharing/v1/map/enable
ApiVersion=1
Status='success'
```bash

  * json->json

```bash
curl -u user:$userpw -H "Content-Type: application/json" -d '{ "PathOrToken": "/user/cal1-from-owner/"}' http://localhost:5232/.sharing/v1/map/unhide
{"ApiVersion": 1, "Status": "success"}
```

## Properties Overlay

Owner or user can define per share a set of properties to overlay on PROPFIND response during create or update via API.

Whitelisted ones are defined in `OVERLAY_PROPERTIES_WHITELIST` in `radicale/sharing/__init__.py`:

 * `C:calendar-description`
 * `ICAL:calendar-color`
 * `CR:addressbook-description`
 * `INF:addressbook-color`
 * `D:displayname`

### Properties Overlay Control Options

 * `permit_properties_overlay`
   * supported *share* permissions: `Pp`
 * `enforce_properties_overlay`
   * supported *share* permissions: `Ee`

### Properties Overlay Example

#### Requirements

  * `permit_properties_overlay = True`

#### Test sequence

  * Prepare XML statements

```bash
## PROPFIND color
xml_pfc='<?xml version="1.0"?>
<propfind xmlns="DAV:" xmlns:ICAL="http://apple.com/ns/ical/">
  <prop>
    <ICAL:calendar-color />
  </prop>
</propfind>'

## PROPPATCH color
xml_ppc='<?xml version="1.0"?>
<D:propertyupdate xmlns:D="DAV:">
  <D:set>
    <D:prop>
      <I:calendar-color xmlns:I="http://apple.com/ns/ical/">#DDDDDD</I:calendar-color>
    </D:prop>
  </D:set>
</D:propertyupdate>'
```

  * Tests

```bash
## Retrieve collection color of owner (no color set)
curl -u owner:$ownerpw -d "$xml_pfc" -X PROPFIND http://localhost:5232/owner/testcalendar1/

## Create read-only share for user
curl -u owner:$ownerpw -d "PathOrToken=/user/cal1-from-owner/" -d "PathMapped=/owner/testcalendar1/" -d "User=user" -d "Enabled=True" -d "Hidden=False" http://localhost:5232/.sharing/v1/map/create

## Accept (enable+unhide) share by user
curl -u user:$userpw -d "PathOrToken=/user/cal1-from-owner/" -d "Enabled=True" -d "Hidden=False" http://localhost:5232/.sharing/v1/map/update

## Retrieve collection color of share by user (no color set)
curl -u user:$userpw -d "$xml_pfc" -X PROPFIND http://localhost:5232/user/cal1-from-owner/

## Set property overlay by user
curl -u user:$userpw -d "PathOrToken=/user/cal1-from-owner/" -d 'Properties="ICAL:calendar-color"="#CCCCCC"' http://localhost:5232/.sharing/v1/map/update

## Retrieve collection color of share by user (color set)
curl -u user:$userpw -d "$xml_pfc" -X PROPFIND http://localhost:5232/user/cal1-from-owner/

## Delete property overlay by user
curl -u user:$userpw -d "PathOrToken=/user/cal1-from-owner/" -d 'Properties=' http://localhost:5232/.sharing/v1/map/update

## Retrieve collection color of share by user (no color set)
url -u user:$userpw -d "$xml_pfc" -X PROPFIND http://localhost:5232/user/cal1-from-owner/

## Add property overlay by user using PROPPATCH
curl -u user:$userpw -d "$xml_ppc" -X PROPPATCH http://localhost:5232/user/cal1-from-owner/

## Retrieve collection color of share by user (color set)
curl -u user:$userpw -d "$xml_pfc" -X PROPFIND http://localhost:5232/user/cal1-from-owner/
```

## Virtual "bday" collection

Owner can create for itself or for particular user a virtual bday collection from an existing addressbook.


### Examples

Preconditions:

 * Collection with type *adressbook* is existing
 * Config options enabled in section `sharing`:
   * `collection_by_bday`
   * `permit_create_bday`

#### Examples using API

  * Create

```bash
## Create sharing of type "bday"
curl -u owner:$ownerpw -d "PathOrToken=/owner/bday-of-addressbook/" -d "PathMapped=/owner/addressbook/" -d "User=owner" http://localhost:5232/.sharing/v1/bday/create


## Enable
curl -u owner:$ownerpw -d "PathOrToken=/owner/bday-of-addressbook/" http://localhost:5232/.sharing/v1/bday/enable

## Unhide
curl -u owner:$ownerpw -d "PathOrToken=/owner/bday-of-addressbook/" http://localhost:5232/.sharing/v1/bday/unhide
```

  * Check

Use e.g. WebUI, an additional (virtual) calendar collection appears
