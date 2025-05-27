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


# Mapping of privacy settings to vCard properties
PRIVACY_TO_VCARD_MAP = {
    'disallow_name': [VCardProperty.FN, VCardProperty.N, VCardProperty.NICKNAME],
    'disallow_email': [VCardProperty.EMAIL],
    'disallow_phone': [VCardProperty.TEL],
    'disallow_company': [VCardProperty.ORG, VCardProperty.LOGO],
    'disallow_title': [VCardProperty.TITLE, VCardProperty.ROLE],
    'disallow_photo': [VCardProperty.PHOTO],
    'disallow_birthday': [VCardProperty.BDAY, VCardProperty.ANNIVERSARY],
    'disallow_address': [VCardProperty.ADR, VCardProperty.LABEL],
}


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
