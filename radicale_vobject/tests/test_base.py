# -*- coding: utf-8 -*-

from __future__ import print_function

import datetime
import dateutil
import os
import re
import sys
import unittest
import json

from dateutil.tz import tzutc
from dateutil.rrule import rrule, rruleset, WEEKLY, MONTHLY

from radicale_vobject import base, iCalendar
from radicale_vobject import icalendar

from radicale_vobject.base import __behaviorRegistry as behavior_registry
from radicale_vobject.base import ContentLine, parseLine, ParseError
from radicale_vobject.base import readComponents, textLineToContentLine

from radicale_vobject.change_tz import change_tz

from radicale_vobject.icalendar import MultiDateBehavior, PeriodBehavior, \
    RecurringComponent, utc
from radicale_vobject.icalendar import parseDtstart, stringToTextValues, \
    stringToPeriod, timedeltaToString

two_hours = datetime.timedelta(hours=2)


def get_test_filepath(path):
   """
   Helper function to get the filepath of test files.
   """
   return os.path.join(os.path.dirname(__file__), "test_files", path)


def get_test_file(path):
    """
    Helper function to open and read test files.
    """
    filepath = get_test_filepath(path)
    if sys.version_info[0] < 3:
        # On python 2, this library operates on bytes.
        f = open(filepath, 'r')
    else:
        # On python 3, it operates on unicode. We need to specify an encoding
        # for systems for which the preferred encoding isn't utf-8 (e.g windows)
        f = open(filepath, 'r', encoding='utf-8')
    text = f.read()
    f.close()
    return text


class TestCalendarSerializing(unittest.TestCase):
    """
    Test creating an iCalendar file
    """
    max_diff = None

    def test_scratchbuild(self):
        """
        CreateCalendar 2.0 format from scratch
        """
        test_cal = get_test_file("simple_2_0_test.ics")
        cal = base.newFromBehavior('vcalendar', '2.0')
        cal.add('vevent')
        cal.vevent.add('dtstart').value = datetime.datetime(2006, 5, 9)
        cal.vevent.add('description').value = "Test event"
        cal.vevent.add('created').value = \
            datetime.datetime(2006, 1, 1, 10,
                              tzinfo=dateutil.tz.tzical(
                                  get_test_filepath("timezones.ics")).get('US/Pacific'))
        cal.vevent.add('uid').value = "Not very random UID"
        cal.vevent.add('dtstamp').value = datetime.datetime(2017, 6, 26, 0, tzinfo=tzutc())

        # Note we're normalizing line endings, because no one got time for that.
        self.assertEqual(
            cal.serialize().replace('\r\n', '\n'),
            test_cal.replace('\r\n', '\n')
        )

    def test_unicode(self):
        """
        Test unicode characters
        """
        test_cal = get_test_file("utf8_test.ics")
        vevent = base.readOne(test_cal).vevent
        vevent2 = base.readOne(vevent.serialize())
        self.assertEqual(str(vevent), str(vevent2))

        self.assertEqual(
            vevent.summary.value,
            'The title こんにちはキティ'
        )

        if sys.version_info[0] < 3:
            test_cal = test_cal.decode('utf-8')
            vevent = base.readOne(test_cal).vevent
            vevent2 = base.readOne(vevent.serialize())
            self.assertEqual(str(vevent), str(vevent2))
            self.assertEqual(
                vevent.summary.value,
                u'The title こんにちはキティ'
            )

    def test_wrapping(self):
        """
        Should support input file with a long text field covering multiple lines
        """
        test_journal = get_test_file("journal.ics")
        vobj = base.readOne(test_journal)
        vjournal = base.readOne(vobj.serialize())
        self.assertTrue('Joe, Lisa, and Bob' in vjournal.description.value)
        self.assertTrue('Tuesday.\n2.' in vjournal.description.value)

    def test_multiline(self):
        """
        Multi-text serialization test
        """
        category = base.newFromBehavior('categories')
        category.value = ['Random category']
        self.assertEqual(
            category.serialize().strip(),
            "CATEGORIES:Random category"
        )

        category.value.append('Other category')
        self.assertEqual(
            category.serialize().strip(),
            "CATEGORIES:Random category,Other category"
        )

    def test_semicolon_separated(self):
        """
        Semi-colon separated multi-text serialization test
        """
        request_status = base.newFromBehavior('request-status')
        request_status.value = ['5.1', 'Service unavailable']
        self.assertEqual(
            request_status.serialize().strip(),
            "REQUEST-STATUS:5.1;Service unavailable"
        )

    @staticmethod
    def test_unicode_multiline():
        """
        Test multiline unicode characters
        """
        cal = iCalendar()
        cal.add('method').value = 'REQUEST'
        cal.add('vevent')
        cal.vevent.add('created').value = datetime.datetime.now()
        cal.vevent.add('summary').value = 'Классное событие'
        cal.vevent.add('description').value = ('Классное событие Классное событие Классное событие Классное событие '
                                               'Классное событие Классsdssdное событие')

        # json tries to encode as utf-8 and it would break if some chars could not be encoded
        json.dumps(cal.serialize())

    @staticmethod
    def test_ical_to_hcal():
        """
        Serializing iCalendar to hCalendar.

        Since Hcalendar is experimental and the behavior doesn't seem to want to load,
        This test will have to wait.


        tzs = dateutil.tz.tzical(get_test_filepath("timezones.ics"))
        cal = base.newFromBehavior('hcalendar')
        self.assertEqual(
            str(cal.behavior),
            "<class 'radicale_vobject.hcalendar.HCalendar'>"
        )
        cal.add('vevent')
        cal.vevent.add('summary').value = "this is a note"
        cal.vevent.add('url').value = "http://microformats.org/code/hcalendar/creator"
        cal.vevent.add('dtstart').value = datetime.date(2006,2,27)
        cal.vevent.add('location').value = "a place"
        cal.vevent.add('dtend').value = datetime.date(2006,2,27) + datetime.timedelta(days = 2)

        event2 = cal.add('vevent')
        event2.add('summary').value = "Another one"
        event2.add('description').value = "The greatest thing ever!"
        event2.add('dtstart').value = datetime.datetime(1998, 12, 17, 16, 42, tzinfo = tzs.get('US/Pacific'))
        event2.add('location').value = "somewhere else"
        event2.add('dtend').value = event2.dtstart.value + datetime.timedelta(days = 6)
        hcal = cal.serialize()
        """
        #self.assertEqual(
        #    str(hcal),
        #    """<span class="vevent">
        #           <a class="url" href="http://microformats.org/code/hcalendar/creator">
        #             <span class="summary">this is a note</span>:
        #              <abbr class="dtstart", title="20060227">Monday, February 27</abbr>
        #              - <abbr class="dtend", title="20060301">Tuesday, February 28</abbr>
        #              at <span class="location">a place</span>
        #           </a>
        #        </span>
        #        <span class="vevent">
        #           <span class="summary">Another one</span>:
        #           <abbr class="dtstart", title="19981217T164200-0800">Thursday, December 17, 16:42</abbr>
        #           - <abbr class="dtend", title="19981223T164200-0800">Wednesday, December 23, 16:42</abbr>
        #           at <span class="location">somewhere else</span>
        #           <div class="description">The greatest thing ever!</div>
        #        </span>
        #    """
        #)


class TestBehaviors(unittest.TestCase):
    """
    Test Behaviors
    """
    def test_general_behavior(self):
        """
        Tests for behavior registry, getting and creating a behavior.
        """
        # Check expected behavior registry.
        self.assertEqual(
            sorted(behavior_registry.keys()),
            ['', 'ACTION', 'ADR', 'AVAILABLE', 'BUSYTYPE', 'CALSCALE',
             'CATEGORIES', 'CLASS', 'COMMENT', 'COMPLETED', 'CONTACT',
             'CREATED', 'DAYLIGHT', 'DESCRIPTION', 'DTEND', 'DTSTAMP',
             'DTSTART', 'DUE', 'DURATION', 'EXDATE', 'EXRULE', 'FN', 'FREEBUSY',
             'LABEL', 'LAST-MODIFIED', 'LOCATION', 'METHOD', 'N', 'ORG',
             'PHOTO', 'PRODID', 'RDATE', 'RECURRENCE-ID', 'RELATED-TO',
             'REQUEST-STATUS', 'RESOURCES', 'REV', 'RRULE', 'STANDARD', 'STATUS',
             'SUMMARY', 'TRANSP', 'TRIGGER', 'UID', 'VALARM', 'VAVAILABILITY',
             'VCALENDAR', 'VCARD', 'VEVENT', 'VFREEBUSY', 'VJOURNAL',
             'VTIMEZONE', 'VTODO']
        )

        # test get_behavior
        behavior = base.getBehavior('VCALENDAR')
        self.assertEqual(
            str(behavior),
            "<class 'radicale_vobject.icalendar.VCalendar2_0'>"
        )
        self.assertTrue(behavior.isComponent)

        self.assertEqual(
            base.getBehavior("invalid_name"),
            None
        )
        # test for ContentLine (not a component)
        non_component_behavior = base.getBehavior('RDATE')
        self.assertFalse(non_component_behavior.isComponent)

    def test_MultiDateBehavior(self):
        """
        Test MultiDateBehavior
        """
        parseRDate = MultiDateBehavior.transformToNative
        self.assertEqual(
            str(parseRDate(textLineToContentLine("RDATE;VALUE=DATE:19970304,19970504,19970704,19970904"))),
            "<RDATE{'VALUE': ['DATE']}[datetime.date(1997, 3, 4), datetime.date(1997, 5, 4), datetime.date(1997, 7, 4), datetime.date(1997, 9, 4)]>"
        )
        self.assertEqual(
            str(parseRDate(textLineToContentLine("RDATE;VALUE=PERIOD:19960403T020000Z/19960403T040000Z,19960404T010000Z/PT3H"))),
            "<RDATE{'VALUE': ['PERIOD']}[(datetime.datetime(1996, 4, 3, 2, 0, tzinfo=tzutc()), datetime.datetime(1996, 4, 3, 4, 0, tzinfo=tzutc())), (datetime.datetime(1996, 4, 4, 1, 0, tzinfo=tzutc()), datetime.timedelta(0, 10800))]>"
        )

    def test_periodBehavior(self):
        """
        Test PeriodBehavior
        """
        line = ContentLine('test', [], '', isNative=True)
        line.behavior = PeriodBehavior
        line.value = [(datetime.datetime(2006, 2, 16, 10), two_hours)]

        self.assertEqual(
            line.transformFromNative().value,
            '20060216T100000/PT2H'
        )
        self.assertEqual(
            line.transformToNative().value,
            [(datetime.datetime(2006, 2, 16, 10, 0),
              datetime.timedelta(0, 7200))]
        )

        line.value.append((datetime.datetime(2006, 5, 16, 10), two_hours))

        self.assertEqual(
            line.serialize().strip(),
            'TEST:20060216T100000/PT2H,20060516T100000/PT2H'
        )


class TestVTodo(unittest.TestCase):
    """
    VTodo Tests
    """
    def test_vtodo(self):
        """
        Test VTodo
        """
        vtodo = get_test_file("vtodo.ics")
        obj = base.readOne(vtodo)
        obj.vtodo.add('completed')
        obj.vtodo.completed.value = datetime.datetime(2015,5,5,13,30)
        self.assertEqual(obj.vtodo.completed.serialize()[0:23],
                         'COMPLETED:20150505T1330')
        obj = base.readOne(obj.serialize())
        self.assertEqual(obj.vtodo.completed.value,
                         datetime.datetime(2015,5,5,13,30))


class TestVobject(unittest.TestCase):
    """
    VObject Tests
    """
    max_diff = None

    @classmethod
    def setUpClass(cls):
        """
        Method for setting up class fixture before running tests in the class.
        Fetches test file.
        """
        cls.simple_test_cal = get_test_file("simple_test.ics")

    def test_readComponents(self):
        """
        Test if reading components correctly
        """
        cal = next(readComponents(self.simple_test_cal))

        self.assertEqual(str(cal), "<VCALENDAR| [<VEVENT| [<SUMMARY{'BLAH': ['hi!']}Bastille Day Party>]>]>")
        self.assertEqual(str(cal.vevent.summary), "<SUMMARY{'BLAH': ['hi!']}Bastille Day Party>")

    def test_parseLine(self):
        """
        Test line parsing
        """
        self.assertEqual(parseLine("BLAH:"), ('BLAH', [], '', None))
        self.assertEqual(
            parseLine("RDATE:VALUE=DATE:19970304,19970504,19970704,19970904"),
            ('RDATE', [], 'VALUE=DATE:19970304,19970504,19970704,19970904', None)
        )
        self.assertEqual(
            parseLine('DESCRIPTION;ALTREP="http://www.wiz.org":The Fall 98 Wild Wizards Conference - - Las Vegas, NV, USA'),
            ('DESCRIPTION', [['ALTREP', 'http://www.wiz.org']], 'The Fall 98 Wild Wizards Conference - - Las Vegas, NV, USA', None)
        )
        self.assertEqual(
            parseLine("EMAIL;PREF;INTERNET:john@nowhere.com"),
            ('EMAIL', [['PREF'], ['INTERNET']], 'john@nowhere.com', None)
        )
        self.assertEqual(
            parseLine('EMAIL;TYPE="blah",hah;INTERNET="DIGI",DERIDOO:john@nowhere.com'),
            ('EMAIL', [['TYPE', 'blah', 'hah'], ['INTERNET', 'DIGI', 'DERIDOO']], 'john@nowhere.com', None)
        )
        self.assertEqual(
            parseLine('item1.ADR;type=HOME;type=pref:;;Reeperbahn 116;Hamburg;;20359;'),
            ('ADR', [['type', 'HOME'], ['type', 'pref']], ';;Reeperbahn 116;Hamburg;;20359;', 'item1')
        )
        self.assertRaises(ParseError, parseLine, ":")


class TestGeneralFileParsing(unittest.TestCase):
    """
    General tests for parsing ics files.
    """
    def test_readOne(self):
        """
        Test reading first component of ics
        """
        cal = get_test_file("silly_test.ics")
        silly = base.readOne(cal)
        self.assertEqual(
            str(silly),
            "<SILLYPROFILE| [<MORESTUFF{}this line is not folded, but in practice probably ought to be, as it is exceptionally long, and moreover demonstratively stupid>, <SILLYNAME{}name>, <STUFF{}foldedline>]>"
        )
        self.assertEqual(
            str(silly.stuff),
            "<STUFF{}foldedline>"
        )

    def test_importing(self):
        """
        Test importing ics
        """
        cal = get_test_file("standard_test.ics")
        c = base.readOne(cal, validate=True)
        self.assertEqual(
            str(c.vevent.valarm.trigger),
            "<TRIGGER{}-1 day, 0:00:00>"
        )

        self.assertEqual(
            str(c.vevent.dtstart.value),
            "2002-10-28 14:00:00-08:00"
        )
        self.assertTrue(
            isinstance(c.vevent.dtstart.value, datetime.datetime)
        )
        self.assertEqual(
            str(c.vevent.dtend.value),
            "2002-10-28 15:00:00-08:00"
        )
        self.assertTrue(
            isinstance(c.vevent.dtend.value, datetime.datetime)
        )
        self.assertEqual(
            c.vevent.dtstamp.value,
            datetime.datetime(2002, 10, 28, 1, 17, 6, tzinfo=tzutc())
        )

        vevent = c.vevent.transformFromNative()
        self.assertEqual(
            str(vevent.rrule),
            "<RRULE{}FREQ=Weekly;COUNT=10>"
        )

    def test_bad_stream(self):
        """
        Test bad ics stream
        """
        cal = get_test_file("badstream.ics")
        self.assertRaises(ParseError, base.readOne, cal)

    def test_bad_line(self):
        """
        Test bad line in ics file
        """
        cal = get_test_file("badline.ics")
        self.assertRaises(ParseError, base.readOne, cal)

        newcal = base.readOne(cal, ignoreUnreadable=True)
        self.assertEqual(
            str(newcal.vevent.x_bad_underscore),
            '<X-BAD-UNDERSCORE{}TRUE>'
        )

    def test_parseParams(self):
        """
        Test parsing parameters
        """
        self.assertEqual(
            base.parseParams(';ALTREP="http://www.wiz.org"'),
            [['ALTREP', 'http://www.wiz.org']]
        )
        self.assertEqual(
            base.parseParams(';ALTREP="http://www.wiz.org;;",Blah,Foo;NEXT=Nope;BAR'),
            [['ALTREP', 'http://www.wiz.org;;', 'Blah', 'Foo'],
             ['NEXT', 'Nope'], ['BAR']]
        )


class TestVcards(unittest.TestCase):
    """
    Test VCards
    """
    @classmethod
    def setUpClass(cls):
        """
        Method for setting up class fixture before running tests in the class.
        Fetches test file.
        """
        cls.test_file = get_test_file("vcard_with_groups.ics")
        cls.card = base.readOne(cls.test_file)

    def test_vcard_creation(self):
        """
        Test creating a vCard
        """
        vcard = base.newFromBehavior('vcard', '3.0')
        self.assertEqual(
            str(vcard),
            "<VCARD| []>"
        )

    def test_default_behavior(self):
        """
        Default behavior test.
        """
        card = self.card
        self.assertEqual(
            base.getBehavior('note'),
            None
        )
        self.assertEqual(
            str(card.note.value),
            "The Mayor of the great city of Goerlitz in the great country of Germany.\nNext line."
        )

    def test_with_groups(self):
        """
        vCard groups test
        """
        card = self.card
        self.assertEqual(
            str(card.group),
            'home'
        )
        self.assertEqual(
            str(card.tel.group),
            'home'
        )

        card.group = card.tel.group = 'new'
        self.assertEqual(
            str(card.tel.serialize().strip()),
            'new.TEL;TYPE=fax,voice,msg:+49 3581 123456'
        )
        self.assertEqual(
            str(card.serialize().splitlines()[0]),
            'new.BEGIN:VCARD'
        )


    def test_vcard_3_parsing(self):
        """
        VCARD 3.0 parse test
        """
        test_file = get_test_file("simple_3_0_test.ics")
        card = base.readOne(test_file)
        # value not rendering correctly?
        #self.assertEqual(
        #    card.adr.value,
        #    "<Address: Haight Street 512;\nEscape, Test\nNovosibirsk,  80214\nGnuland>"
        #)
        self.assertEqual(
            card.org.value,
            ["University of Novosibirsk", "Department of Octopus Parthenogenesis"]
        )

        for _ in range(3):
            new_card = base.readOne(card.serialize())
            self.assertEqual(new_card.org.value, card.org.value)
            card = new_card


class TestIcalendar(unittest.TestCase):
    """
    Tests for icalendar.py
    """
    max_diff = None
    def test_parseDTStart(self):
        """
        Should take a content line and return a datetime object.
        """
        self.assertEqual(
            parseDtstart(textLineToContentLine("DTSTART:20060509T000000")),
            datetime.datetime(2006, 5, 9, 0, 0)
        )

    def test_regexes(self):
        """
        Test regex patterns
        """
        self.assertEqual(
            re.findall(base.patterns['name'], '12foo-bar:yay'),
            ['12foo-bar', 'yay']
        )
        self.assertEqual(
            re.findall(base.patterns['safe_char'], 'a;b"*,cd'),
            ['a', 'b', '*', 'c', 'd']
        )
        self.assertEqual(
            re.findall(base.patterns['qsafe_char'], 'a;b"*,cd'),
            ['a', ';', 'b', '*', ',', 'c', 'd']
        )
        self.assertEqual(
            re.findall(base.patterns['param_value'],
                       '"quoted";not-quoted;start"after-illegal-quote',
                       re.VERBOSE),
            ['"quoted"', '', 'not-quoted', '', 'start', '',
             'after-illegal-quote', '']
        )
        match = base.line_re.match('TEST;ALTREP="http://www.wiz.org":value:;"')
        self.assertEqual(
            match.group('value'),
            'value:;"'
        )
        self.assertEqual(
            match.group('name'),
            'TEST'
        )
        self.assertEqual(
            match.group('params'),
            ';ALTREP="http://www.wiz.org"'
        )

    def test_stringToTextValues(self):
        """
        Test string lists
        """
        self.assertEqual(
            stringToTextValues(''),
            ['']
        )
        self.assertEqual(
            stringToTextValues('abcd,efgh'),
            ['abcd', 'efgh']
        )

    def test_stringToPeriod(self):
        """
        Test datetime strings
        """
        self.assertEqual(
            stringToPeriod("19970101T180000Z/19970102T070000Z"),
            (datetime.datetime(1997, 1, 1, 18, 0, tzinfo=tzutc()),
             datetime.datetime(1997, 1, 2, 7, 0, tzinfo=tzutc()))
        )
        self.assertEqual(
            stringToPeriod("19970101T180000Z/PT1H"),
            (datetime.datetime(1997, 1, 1, 18, 0, tzinfo=tzutc()),
             datetime.timedelta(0, 3600))
        )

    def test_timedeltaToString(self):
        """
        Test timedelta strings
        """
        self.assertEqual(
            timedeltaToString(two_hours),
            'PT2H'
        )
        self.assertEqual(
            timedeltaToString(datetime.timedelta(minutes=20)),
            'PT20M'
        )

    def test_vtimezone_creation(self):
        """
        Test timezones
        """
        tzs = dateutil.tz.tzical(get_test_filepath("timezones.ics"))
        pacific = icalendar.TimezoneComponent(tzs.get('US/Pacific'))
        self.assertEqual(
            str(pacific),
            "<VTIMEZONE | <TZID{}US/Pacific>>"
        )
        santiago = icalendar.TimezoneComponent(tzs.get('Santiago'))
        self.assertEqual(
            str(santiago),
            "<VTIMEZONE | <TZID{}Santiago>>"
        )
        for year in range(2001, 2010):
            for month in (2, 9):
                dt = datetime.datetime(year, month, 15,
                                       tzinfo=tzs.get('Santiago'))
                self.assertTrue(dt.replace(tzinfo=tzs.get('Santiago')), dt)

    @staticmethod
    def test_timezone_serializing():
        """
        Serializing with timezones test
        """
        tzs = dateutil.tz.tzical(get_test_filepath("timezones.ics"))
        pacific = tzs.get('US/Pacific')
        cal = base.Component('VCALENDAR')
        cal.setBehavior(icalendar.VCalendar2_0)
        ev = cal.add('vevent')
        ev.add('dtstart').value = datetime.datetime(2005, 10, 12, 9,
                                                    tzinfo=pacific)
        evruleset = rruleset()
        evruleset.rrule(rrule(WEEKLY, interval=2, byweekday=[2,4],
                              until=datetime.datetime(2005, 12, 15, 9)))
        evruleset.rrule(rrule(MONTHLY, bymonthday=[-1,-5]))
        evruleset.exdate(datetime.datetime(2005, 10, 14, 9, tzinfo=pacific))
        ev.rruleset = evruleset
        ev.add('duration').value = datetime.timedelta(hours=1)

        apple = tzs.get('America/Montreal')
        ev.dtstart.value = datetime.datetime(2005, 10, 12, 9, tzinfo=apple)

    def test_pytz_timezone_serializing(self):
        """
        Serializing with timezones from pytz test
        """
        try:
            import pytz
        except ImportError:
            return self.skipTest("pytz not installed")  # NOQA

        # Avoid conflicting cached tzinfo from other tests
        def unregister_tzid(tzid):
            """Clear tzid from icalendar TZID registry"""
            if icalendar.getTzid(tzid, False):
                icalendar.registerTzid(tzid, None)

        unregister_tzid('US/Eastern')
        eastern = pytz.timezone('US/Eastern')
        cal = base.Component('VCALENDAR')
        cal.setBehavior(icalendar.VCalendar2_0)
        ev = cal.add('vevent')
        ev.add('dtstart').value = eastern.localize(
            datetime.datetime(2008, 10, 12, 9))
        serialized = cal.serialize()

        expected_vtimezone = get_test_file("tz_us_eastern.ics")
        self.assertIn(
            expected_vtimezone.replace('\r\n', '\n'),
            serialized.replace('\r\n', '\n')
        )

        # Exhaustively test all zones (just looking for no errors)
        for tzname in pytz.all_timezones:
            unregister_tzid(tzname)
            tz = icalendar.TimezoneComponent(tzinfo=pytz.timezone(tzname))
            tz.serialize()

    def test_freeBusy(self):
        """
        Test freebusy components
        """
        test_cal = get_test_file("freebusy.ics")

        vfb = base.newFromBehavior('VFREEBUSY')
        vfb.add('uid').value = 'test'
        vfb.add('dtstamp').value = datetime.datetime(2006, 2, 15, 0, tzinfo=utc)
        vfb.add('dtstart').value = datetime.datetime(2006, 2, 16, 1, tzinfo=utc)
        vfb.add('dtend').value   = vfb.dtstart.value + two_hours
        vfb.add('freebusy').value = [(vfb.dtstart.value, two_hours / 2)]
        vfb.add('freebusy').value = [(vfb.dtstart.value, vfb.dtend.value)]

        self.assertEqual(
            vfb.serialize().replace('\r\n', '\n'),
            test_cal.replace('\r\n', '\n')
        )

    def test_availablity(self):
        """
        Test availability components
        """
        test_cal = get_test_file("availablity.ics")

        vcal = base.newFromBehavior('VAVAILABILITY')
        vcal.add('uid').value = 'test'
        vcal.add('dtstamp').value = datetime.datetime(2006, 2, 15, 0, tzinfo=utc)
        vcal.add('dtstart').value = datetime.datetime(2006, 2, 16, 0, tzinfo=utc)
        vcal.add('dtend').value   = datetime.datetime(2006, 2, 17, 0, tzinfo=utc)
        vcal.add('busytype').value = "BUSY"

        av = base.newFromBehavior('AVAILABLE')
        av.add('uid').value = 'test1'
        av.add('dtstamp').value = datetime.datetime(2006, 2, 15, 0, tzinfo=utc)
        av.add('dtstart').value = datetime.datetime(2006, 2, 16, 9, tzinfo=utc)
        av.add('dtend').value   = datetime.datetime(2006, 2, 16, 12, tzinfo=utc)
        av.add('summary').value = "Available in the morning"

        vcal.add(av)

        self.assertEqual(
            vcal.serialize().replace('\r\n', '\n'),
            test_cal.replace('\r\n', '\n')
        )

    def test_recurrence(self):
        """
        Ensure date valued UNTILs in rrules are in a reasonable timezone,
        and include that day (12/28 in this test)
        """
        test_file = get_test_file("recurrence.ics")
        cal = base.readOne(test_file)
        dates = list(cal.vevent.getrruleset())
        self.assertEqual(
            dates[0],
            datetime.datetime(2006, 1, 26, 23, 0, tzinfo=tzutc())
        )
        self.assertEqual(
            dates[1],
            datetime.datetime(2006, 2, 23, 23, 0, tzinfo=tzutc())
        )
        self.assertEqual(
            dates[-1],
            datetime.datetime(2006, 12, 28, 23, 0, tzinfo=tzutc())
        )

    def test_recurring_component(self):
        """
        Test recurring events
        """
        vevent = RecurringComponent(name='VEVENT')

        # init
        self.assertTrue(vevent.isNative)

        # rruleset should be None at this point.
        # No rules have been passed or created.
        self.assertEqual(vevent.rruleset, None)

        # Now add start and rule for recurring event
        vevent.add('dtstart').value = datetime.datetime(2005, 1, 19, 9)
        vevent.add('rrule').value =u"FREQ=WEEKLY;COUNT=2;INTERVAL=2;BYDAY=TU,TH"
        self.assertEqual(
            list(vevent.rruleset),
            [datetime.datetime(2005, 1, 20, 9, 0), datetime.datetime(2005, 2, 1, 9, 0)]
        )
        self.assertEqual(
            list(vevent.getrruleset(addRDate=True)),
            [datetime.datetime(2005, 1, 19, 9, 0), datetime.datetime(2005, 1, 20, 9, 0)]
        )

        # Also note that dateutil will expand all-day events (datetime.date values)
        # to datetime.datetime value with time 0 and no timezone.
        vevent.dtstart.value = datetime.date(2005,3,18)
        self.assertEqual(
            list(vevent.rruleset),
            [datetime.datetime(2005, 3, 29, 0, 0), datetime.datetime(2005, 3, 31, 0, 0)]
        )
        self.assertEqual(
            list(vevent.getrruleset(True)),
            [datetime.datetime(2005, 3, 18, 0, 0), datetime.datetime(2005, 3, 29, 0, 0)]
        )

    def test_recurrence_without_tz(self):
        """
        Test recurring vevent missing any time zone definitions.
        """
        test_file = get_test_file("recurrence-without-tz.ics")
        cal = base.readOne(test_file)
        dates = list(cal.vevent.getrruleset())
        self.assertEqual(dates[0], datetime.datetime(2013, 1, 17, 0, 0))
        self.assertEqual(dates[1], datetime.datetime(2013, 1, 24, 0, 0))
        self.assertEqual(dates[-1], datetime.datetime(2013, 3, 28, 0, 0))

    def test_recurrence_offset_naive(self):
        """
        Ensure recurring vevent missing some time zone definitions is
        parsing. See isseu #75.
        """
        test_file = get_test_file("recurrence-offset-naive.ics")
        cal = base.readOne(test_file)
        dates = list(cal.vevent.getrruleset())
        self.assertEqual(dates[0], datetime.datetime(2013, 1, 17, 0, 0))
        self.assertEqual(dates[1], datetime.datetime(2013, 1, 24, 0, 0))
        self.assertEqual(dates[-1], datetime.datetime(2013, 3, 28, 0, 0))


class TestChangeTZ(unittest.TestCase):
    """
    Tests for change_tz.change_tz
    """
    class StubCal(object):
        class StubEvent(object):
            class Node(object):
                def __init__(self, value):
                    self.value = value

            def __init__(self, dtstart, dtend):
                self.dtstart = self.Node(dtstart)
                self.dtend = self.Node(dtend)

        def __init__(self, dates):
            """
            dates is a list of tuples (dtstart, dtend)
            """
            self.vevent_list = [self.StubEvent(*d) for d in dates]

    def test_change_tz(self):
        """
        Change the timezones of events in a component to a different
        timezone
        """

        # Setup - create a stub vevent list
        old_tz = dateutil.tz.gettz('UTC')  # 0:00
        new_tz = dateutil.tz.gettz('America/Chicago')  # -5:00

        dates = [
            (datetime.datetime(1999, 12, 31, 23, 59, 59, 0, tzinfo=old_tz),
             datetime.datetime(2000, 1, 1, 0, 0, 0, 0, tzinfo=old_tz)),
            (datetime.datetime(2010, 12, 31, 23, 59, 59, 0, tzinfo=old_tz),
             datetime.datetime(2011, 1, 2, 3, 0, 0, 0, tzinfo=old_tz))]

        cal = self.StubCal(dates)

        # Exercise - change the timezone
        change_tz(cal, new_tz, dateutil.tz.gettz('UTC'))

        # Test - that the tzs were converted correctly
        expected_new_dates = [
            (datetime.datetime(1999, 12, 31, 17, 59, 59, 0, tzinfo=new_tz),
             datetime.datetime(1999, 12, 31, 18, 0, 0, 0, tzinfo=new_tz)),
            (datetime.datetime(2010, 12, 31, 17, 59, 59, 0, tzinfo=new_tz),
             datetime.datetime(2011, 1, 1, 21, 0, 0, 0, tzinfo=new_tz))]

        for vevent, expected_datepair in zip(cal.vevent_list,
                                             expected_new_dates):
            self.assertEqual(vevent.dtstart.value, expected_datepair[0])
            self.assertEqual(vevent.dtend.value, expected_datepair[1])

    def test_change_tz_utc_only(self):
        """
        Change any UTC timezones of events in a component to a different
        timezone
        """

        # Setup - create a stub vevent list
        utc_tz = dateutil.tz.gettz('UTC')  # 0:00
        non_utc_tz = dateutil.tz.gettz('America/Santiago')  # -4:00
        new_tz = dateutil.tz.gettz('America/Chicago')  # -5:00

        dates = [
            (datetime.datetime(1999, 12, 31, 23, 59, 59, 0, tzinfo=utc_tz),
             datetime.datetime(2000, 1, 1, 0, 0, 0, 0, tzinfo=non_utc_tz))]

        cal = self.StubCal(dates)

        # Exercise - change the timezone passing utc_only=True
        change_tz(cal, new_tz, dateutil.tz.gettz('UTC'), utc_only=True)

        # Test - that only the utc item has changed
        expected_new_dates = [
            (datetime.datetime(1999, 12, 31, 17, 59, 59, 0, tzinfo=new_tz),
             dates[0][1])]

        for vevent, expected_datepair in zip(cal.vevent_list,
                                             expected_new_dates):
            self.assertEqual(vevent.dtstart.value, expected_datepair[0])
            self.assertEqual(vevent.dtend.value, expected_datepair[1])

    def test_change_tz_default(self):
        """
        Change the timezones of events in a component to a different
        timezone, passing a default timezone that is assumed when the events
        don't have one
        """

        # Setup - create a stub vevent list
        new_tz = dateutil.tz.gettz('America/Chicago')  # -5:00

        dates = [
            (datetime.datetime(1999, 12, 31, 23, 59, 59, 0, tzinfo=None),
             datetime.datetime(2000, 1, 1, 0, 0, 0, 0, tzinfo=None))]

        cal = self.StubCal(dates)

        # Exercise - change the timezone
        change_tz(cal, new_tz, dateutil.tz.gettz('UTC'))

        # Test - that the tzs were converted correctly
        expected_new_dates = [
            (datetime.datetime(1999, 12, 31, 17, 59, 59, 0, tzinfo=new_tz),
             datetime.datetime(1999, 12, 31, 18, 0, 0, 0, tzinfo=new_tz))]

        for vevent, expected_datepair in zip(cal.vevent_list,
                                             expected_new_dates):
            self.assertEqual(vevent.dtstart.value, expected_datepair[0])
            self.assertEqual(vevent.dtend.value, expected_datepair[1])


if __name__ == '__main__':
    unittest.main()
