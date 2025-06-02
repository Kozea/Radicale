"""vCard property definitions and mappings for privacy enforcement.

This module contains the enumeration of vCard 4.0 properties and their mappings
to privacy settings for the Radicale privacy enforcement system.
"""

from enum import Enum, auto


class VCardProperty(Enum):
    """Enumeration of vCard 4.0 properties."""
    # Identification Properties
    FN = auto()  # Formatted Name
    N = auto()   # Name
    NICKNAME = auto()
    PHOTO = auto()
    BDAY = auto()
    ANNIVERSARY = auto()
    GENDER = auto()

    # Delivery Addressing Properties
    ADR = auto()  # Address
    LABEL = auto()

    # Communications Properties
    TEL = auto()  # Telephone
    EMAIL = auto()
    IMPP = auto()  # Instant Messaging
    LANG = auto()  # Language

    # Geographical Properties
    TZ = auto()  # Time Zone
    GEO = auto()  # Geographical Position

    # Organizational Properties
    TITLE = auto()
    ROLE = auto()
    LOGO = auto()
    ORG = auto()  # Organization
    MEMBER = auto()
    RELATED = auto()

    # Explanatory Properties
    CATEGORIES = auto()
    NOTE = auto()
    PRODID = auto()
    REV = auto()  # Revision
    SOUND = auto()
    UID = auto()
    CLIENTPIDMAP = auto()
    URL = auto()
    VERSION = auto()

    # Security Properties
    KEY = auto()

    # Calendar Properties
    CALADRURI = auto()
    CALURI = auto()
    FBURL = auto()

    # Extended Properties
    KIND = auto()
    XML = auto()
    SOURCE = auto()


class VCardPropertyType(Enum):
    """Enumeration of vCard property value types."""
    SINGLE = auto()  # Single value property
    LIST = auto()    # List of values property
    PRESENCE = auto()  # Property that only indicates presence


# Mapping of privacy settings to vCard properties
PRIVACY_TO_VCARD_MAP = {
    'disallow_company': ['org', 'logo'],
    'disallow_title': ['title', 'role'],
    'disallow_photo': ['photo'],
    'disallow_birthday': ['bday', 'anniversary'],
    'disallow_address': ['adr', 'label'],
}

# List of public vCard properties that should never be filtered
PUBLIC_VCARD_PROPERTIES = ['fn', 'n', 'email', 'tel']

# Mapping of vCard property names to enum values
VCARD_NAME_TO_ENUM = {
    'fn': VCardProperty.FN,
    'n': VCardProperty.N,
    'nickname': VCardProperty.NICKNAME,
    'photo': VCardProperty.PHOTO,
    'bday': VCardProperty.BDAY,
    'anniversary': VCardProperty.ANNIVERSARY,
    'gender': VCardProperty.GENDER,
    'adr': VCardProperty.ADR,
    'label': VCardProperty.LABEL,
    'tel': VCardProperty.TEL,
    'email': VCardProperty.EMAIL,
    'impp': VCardProperty.IMPP,
    'lang': VCardProperty.LANG,
    'tz': VCardProperty.TZ,
    'geo': VCardProperty.GEO,
    'title': VCardProperty.TITLE,
    'role': VCardProperty.ROLE,
    'logo': VCardProperty.LOGO,
    'org': VCardProperty.ORG,
    'member': VCardProperty.MEMBER,
    'related': VCardProperty.RELATED,
    'categories': VCardProperty.CATEGORIES,
    'note': VCardProperty.NOTE,
    'prodid': VCardProperty.PRODID,
    'rev': VCardProperty.REV,
    'sound': VCardProperty.SOUND,
    'uid': VCardProperty.UID,
    'clientpidmap': VCardProperty.CLIENTPIDMAP,
    'url': VCardProperty.URL,
    'version': VCardProperty.VERSION,
    'key': VCardProperty.KEY,
    'caladruri': VCardProperty.CALADRURI,
    'caluri': VCardProperty.CALURI,
    'fburl': VCardProperty.FBURL,
    'kind': VCardProperty.KIND,
    'xml': VCardProperty.XML,
    'source': VCardProperty.SOURCE,
}


# Mapping of vCard property names to their value types
VCARD_PROPERTY_TYPES = {
    # List properties
    'email': VCardPropertyType.LIST,
    'tel': VCardPropertyType.LIST,
    'impp': VCardPropertyType.LIST,
    'member': VCardPropertyType.LIST,
    'related': VCardPropertyType.LIST,
    'categories': VCardPropertyType.LIST,
    'clientpidmap': VCardPropertyType.LIST,

    # Presence-only properties
    'photo': VCardPropertyType.PRESENCE,
    'logo': VCardPropertyType.PRESENCE,
    'sound': VCardPropertyType.PRESENCE,
    'key': VCardPropertyType.PRESENCE,

    # All other properties are single value by default
}
