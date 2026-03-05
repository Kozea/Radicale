
# Collection Sharing

Static collection sharing without permissions filter using soft-links (Unix-only) is supported since storage type `multifilesystem` was implemented, see (Wiki: Sharing Collections)[https://github.com/Kozea/Radicale/wiki/Sharing-Collections]

With 3.7.0 a major extension was implemented using internal mapping configuration stored in a database and a management API.

## Sharing Configuration Store

Types of supported sharing configuration:

 * csv (_>= 3.7.0_)
 * files (_>= 3.7.0_)

### Sharing Configuration Entry Data

 * `ShareType`: type of share
    * `token`: token-based share (do not require user authentication)
    * `map`: map-based share (requires user authentication)
 * `PathOrToken`: token or "virtual" collection, has to be unique (PRIMARY KEY)
 * `PathMapped`: target collection
 * `Owner`: owner of the share
 * `User`: user of the share
 * `Permissions`: effective permission of the share
 * `EnabledByOwner`: control by owner
 * `EnabledByUser`: control by user
 * `HiddenByOwner`: control by owner 
 * `HiddenByUser`: control by user
 * `TimestampCreated`: unixtime of creation
 * `TimestampUpdated`: unixtime of last update
 * `Properties`: overlay properties (limited set whitelisted)
 
`Enabled*`: owner AND user have to enable a share to become usable

`Hidden*`: owner AND user have to disable a share to become visible in PROPFIND

### Sharing Configuration Entry Storage

#### CSV

(_>= 3.7.0_)

One CSV file containing one row per sharing config, separated by `;` and containing header with columns from above.

If given, properties are stored in JSON format in CSV.

#### Files

(_>= 3.7.0_)

File-based configuration store is using encoded `PathOrToken` as filename for each config. File contains the data stored as "dict" in binary Python "pickle" format (same is also used for item cache files).

## Sharing Access

### Sharing Access via Maps

(_>= 3.7.0_)

Map-based sharing can be accessed as usual after authentication and authorization.

#### Permission Control

 * `permit_create_map`
   * supported *rights* permissions: `Mm`

#### Workflow

* create map as owner
* enable map as owner (can be combined with "create")
* enable map as user (explicit required to avoid sudden available share)

In case share should be visible using PROPFIND

* unhide map as owner (can be combined with "create")
* unhide map as user (explicit required to avoid sudden visible share)


### Sharing Access via Tokens

(_>= 3.7.0_)

Token-based sharing can be accessed after retrieving the token via

Token-URI: `/.token/<Token>`

#### Permission Control

 * `permit_create_token`
   * supported *rights* permissions: `Tt`

#### Workflow

* create token as owner
* enable token as owner (can be combined with "create")
* handover URI with token to client

## Sharing Configuration Management API

### Sharing Configuration Management API version 1

(_>= 3.7.0_)

Type: POST API

Base-URI: `/.sharing/v1/<ShareType>/<Hook>`

See also test cases in `radicale/tests/test_sharing.py`

#### Data Format

##### Input Data Format

Parsing be controlled by `CONTENT_TYPE`

 * application/x-www-form-urlencoded (_>= 3.7.0_)
 * application/json (_>= 3.7.0_)
 
##### Output Data Format

Can be selected by `HTTP_ACCEPT`

 * text/plain (_>= 3.7.0_)
 * text/csv (_>= 3.7.0_) - only for "list"
 * application/json (_>= 3.7.0_)
 
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

* Example: TEXT

```
curl -u user:pass -H "accept: text/plain" -d "" http://localhost:5232/.sharing/v1/all/info
ApiVersion=1
Status='success'
FeatureEnabledCollectionByMap=True
PermittedCreateCollectionByMap=True
FeatureEnabledCollectionByToken=True
PermittedCreateCollectionByToken=True  
```

* Example: JSON

```
curl -u user:pass --silent -H "accept: application/json" -d "" http://localhost:5232/.sharing/v1/all/info | jq
{
  "ApiVersion": 1,
  "Status": "success",
  "FeatureEnabledCollectionByMap": true,
  "PermittedCreateCollectionByMap": true,
  "FeatureEnabledCollectionByToken": true,
  "PermittedCreateCollectionByToken": true
}
```


##### API Hook "(token|map)/create"

 * Authorization

Authenticated user is `Owner`

###### API Hook "token/create"

Create a share by mapping a collection of an `Owner` to a token.

 * Authorization

Authenticated user as `Owner` has at least read access to `PathMapped`

 * Input

| Parameter | Type | Requirement |
| - | - | - |
| PathMapped | str | mandatory |
| User | str | optional(default:owner) |
| Permissions | str | optional(default:r) |
| Enabled | bool | optional(owner/default:False) |
| Hidden | bool | optional(owner/default:True) |
| Properties | str | optional |

  * Output

| Parameter | Type | Value |
| - | - |
| PathOrToken | str | (autogenerated token) |

* Example: TEXT

```
curl -u user:pass -d "PathMapped=/user/testcalendar1/" http://localhost:5232/.sharing/v1/token/create
ApiVersion=1
Status='success'
PathOrToken='v1/VQR7AmsVRi2ZlFj_JwGpFx-ES5Goyku-gP_YkLh1zUw='
```

###### API Hook "map/create"

Create a share by mapping a collection of an `Owner` to an `User`.

 * Authorization

Authenticated user as `Owner` has at least read access to `PathMapped`

Provided `User` has at least read access to `PathOrToken`

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

 * Output: result status

 * Example: TEXT

```
curl -u owner:pass -d "PathOrToken=/user/cal1-from-owner/" -d "PathMapped=/owner/cal1/" -d "User=user" http://localhost:5232/.sharing/v1/map/create
ApiVersion=1
Status=success
```


##### API Hook "(map|token|all)/list"

List shares (optional with filter) either owned or assigned as user.

 * Authorization

Authenticated user as `Owner` or `User`

 * Input

| Parameter | Type | Used for |
| - | - | - |
| PathOrToken | str | optional |
| PathMapped | str | optional |

 * Output: plain/csv/json

 * Example: CSV
 
```
curl -H "accept: text/csv" -u owner:pass -d "" http://localhost:5232/.sharing/v1/map/list
ShareType,PathOrToken,PathMapped,Owner,User,Permissions,EnabledByOwner,EnabledByUser,HiddenByOwner,HiddenByUser,TimestampCreated,TimestampUpdated,Properties
map,/user/cal1-from-owner/,/owner/cal1/,owner,user,r,False,False,True,True,1771962120,1771962120,{}
```


##### API Hook "(map|token)/delete"

Delete a share selected by `PathOrToken`.

 * Authorization

Authenticated user is `Owner`

 * Input

| Parameter | Type | Used for | as Owner | as User |
| - | - | - | - | - |
| PathOrToken | str | selection | mandatory | not-permitted |

  * Output: result status

##### API Hook "(token|map)/update"

Update a share selected by `PathOrToken`.

Execute delete+create in case `PathOrToken` needs to be changed.

 * Authorization

Authenticated user is `Owner` or `User`

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

  * Output: result status

##### API Hooks "(map|token)/(enable|disable|hide|unhide)"

Toggle enable|disable|hide|unhide of `Owner` or `User` of a share selected by `PathOrToken`

 * Authorization

Authenticated user is `Owner` or `User`

 * Input

| Parameter | Type | Used for | Owner | User |
| - | - | - | - | - |
| PathOrToken | selection | mandatory | mandatory |

 * Output: result status
  
 * Example: TEXT (enable)
 
```
curl -u owner:pass -d "PathOrToken=/user/cal1-from-owner/" -d "PathMapped=/owner/cal1/" -d "User=user" http://localhost:5232/.sharing/v1/map/enable
ApiVersion=1
Status=success
```

 * Example: JSON (unhide)
 
```
curl -u owner:pass -d '{"PathOrToken": "/user/cal1-from-owner/", "PathMapped": "/owner/cal1/", "User": "user"} http://localhost:5232/.sharing/v1/map/unhide
ApiVersion=1
Status='success'
```

## Properties Overlay

Owner or user can define per share a set of properties to overlay on PROPFIND response during create or update via API.

Whitelisted ones are defined in `OVERLAY_PROPERTIES_WHITELIST` in `radicale/sharing/__init__.py`:

 * `C:calendar-description` (_>= 3.7.0_)
 * `ICAL:calendar-color` (_>= 3.7.0_)
 * `CR:addressbook-description` (_>= 3.7.0_)
 * `INF:addressbook-color` (_>= 3.7.0_)

### Properties Overlay Control Options

 * `permit_properties_overlay`
   * supported *share* permissions: `Pp`
 * `enforce_properties_overlay`
   * supported *share* permissions: `Ee`
