# This file is related to Radicale - CalDAV and CardDAV server
# for email notifications
# Copyright © 2025-2025 Nate Harris
#
# This library is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Radicale.  If not, see <http://www.gnu.org/licenses/>.

import enum
import hashlib
import json
import re
import smtplib
import ssl
from datetime import datetime, timedelta
from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from typing import Any, Dict, List, Optional, Sequence, Tuple

import vobject

from radicale.hook import (BaseHook, HookNotificationItem,
                           HookNotificationItemTypes)
from radicale.log import logger

PLUGIN_CONFIG_SCHEMA = {
    "hook": {
        "smtp_server": {
            "value": "",
            "type": str
        },
        "smtp_port": {
            "value": "",
            "type": str
        },
        "smtp_security": {
            "value": "none",
            "type": str,
        },
        "smtp_ssl_verify_mode": {
            "value": "REQUIRED",
            "type": str,
        },
        "smtp_username": {
            "value": "",
            "type": str
        },
        "smtp_password": {
            "value": "",
            "type": str
        },
        "from_email": {
            "value": "",
            "type": str
        },
        "new_or_added_to_event_template": {
            "value": """Hello $attendee_name,

You have been added as an attendee to the following calendar event.

    $event_title
    $event_start_time - $event_end_time
    $event_location

This is an automated message. Please do not reply.""",
            "type": str
        },
        "deleted_or_removed_from_event_template": {
            "value": """Hello $attendee_name,

The following event has been deleted.

    $event_title
    $event_start_time - $event_end_time
    $event_location

This is an automated message. Please do not reply.""",
            "type": str
        },
        "updated_event_template": {
            "value": """Hello $attendee_name,

The following event has been updated.

    $event_title
    $event_start_time - $event_end_time
    $event_location

This is an automated message. Please do not reply.""",
            "type": str
        },
        "mass_email": {
            "value": False,
            "type": bool,
        }
    }
}

MESSAGE_TEMPLATE_VARIABLES = [
    "organizer_name",
    "from_email",
    "attendee_name",
    "event_title",
    "event_start_time",
    "event_end_time",
    "event_location",
]


class SMTP_SECURITY_TYPE_ENUM(enum.Enum):
    EMPTY = ""
    NONE = "none"
    STARTTLS = "starttls"
    TLS = "tls"

    @classmethod
    def from_string(cls, value):
        """Convert a string to the corresponding enum value."""
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"Invalid security type: {value}. Allowed values are: {[m.value for m in cls]}")


class SMTP_SSL_VERIFY_MODE_ENUM(enum.Enum):
    EMPTY = ""
    NONE = "NONE"
    OPTIONAL = "OPTIONAL"
    REQUIRED = "REQUIRED"

    @classmethod
    def from_string(cls, value):
        """Convert a string to the corresponding enum value."""
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"Invalid SSL verify mode: {value}. Allowed values are: {[m.value for m in cls]}")


SMTP_SECURITY_TYPES: Sequence[str] = (SMTP_SECURITY_TYPE_ENUM.NONE.value,
                                      SMTP_SECURITY_TYPE_ENUM.STARTTLS.value,
                                      SMTP_SECURITY_TYPE_ENUM.TLS.value)
SMTP_SSL_VERIFY_MODES: Sequence[str] = (SMTP_SSL_VERIFY_MODE_ENUM.NONE.value,
                                        SMTP_SSL_VERIFY_MODE_ENUM.OPTIONAL.value,
                                        SMTP_SSL_VERIFY_MODE_ENUM.REQUIRED.value)


def read_ics_event(contents: str) -> Optional['Event']:
    """
    Read the vobject item from the provided string and create an Event.
    """
    v_cal: vobject.base.Component = vobject.readOne(contents)
    cal: Calendar = Calendar(vobject_item=v_cal)
    return cal.event if cal.event else None


def ics_contents_contains_event(contents: str):
    """
    Check if the ICS contents contain an event (versus a VADDRESSBOOK, VTODO or VJOURNAL).
    :param contents: The contents of the ICS file.
    :return: True if the ICS file contains an event, False otherwise.
    """
    return read_ics_event(contents) is not None


def extract_email(value: str) -> Optional[str]:
    """Extract email address from a string."""
    if not value:
        return None
    value = value.strip().lower()
    match = re.search(r"mailto:([^;]+)", value)
    if match:
        return match.group(1)
    # Fallback to the whole value if no mailto found
    return value if "@" in value else None


def determine_added_removed_and_unaltered_attendees(original_event: 'Event',
                                                    new_event: 'Event') -> (
        Tuple)[List['Attendee'], List['Attendee'], List['Attendee']]:
    """
    Determine the added, removed and unaltered attendees between two events.
    """
    original_event_attendees = {attendee.email: attendee for attendee in original_event.attendees}
    new_event_attendees = {attendee.email: attendee for attendee in new_event.attendees}
    # Added attendees are those who are in the new event but not in the original event
    added_attendees = [new_event_attendees[email] for email in new_event_attendees if
                       email not in original_event_attendees]
    # Removed attendees are those who are in the original event but not in the new event
    removed_attendees = [original_event_attendees[email] for email in original_event_attendees if
                         email not in new_event_attendees]
    # Unaltered attendees are those who are in both events
    unaltered_attendees = [original_event_attendees[email] for email in original_event_attendees if
                           email in new_event_attendees]

    return added_attendees, removed_attendees, unaltered_attendees


def event_details_other_than_attendees_changed(original_event: 'Event',
                                               new_event: 'Event') -> bool:
    """
    Check if any details other than attendees and IDs have changed between two events.
    """

    def hash_dict(d: Dict[str, Any]) -> str:
        """
        Create a hash of the dictionary to compare contents.
        This will ignore None values and empty strings.
        """
        return hashlib.sha1(json.dumps(d).encode("utf8")).hexdigest()

    original_event_details = {
        "summary": original_event.summary,
        "description": original_event.description,
        "location": original_event.location,
        "datetime_start": original_event.datetime_start.time_string() if original_event.datetime_start else None,
        "datetime_end": original_event.datetime_end.time_string() if original_event.datetime_end else None,
        "duration": original_event.duration,
        "status": original_event.status,
        "organizer": original_event.organizer
    }
    new_event_details = {
        "summary": new_event.summary,
        "description": new_event.description,
        "location": new_event.location,
        "datetime_start": new_event.datetime_start.time_string() if new_event.datetime_start else None,
        "datetime_end": new_event.datetime_end.time_string() if new_event.datetime_end else None,
        "duration": new_event.duration,
        "status": new_event.status,
        "organizer": new_event.organizer
    }

    return hash_dict(original_event_details) != hash_dict(new_event_details)


class ContentLine:
    _key: str
    value: Any
    _params: Dict[str, Any]

    def __init__(self, key: str, value: Any, params: Optional[Dict[str, Any]] = None):
        self._key = key
        self.value = value
        self._params = params or {}

    def _get_param(self, name: str) -> List[Optional[Any]]:
        """
        Get a parameter value by name.
        :param name: The name of the parameter to retrieve.
        :return: A list of all matching parameter values, or a single-entry (None) list if the parameter does not exist.
        """
        return self._params.get(name, [None])


class VComponent:
    _vobject_item: vobject.base.Component

    def __init__(self,
                 vobject_item: vobject.base.Component,
                 component_type: str):
        """Initialize a VComponent."""
        if not isinstance(vobject_item, vobject.base.Component):
            raise ValueError("vobject_item must be a vobject.base.Component")
        if vobject_item.name != component_type:
            raise ValueError("Invalid component type: %r, expected %r" %
                             (vobject_item.name, component_type))
        self._vobject_item = vobject_item

    def _get_content_lines(self, name: str) -> List[ContentLine]:
        """Get each matching content line."""
        name = name.lower().strip()
        _content_lines = self._vobject_item.contents.get(name, None)
        if not _content_lines:
            return [ContentLine("", None)]
        if not isinstance(_content_lines, (list, tuple)):
            _content_lines = [_content_lines]
        return [ContentLine(key=name, value=cl.value, params=cl.params)
                for cl in _content_lines if isinstance(cl, vobject.base.ContentLine)] or [ContentLine("", None)]

    def _get_sub_vobjects(self, attribute_name: str, _class: type['VComponent']) -> List[Optional['VComponent']]:
        """Get sub vobject items of the specified type if they exist."""
        sub_vobjects = getattr(self._vobject_item, attribute_name, None)
        if not sub_vobjects:
            return [None]
        if not isinstance(sub_vobjects, (list, tuple)):
            sub_vobjects = [sub_vobjects]
        return ([_class(vobject_item=so) for so in sub_vobjects if  # type: ignore
                 isinstance(so, vobject.base.Component)]
                or [None])


class Attendee(ContentLine):
    def __init__(self, content_line: ContentLine):
        super().__init__(key=content_line._key, value=content_line.value,
                         params=content_line._params)

    @property
    def email(self) -> Optional[str]:
        """Return the email address of the attendee."""
        return extract_email(self.value)

    @property
    def role(self) -> Optional[str]:
        """Return the role of the attendee."""
        return self._get_param("ROLE")[0]

    @property
    def participation_status(self) -> Optional[str]:
        """Return the participation status of the attendee."""
        return self._get_param("PARTSTAT")[0]

    @property
    def name(self) -> Optional[str]:
        return self._get_param("CN")[0]

    @property
    def delegated_from(self) -> Optional[str]:
        """Return the email address of the attendee who delegated this attendee."""
        delegate = self._get_param("DELEGATED-FROM")[0]
        return extract_email(delegate) if delegate else None


class TimeWithTimezone(ContentLine):
    def __init__(self, content_line: ContentLine):
        """Initialize a time with timezone content line."""
        super().__init__(key=content_line._key, value=content_line.value,
                         params=content_line._params)

    @property
    def timezone_id(self) -> Optional[str]:
        """Return the timezone of the time."""
        return self._get_param("TZID")[0]

    @property
    def time(self) -> Optional[datetime]:
        """Return the time value."""
        return self.value

    def time_string(self, _format: str = "%Y-%m-%d %H:%M:%S") -> Optional[str]:
        """Return the time as a formatted string."""
        if self.time:
            return self.time.strftime(_format)
        return None


class Alarm(VComponent):
    def __init__(self,
                 vobject_item: vobject.base.Component):
        """Initialize a VALARM item."""
        super().__init__(vobject_item, "VALARM")

    @property
    def action(self) -> Optional[str]:
        """Return the action of the alarm."""
        return self._get_content_lines("ACTION")[0].value

    @property
    def description(self) -> Optional[str]:
        """Return the description of the alarm."""
        return self._get_content_lines("DESCRIPTION")[0].value

    @property
    def trigger(self) -> Optional[timedelta]:
        """Return the trigger of the alarm."""
        return self._get_content_lines("TRIGGER")[0].value

    @property
    def repeat(self) -> Optional[int]:
        """Return the repeat interval of the alarm."""
        repeat = self._get_content_lines("REPEAT")[0].value
        return int(repeat) if repeat is not None else None

    @property
    def duration(self) -> Optional[str]:
        """Return the duration of the alarm."""
        return self._get_content_lines("DURATION")[0].value


class SubTimezone(VComponent):
    def __init__(self,
                 vobject_item: vobject.base.Component,
                 component_type: str):
        """Initialize a sub VTIMEZONE item."""
        super().__init__(vobject_item, component_type)

    @property
    def datetime_start(self) -> Optional[datetime]:
        """Return the start datetime of the timezone."""
        return self._get_content_lines("DTSTART")[0].value

    @property
    def timezone_name(self) -> Optional[str]:
        """Return the timezone name."""
        return self._get_content_lines("TZNAME")[0].value

    @property
    def timezone_offset_from(self) -> Optional[str]:
        """Return the timezone offset from."""
        return self._get_content_lines("TZOFFSETFROM")[0].value

    @property
    def timezone_offset_to(self) -> Optional[str]:
        """Return the timezone offset to."""
        return self._get_content_lines("TZOFFSETTO")[0].value


class StandardTimezone(SubTimezone):
    def __init__(self,
                 vobject_item: vobject.base.Component):
        """Initialize a STANDARD item."""
        super().__init__(vobject_item, "STANDARD")


class DaylightTimezone(SubTimezone):
    def __init__(self,
                 vobject_item: vobject.base.Component):
        """Initialize a DAYLIGHT item."""
        super().__init__(vobject_item, "DAYLIGHT")


class Timezone(VComponent):
    def __init__(self,
                 vobject_item: vobject.base.Component):
        """Initialize a VTIMEZONE item."""
        super().__init__(vobject_item, "VTIMEZONE")

    @property
    def timezone_id(self) -> Optional[str]:
        """Return the timezone ID."""
        return self._get_content_lines("TZID")[0].value

    @property
    def standard(self) -> Optional[StandardTimezone]:
        """Return the STANDARD subcomponent if it exists."""
        return self._get_sub_vobjects("standard", StandardTimezone)[0]  # type: ignore

    @property
    def daylight(self) -> Optional[DaylightTimezone]:
        """Return the DAYLIGHT subcomponent if it exists."""
        return self._get_sub_vobjects("daylight", DaylightTimezone)[0]  # type: ignore


class Event(VComponent):
    def __init__(self,
                 vobject_item: vobject.base.Component):
        """Initialize a VEVENT item."""
        super().__init__(vobject_item, "VEVENT")

    @property
    def datetime_stamp(self) -> Optional[str]:
        """Return the last modification datetime of the event."""
        return self._get_content_lines("DTSTAMP")[0].value

    @property
    def datetime_start(self) -> Optional[TimeWithTimezone]:
        """Return the start datetime of the event."""
        _content_line = self._get_content_lines("DTSTART")[0]
        return TimeWithTimezone(_content_line) if _content_line.value else None

    @property
    def datetime_end(self) -> Optional[TimeWithTimezone]:
        """Return the end datetime of the event. Either this or duration will be available, but not both."""
        _content_line = self._get_content_lines("DTEND")[0]
        return TimeWithTimezone(_content_line) if _content_line.value else None

    @property
    def duration(self) -> Optional[int]:
        """Return the duration of the event. Either this or datetime_end will be available, but not both."""
        return self._get_content_lines("DURATION")[0].value

    @property
    def uid(self) -> Optional[str]:
        """Return the UID of the event."""
        return self._get_content_lines("UID")[0].value

    @property
    def status(self) -> Optional[str]:
        """Return the status of the event."""
        return self._get_content_lines("STATUS")[0].value

    @property
    def summary(self) -> Optional[str]:
        """Return the summary of the event."""
        return self._get_content_lines("SUMMARY")[0].value

    @property
    def description(self) -> Optional[str]:
        """Return the description of the event."""
        return self._get_content_lines("DESCRIPTION")[0].value

    @property
    def location(self) -> Optional[str]:
        """Return the location of the event."""
        return self._get_content_lines("LOCATION")[0].value

    @property
    def organizer(self) -> Optional[str]:
        """Return the organizer of the event."""
        return self._get_content_lines("ORGANIZER")[0].value

    @property
    def alarms(self) -> List[Alarm]:
        """Return a list of VALARM items in the event."""
        return self._get_sub_vobjects("valarm", Alarm)  # type: ignore # Can be multiple

    @property
    def attendees(self) -> List[Attendee]:
        """Return a list of ATTENDEE items in the event."""
        _content_lines = self._get_content_lines("ATTENDEE")
        return [Attendee(content_line=attendee) for attendee in _content_lines if attendee.value is not None]


class Calendar(VComponent):
    def __init__(self,
                 vobject_item: vobject.base.Component):
        """Initialize a VCALENDAR item."""
        super().__init__(vobject_item, "VCALENDAR")

    @property
    def version(self) -> Optional[str]:
        """Return the version of the calendar."""
        return self._get_content_lines("VERSION")[0].value

    @property
    def product_id(self) -> Optional[str]:
        """Return the product ID of the calendar."""
        return self._get_content_lines("PRODID")[0].value

    @property
    def event(self) -> Optional[Event]:
        """Return the VEVENT item in the calendar."""
        return self._get_sub_vobjects("vevent", Event)[0]  # type: ignore

    # TODO: Add VTODO and VJOURNAL support if needed

    @property
    def timezone(self) -> Optional[Timezone]:
        """Return the VTIMEZONE item in the calendar."""
        return self._get_sub_vobjects("vtimezone", Timezone)[0]  # type: ignore


class EmailEvent:
    def __init__(self,
                 event: Event,
                 ics_content: str,
                 ics_file_name: str):
        self.event = event
        self.ics_content = ics_content
        self.file_name = ics_file_name


class ICSEmailAttachment:
    def __init__(self, file_content: str, file_name: str):
        self.file_content = file_content
        self.file_name = file_name

    def prepare_email_part(self) -> MIMEBase:
        # Add file as application/octet-stream
        # Email client can usually download this automatically as attachment
        part = MIMEBase("application", "octet-stream")
        part.set_payload(self.file_content)

        # Encode file in ASCII characters to send by email
        encode_base64(part)

        # Add header as key/value pair to attachment part
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {self.file_name}",
        )

        return part


class MessageTemplate:
    def __init__(self, subject: str, body: str):
        self.subject = subject
        self.body = body
        if not self._validate_template(template=subject):
            raise ValueError(
                f"Invalid subject template: {subject}. Allowed variables are: {MESSAGE_TEMPLATE_VARIABLES}")
        if not self._validate_template(template=body):
            raise ValueError(f"Invalid body template: {body}. Allowed variables are: {MESSAGE_TEMPLATE_VARIABLES}")

    def __repr__(self):
        return f'MessageTemplate(subject={self.subject}, body={self.body})'

    def __str__(self):
        return f'{self.subject}: {self.body}'

    def _validate_template(self, template: str) -> bool:
        """
        Validate the template to ensure it contains only allowed variables.
        :param template: The template string to validate.
        :return: True if the template is valid, False otherwise.
        """
        # Find all variables in the template (starting with $)
        variables = re.findall(r'\$(\w+)', template)
        # Check if all variables are in the allowed list
        for var in variables:
            if var not in MESSAGE_TEMPLATE_VARIABLES:
                logger.error(
                    f"Invalid variable '{var}' found in template. Allowed variables are: {MESSAGE_TEMPLATE_VARIABLES}")
                return False
        return True

    def _populate_template(self, template: str, context: dict) -> str:
        """
        Populate the template with the provided context.
        :param template: The template string to populate.
        :param context: A dictionary containing the context variables.
        :return: The populated template string.
        """
        for key, value in context.items():
            template = template.replace(f"${key}", str(value or ""))
        return template

    def build_message(self, event: EmailEvent, from_email: str, mass_email: bool,
                      attendee: Optional[Attendee] = None) -> str:
        """
        Build the message body using the template.
        :param event: The event to include in the message.
        :param from_email: The email address of the sender.
        :param mass_email: Whether this is a mass email to multiple attendees.
        :param attendee: The specific attendee to include in the message, if not a mass email.
        :return: The formatted message body.
        """
        if mass_email:
            # If this is a mass email, we do not use individual attendee names
            attendee_name = "everyone"
        else:
            assert attendee is not None, "Attendee must be provided for non-mass emails"
            attendee_name = attendee.name if attendee else "Unknown Name"  # type: ignore

        context = {
            "attendee_name": attendee_name,
            "from_email": from_email,
            "organizer_name": event.event.organizer or "Unknown Organizer",
            "event_title": event.event.summary or "No Title",
            "event_start_time": event.event.datetime_start.time_string(),  # type: ignore
            "event_end_time": event.event.datetime_end.time_string() if event.event.datetime_end else "No End Time",
            "event_location": event.event.location or "No Location Specified",
        }
        return self._populate_template(template=self.body, context=context)

    def build_subject(self, event: EmailEvent, from_email: str, mass_email: bool,
                      attendee: Optional[Attendee] = None) -> str:
        """
        Build the message subject using the template.
        :param attendee: The attendee to include in the subject.
        :param event: The event to include in the subject.
        :param from_email: The email address of the sender.
        :param mass_email: Whether this is a mass email to multiple attendees.
        :param attendee: The specific attendee to include in the message, if not a mass email.
        :return: The formatted message subject.
        """
        if mass_email:
            # If this is a mass email, we do not use individual attendee names
            attendee_name = "everyone"
        else:
            assert attendee is not None, "Attendee must be provided for non-mass emails"
            attendee_name = attendee.name if attendee else "Unknown Name"  # type: ignore

        context = {
            "attendee_name": attendee_name,
            "from_email": from_email,
            "organizer_name": event.event.organizer or "Unknown Organizer",
            "event_title": event.event.summary or "No Title",
            "event_start_time": event.event.datetime_start.time_string(),  # type: ignore
            "event_end_time": event.event.datetime_end.time_string() if event.event.datetime_end else "No End Time",
            "event_location": event.event.location or "No Location Specified",
        }
        return self._populate_template(template=self.subject, context=context)


class EmailConfig:
    def __init__(self,
                 host: str,
                 port: int,
                 security: str,
                 ssl_verify_mode: str,
                 username: str,
                 password: str,
                 from_email: str,
                 send_mass_emails: bool,
                 dryrun: bool,
                 new_or_added_to_event_template: MessageTemplate,
                 deleted_or_removed_from_event_template: MessageTemplate,
                 updated_event_template: MessageTemplate):
        self.host = host
        self.port = port
        self.security = SMTP_SECURITY_TYPE_ENUM.from_string(value=security)
        self.ssl_verify_mode = SMTP_SSL_VERIFY_MODE_ENUM.from_string(value=ssl_verify_mode)
        self.username = username
        self.password = password
        self.from_email = from_email
        self.send_mass_emails = send_mass_emails
        self.dryrun = dryrun
        self.new_or_added_to_event_template = new_or_added_to_event_template
        self.deleted_or_removed_from_event_template = deleted_or_removed_from_event_template
        self.updated_event_template = updated_event_template

    def __str__(self) -> str:
        """
        Return a string representation of the EmailConfig.
        """
        return f"EmailConfig(host={self.host}, port={self.port}, username={self.username}, " \
               f"from_email={self.from_email}, send_mass_emails={self.send_mass_emails}, dryrun={self.dryrun})"

    def __repr__(self):
        return self.__str__()

    def send_added_email(self, attendees: List[Attendee], event: EmailEvent) -> bool:
        """
        Send a notification for created events (and/or adding attendees).
        :param attendees: The attendees to inform.
        :param event: The event being created (or the event the attendee is being added to).
        :return: True if the email was sent successfully, False otherwise.
        """
        ics_attachment = ICSEmailAttachment(file_content=event.ics_content, file_name=f"{event.file_name}")

        return self._prepare_and_send_email(template=self.new_or_added_to_event_template, attendees=attendees,
                                            event=event,
                                            ics_attachment=ics_attachment)

    def send_updated_email(self, attendees: List[Attendee], event: EmailEvent) -> bool:
        """
        Send a notification for updated events.
        :param attendees: The attendees to inform.
        :param event: The event being updated.
        :return: True if the email was sent successfully, False otherwise.
        """
        ics_attachment = ICSEmailAttachment(file_content=event.ics_content, file_name=f"{event.file_name}")

        return self._prepare_and_send_email(template=self.updated_event_template, attendees=attendees, event=event,
                                            ics_attachment=ics_attachment)

    def send_deleted_email(self, attendees: List[Attendee], event: EmailEvent) -> bool:
        """
        Send a notification for deleted events (and/or removing attendees).
        :param attendees: The attendees to inform.
        :param event: The event being deleted (or the event the attendee is being removed from).
        :return: True if the email was sent successfully, False otherwise.
        """
        return self._prepare_and_send_email(template=self.deleted_or_removed_from_event_template, attendees=attendees,
                                            event=event,
                                            ics_attachment=None)

    def _prepare_and_send_email(self, template: MessageTemplate, attendees: List[Attendee],
                                event: EmailEvent, ics_attachment: Optional[ICSEmailAttachment] = None) -> bool:
        """
        Prepare the email message(s) and send them to the attendees.
        :param template: The message template to use for the email.
        :param attendees: The list of attendees to notify.
        :param event: The event to include in the email.
        :param ics_attachment: An optional ICS attachment to include in the email.
        :return: True if the email(s) were sent successfully, False otherwise.
        """
        if self.send_mass_emails:
            # If mass emails are enabled, we send one email to all attendees
            body = template.build_message(event=event, from_email=self.from_email,
                                          mass_email=self.send_mass_emails, attendee=None)
            subject = template.build_subject(event=event, from_email=self.from_email,
                                             mass_email=self.send_mass_emails, attendee=None)

            return self._send_email(subject=subject, body=body, attendees=attendees, ics_attachment=ics_attachment)
        else:
            failure_encountered = False
            for attendee in attendees:
                # For individual emails, we send one email per attendee
                body = template.build_message(event=event, from_email=self.from_email,
                                              mass_email=self.send_mass_emails, attendee=attendee)
                subject = template.build_subject(event=event, from_email=self.from_email,
                                                 mass_email=self.send_mass_emails, attendee=attendee)

                if not self._send_email(subject=subject, body=body, attendees=[attendee],
                                        ics_attachment=ics_attachment):
                    failure_encountered = True

            return not failure_encountered  # Return True if all emails were sent successfully

    def _build_context(self) -> ssl.SSLContext:
        """
        Build the SSL context based on the configured security and SSL verify mode.
        :return: An SSLContext object configured for the SMTP connection.
        """
        context = ssl.create_default_context()
        if self.ssl_verify_mode == SMTP_SSL_VERIFY_MODE_ENUM.REQUIRED:
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
        elif self.ssl_verify_mode == SMTP_SSL_VERIFY_MODE_ENUM.OPTIONAL:
            context.check_hostname = True
            context.verify_mode = ssl.CERT_OPTIONAL
        else:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        return context

    def _send_email(self,
                    subject: str,
                    body: str,
                    attendees: List[Attendee],
                    ics_attachment: Optional[ICSEmailAttachment] = None) -> bool:
        """
        Send the notification using the email service.
        :param subject: The subject of the notification.
        :param body: The body of the notification.
        :param attendees: The attendees to notify.
        :param ics_attachment: An optional ICS attachment to include in the email.
        :return: True if the email was sent successfully, False otherwise.
        """
        to_addresses = [attendee.email for attendee in attendees if attendee.email]
        if not to_addresses:
            logger.warning("No valid email addresses found in attendees. Cannot send email.")
            return False

        if self.dryrun is True:
            logger.warning("Hook 'email': DRY-RUN _send_email / to_addresses=%r", to_addresses)
            return True

        # Add headers
        message = MIMEMultipart("mixed")
        message["From"] = self.from_email
        message["Reply-To"] = self.from_email
        message["Subject"] = subject
        message["Date"] = formatdate(localtime=True)

        # Add body text
        message.attach(MIMEText(body, "plain"))

        # Add ICS attachment if provided
        if ics_attachment:
            ical_attachment = ics_attachment.prepare_email_part()
            message.attach(ical_attachment)

        # Convert message to text
        text = message.as_string()

        try:
            if self.security == SMTP_SECURITY_TYPE_ENUM.EMPTY:
                logger.warning("SMTP security type is empty, raising ValueError.")
                raise ValueError("SMTP security type cannot be empty. Please specify a valid security type.")
            elif self.security == SMTP_SECURITY_TYPE_ENUM.NONE:
                server = smtplib.SMTP(host=self.host, port=self.port)
            elif self.security == SMTP_SECURITY_TYPE_ENUM.STARTTLS:
                context = self._build_context()
                server = smtplib.SMTP(host=self.host, port=self.port)
                server.ehlo()  # Identify self to server
                server.starttls(context=context)  # Start TLS connection
                server.ehlo()  # Identify again after starting TLS
            elif self.security == SMTP_SECURITY_TYPE_ENUM.TLS:
                context = self._build_context()
                server = smtplib.SMTP_SSL(host=self.host, port=self.port, context=context)

            if self.username and self.password:
                logger.debug("Logging in to SMTP server with username: %s", self.username)
                server.login(user=self.username, password=self.password)

            errors: Dict[str, Tuple[int, bytes]] = server.sendmail(from_addr=self.from_email, to_addrs=to_addresses,
                                                                   msg=text)
            logger.debug("Email sent successfully to %s", to_addresses)
            server.quit()
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error occurred: {e}")
            return False

        if errors:
            for email, (code, error) in errors.items():
                logger.error(f"Failed to send email to {email}: {str(error)} (Code: {code})")
            return False

        return True


def _read_event(vobject_data: str) -> EmailEvent:
    """
    Read the vobject item from the provided string and create an EmailEvent.
    """
    v_cal: vobject.base.Component = vobject.readOne(vobject_data)
    cal: Calendar = Calendar(vobject_item=v_cal)
    event: Event = cal.event  # type: ignore

    return EmailEvent(
        event=event,
        ics_content=vobject_data,
        ics_file_name="event.ics"
    )


class Hook(BaseHook):
    def __init__(self, configuration):
        super().__init__(configuration)
        self.email_config = EmailConfig(
            host=self.configuration.get("hook", "smtp_server"),
            port=self.configuration.get("hook", "smtp_port"),
            security=self.configuration.get("hook", "smtp_security"),
            ssl_verify_mode=self.configuration.get("hook", "smtp_ssl_verify_mode"),
            username=self.configuration.get("hook", "smtp_username"),
            password=self.configuration.get("hook", "smtp_password"),
            from_email=self.configuration.get("hook", "from_email"),
            send_mass_emails=self.configuration.get("hook", "mass_email"),
            dryrun=self.configuration.get("hook", "dryrun"),
            new_or_added_to_event_template=MessageTemplate(
                subject="You have been added to an event",
                body=self.configuration.get("hook", "new_or_added_to_event_template")
            ),
            deleted_or_removed_from_event_template=MessageTemplate(
                subject="An event you were invited to has been deleted",
                body=self.configuration.get("hook", "deleted_or_removed_from_event_template")
            ),
            updated_event_template=MessageTemplate(
                subject="An event you are invited to has been updated",
                body=self.configuration.get("hook", "updated_event_template")
            )
        )
        logger.info(
            "Email hook initialized with configuration: %s",
            self.email_config
        )

    def notify(self, notification_item) -> None:
        """
        Entrypoint for processing a single notification item.
        Overrides default notify method from BaseHook.
        Triggered by Radicale when a notifiable event occurs (e.g. item added, updated or deleted)
        """
        if isinstance(notification_item, HookNotificationItem):
            self._process_event_and_notify(notification_item)

    def _process_event_and_notify(self, notification_item: HookNotificationItem) -> None:
        """
        Process the event and send an email notification.
        :param notification_item: The single item to process.
        :type notification_item: HookNotificationItem
        :return: None
        """
        if self.email_config.dryrun:
            logger.warning("Hook 'email': DRY-RUN received notification_item: %r", vars(notification_item))
        else:
            logger.debug("Received notification_item: %r", vars(notification_item))
        try:
            notification_type = HookNotificationItemTypes(value=notification_item.type)
        except ValueError:
            logger.warning("Unknown notification item type: %s", notification_item.type)
            return

        if notification_type == HookNotificationItemTypes.CPATCH:
            # Ignore cpatch notifications (PROPPATCH requests for WebDAV metadata updates)
            return

        elif notification_type == HookNotificationItemTypes.UPSERT:
            # Handle upsert notifications

            new_item_str: str = notification_item.new_content  # type: ignore # A serialized vobject.base.Component
            previous_item_str: Optional[str] = notification_item.old_content

            if not ics_contents_contains_event(contents=new_item_str):
                # If ICS file does not contain an event, do not send any notifications (regardless of previous content).
                logger.debug("No event found in the ICS file, skipping notification.")
                return

            email_event: EmailEvent = _read_event(vobject_data=new_item_str)  # type: ignore
            if not email_event:
                logger.error("Failed to read event from new content: %s", new_item_str)
                return
            email_event_event = email_event.event  # type: ignore
            if not email_event_event:
                logger.error("Event could not be parsed from the new content: %s", new_item_str)
                return
            email_event_end_time = email_event_event.datetime_end  # type: ignore
            # Skip notification if the event end time is more than 1 minute in the past.
            if email_event_end_time and email_event_end_time.time:
                event_end = email_event_end_time.time  # type: ignore
                now = datetime.now(
                    event_end.tzinfo) if event_end.tzinfo else datetime.now()  # Handle timezone-aware datetime
                if event_end < (now - timedelta(minutes=1)):
                    logger.warning("Event end time is in the past, skipping notification for event: %s",
                                   email_event_event.uid)
                return

            if not previous_item_str:
                # Dealing with a completely new event, no previous content to compare against.
                # Email every attendee about the new event.
                logger.debug("New event detected, sending notifications to all attendees.")
                email_success: bool = self.email_config.send_added_email(  # type: ignore
                    attendees=email_event.event.attendees,
                    event=email_event
                )
                if not email_success:
                    logger.error("Failed to send some or all added email notifications for event: %s",
                                 email_event.event.uid)
                return

            # Dealing with an update to an existing event, compare new and previous content.
            new_event: Event = read_ics_event(contents=new_item_str)  # type: ignore
            previous_event: Optional[Event] = read_ics_event(contents=previous_item_str)
            if not previous_event:
                # If we cannot parse the previous event for some reason, simply treat it as a new event.
                logger.warning("Previous event content could not be parsed, treating as a new event.")
                email_success: bool = self.email_config.send_added_email(  # type: ignore
                    attendees=email_event.event.attendees,
                    event=email_event
                )
                if not email_success:
                    logger.error("Failed to send some or all added email notifications for event: %s",
                                 email_event.event.uid)
                return

            # Determine added, removed, and unaltered attendees
            added_attendees, removed_attendees, unaltered_attendees = determine_added_removed_and_unaltered_attendees(
                original_event=previous_event, new_event=new_event)

            # Notify added attendees as "event created"
            if added_attendees:
                email_success: bool = self.email_config.send_added_email(  # type: ignore
                    attendees=added_attendees,
                    event=email_event
                )
                if not email_success:
                    logger.error("Failed to send some or all added email notifications for event: %s",
                                 email_event.event.uid)

            # Notify removed attendees as "event deleted"
            if removed_attendees:
                email_success: bool = self.email_config.send_deleted_email(  # type: ignore
                    attendees=removed_attendees,
                    event=email_event
                )
                if not email_success:
                    logger.error("Failed to send some or all removed email notifications for event: %s",
                                 email_event.event.uid)

            # Notify unaltered attendees as "event updated" if details other than attendees have changed
            if unaltered_attendees and event_details_other_than_attendees_changed(original_event=previous_event,
                                                                                  new_event=new_event):
                email_success: bool = self.email_config.send_updated_email(  # type: ignore
                    attendees=unaltered_attendees,
                    event=email_event
                )
                if not email_success:
                    logger.error("Failed to send some or all updated email notifications for event: %s",
                                 email_event.event.uid)

            # Skip sending notifications to existing attendees if the only changes made to the event
            # were the addition/removal of other attendees.

            return

        elif notification_type == HookNotificationItemTypes.DELETE:
            # Handle delete notifications

            deleted_item_str: str = notification_item.old_content  # type: ignore # A serialized vobject.base.Component

            if not ics_contents_contains_event(contents=deleted_item_str):
                # If the ICS file does not contain an event, we do not send any notifications.
                logger.debug("No event found in the ICS file, skipping notification.")
                return

            email_event: EmailEvent = _read_event(vobject_data=deleted_item_str)  # type: ignore

            email_success: bool = self.email_config.send_deleted_email(  # type: ignore
                attendees=email_event.event.attendees,
                event=email_event
            )
            if not email_success:
                logger.error("Failed to send some or all deleted email notifications for event: %s",
                             email_event.event.uid)

            return

        return
