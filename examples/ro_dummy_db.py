from contextlib import contextmanager
from datetime import datetime

import vobject

from radicale.app import Application
from radicale.item import Item
from radicale.storage import BaseCollection as _BaseCollection
from radicale.storage import BaseStorage


def _find(lst, key, value):
    for item in lst:
        if item[key] == value:
            return item
    return None


def noop(*a, **kw):
    """Do nothing.

    Some CalDAV clients do not respect principal privileges, just ignore them.
    """


class Auth:
    def __init__(self, db):
        self.db = db

    def get_external_login(self, environ):
        return ()

    def login(self, login, password):
        user = _find(self.db["users"], "username", login)

        if user is not None and user["password"] == password:
            return login

        return ""


class Rights:
    def authorization(self, user, path):
        if user:
            return "Rr"
        return ""


class Web:
    def get(self, environ, base_prefix, path, user):
        return 200, {"Content-Type": "text/plain"}, "OK"


class Storage(BaseStorage):
    move = noop

    def __init__(self, db):
        self.db = db

    @contextmanager
    def acquire_lock(self, mode, user=None):
        yield

    def resolve(self, path):
        path = path.strip("/").split("/")

        if path == [""]:
            return RootCollection(self.db)
        elif len(path) == 1:
            user = _find(self.db["users"], "username", path[0])

            if user:
                return PrincipalCollection(self.db, user)
        elif len(path) == 2:
            username = path[0]
            user = _find(self.db["users"], "username", username)
            calendar = _find(self.db["calendars"], "id", path[1])

            if user and calendar and calendar["owner"] == username:
                return CalendarCollection(self.db, user, calendar)

        return None

    def discover(self, path, depth="0"):
        collection = self.resolve(path)

        if collection is None:
            return

        yield collection

        if depth == "0":
            return

        yield from collection.discover()


class BaseCollection(_BaseCollection):
    create_collection = noop
    upload = noop
    delete = noop
    set_meta = noop
    set_meta_all = noop

    def __init__(self, db):
        self.db = db

    @property
    def is_principal(self):
        return False

    @property
    def last_modified_dt(self):
        return datetime(1970, 1, 1)

    @property
    def last_modified(self):
        return self.last_modified_dt.strftime(r"%a, %d %b %Y %H:%M:%S GMT")

    @property
    def etag(self):
        return '"%s"' % self.last_modified_dt.timestamp()

    def get_meta(self, key=None):
        if key is None:
            return self.meta
        return self.meta.get(key)

    def get_all(self):
        return self.discover()


class RootCollection(BaseCollection):
    def __init__(self, db):
        super().__init__(db)

        self.meta = {
            "D:displayname": "Test",
        }

    @property
    def owner(self):
        return ""

    @property
    def path(self):
        return ""

    def discover(self):
        for user in self.db["users"]:
            yield PrincipalCollection(self.db, user)


class PrincipalCollection(BaseCollection):
    def __init__(self, db, user):
        super().__init__(db)

        self.user = user
        self.meta = {
            "D:displayname": user["name"],
        }

    @property
    def is_principal(self):
        return True

    @property
    def owner(self):
        return self.user["username"]

    @property
    def path(self):
        return self.user["username"]

    def discover(self):
        user = self.user
        username = user["username"]

        for calendar in self.db["calendars"]:
            if calendar["owner"] == username:
                yield CalendarCollection(self.db, user, calendar)


class CalendarCollection(BaseCollection):
    def __init__(self, db, user, calendar):
        super().__init__(db)

        self.user = user
        self.calendar = calendar
        self.meta = {
            "tag": "VCALENDAR",
            "C:supported-calendar-component-set": "VEVENT",
            "D:displayname": calendar["name"],
            "ICAL:calendar-color": calendar["color"],
            "ICAL:calendar-order": str(calendar["order"]),
        }

    @property
    def owner(self):
        return self.user["username"]

    @property
    def path(self):
        return "%s/%s" % (self.user["username"], self.calendar["id"])

    def discover(self):
        users = self.db["users"]
        calendar_id = self.calendar["id"]

        for event in self.db["events"]:
            if event["calendar"] != calendar_id:
                continue

            updated = event["last_modified"]
            organizer = _find(users, "username", event["organizer"])
            attendees = [
                _find(users, "username", username)
                for username in event["attendees"]
            ]

            yield Item(
                collection=self,
                href="%s.ics" % event["id"],
                last_modified=updated.strftime(r"%a, %d %b %Y %H:%M:%S GMT"),
                vobject_item=as_vevent(
                    self.calendar,
                    event,
                    organizer,
                    attendees,
                ),
                etag='"%s"' % updated.timestamp(),
            )


def as_vevent(calendar, event, organizer, attendees):
    vcalendar = vobject.newFromBehavior("vcalendar")
    vevent = vcalendar.add("vevent")

    vcalendar.add("x-wr-calname").value = calendar["name"]
    vevent.add("uid").value = "event%s@example.com" % event["id"]
    vevent.add("summary").value = event["summary"]
    vevent.add("description").value = event["description"]
    vevent.add("status").value = event["status"]
    vevent.add("created").value = event["created"]
    vevent.add("last-modified").value = event["last_modified"]
    vevent.add("dtstart").value = event["start"]
    vevent.add("dtend").value = event["end"]

    vorganizer = vevent.add("organizer")
    vorganizer.value = 'mailto:' + organizer["email"]
    vorganizer.params["CN"] = organizer["name"]

    for user in attendees:
        attendee = vevent.add("attendee")
        attendee.value = 'mailto:' + user["email"]
        attendee.params["ROLE"] = 'REQ-PARTICIPANT'
        attendee.params["CN"] = user["name"]
        attendee.params["STATUS"] = 'ACCEPTED'

    return vcalendar


DB = {
    "users": [
        {
            "name": "Admin",
            "username": "admin",
            "password": "hackme",
            "email": "admin@example.com",
        },
        {
            "name": "Test User",
            "username": "test",
            "password": "hackme",
            "email": "test@example.com",
        },
    ],
    "calendars": [
        {
            "id": "1",
            "owner": "admin",
            "name": "Default Calendar",
            "color": "#000000",
            "order": 0,
        },
        {
            "id": "2",
            "owner": "admin",
            "name": "Vacation",
            "color": "#FFFFFF",
            "order": 1,
        },
        {
            "id": "3",
            "owner": "test",
            "name": "Test Calendar",
            "color": "#FF00FF",
            "order": 0,
        },
    ],
    "events": [
        {
            "id": "1",
            "calendar": "2",
            "summary": "Party",
            "description": "",
            "status": "CONFIRMED",
            "created": datetime(2020, 1, 12, 12, 0),
            "last_modified": datetime(2020, 1, 12, 12, 35, 11),
            "start": datetime(2020, 3, 14, 18, 0),
            "end": datetime(2020, 3, 14, 22, 0),
            "organizer": "admin",
            "attendees": ["admin", "test"],
        },
        {
            "id": "2",
            "calendar": "3",
            "summary": "Business trip",
            "description": "",
            "status": "CONFIRMED",
            "created": datetime(2020, 1, 12, 13, 0),
            "last_modified": datetime(2020, 1, 12, 18, 56, 2),
            "start": datetime(2020, 6, 1, 12, 0),
            "end": datetime(2020, 6, 1, 16, 30),
            "organizer": "test",
            "attendees": [],
        },
        {
            "id": "1",
            "calendar": "1",
            "summary": "Sprint review, planning",
            "description": "",
            "status": "CONFIRMED",
            "created": datetime(2020, 1, 17, 14, 0),
            "last_modified": datetime(2020, 1, 17, 16, 0),
            "start": datetime(2020, 3, 14, 18, 0),
            "end": datetime(2020, 3, 14, 22, 0),
            "organizer": "admin",
            "attendees": ["admin", "test"],
        },
    ],
}


def application(environ, start_response):
    auth = Auth(DB)
    rights = Rights()
    storage = Storage(DB)
    web = Web()
    app = Application(
        auth=auth,
        rights=rights,
        storage=storage,
        web=web,
    )

    return app(environ, start_response)
