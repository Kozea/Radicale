# This file is part of Radicale Server - Calendar Server
# Copyright © 2012-2017 Guillaume Ayoub
# Copyright © 2017-2018 Unrud <unrud@outlook.com>
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

"""
Tests for Radicale.

"""

import base64
import logging
import sys
from io import BytesIO

import defusedxml.ElementTree as DefusedET

import radicale
from radicale import xmlutils

# Enable debug output
radicale.log.logger.setLevel(logging.DEBUG)


class BaseTest:
    """Base class for tests."""

    def request(self, method, path, data=None, login=None, **args):
        """Send a request."""
        for key in args:
            args[key.upper()] = args[key]
        if login:
            args["HTTP_AUTHORIZATION"] = "Basic " + base64.b64encode(
                login.encode()).decode()
        args["REQUEST_METHOD"] = method.upper()
        args["PATH_INFO"] = path
        if data:
            data = data.encode()
            args["wsgi.input"] = BytesIO(data)
            args["CONTENT_LENGTH"] = str(len(data))
        args["wsgi.errors"] = sys.stderr
        status = headers = None

        def start_response(status_, headers_):
            nonlocal status, headers
            status = status_
            headers = headers_
        answer = self.application(args, start_response)

        return (int(status.split()[0]), dict(headers),
                answer[0].decode() if answer else None)

    @staticmethod
    def parse_responses(text):
        xml = DefusedET.fromstring(text)
        assert xml.tag == xmlutils.make_clark("D:multistatus")
        path_responses = {}
        for response in xml.findall(xmlutils.make_clark("D:response")):
            href = response.find(xmlutils.make_clark("D:href"))
            assert href.text not in path_responses
            prop_respones = {}
            for propstat in response.findall(
                    xmlutils.make_clark("D:propstat")):
                status = propstat.find(xmlutils.make_clark("D:status"))
                assert status.text.startswith("HTTP/1.1 ")
                status_code = int(status.text.split(" ")[1])
                for element in propstat.findall(
                        "./%s/*" % xmlutils.make_clark("D:prop")):
                    human_tag = xmlutils.make_human_tag(element.tag)
                    assert human_tag not in prop_respones
                    prop_respones[human_tag] = (status_code, element)
            status = response.find(xmlutils.make_clark("D:status"))
            if status is not None:
                assert not prop_respones
                assert status.text.startswith("HTTP/1.1 ")
                status_code = int(status.text.split(" ")[1])
                path_responses[href.text] = status_code
            else:
                path_responses[href.text] = prop_respones
        return path_responses

    @staticmethod
    def _check_status(status, good_status, check=True):
        if check is True:
            assert status == good_status
        elif check is not False:
            assert status == check
        return status == good_status

    def get(self, path, check=True, **args):
        status, _, answer = self.request("GET", path, **args)
        self._check_status(status, 200, check)
        return status, answer

    def post(self, path, data=None, check=True, **args):
        status, _, answer = self.request("POST", path, data, **args)
        self._check_status(status, 200, check)
        return status, answer

    def put(self, path, data, check=True, **args):
        status, _, answer = self.request("PUT", path, data, **args)
        self._check_status(status, 201, check)
        return status, answer

    def propfind(self, path, data=None, check=True, **args):
        status, _, answer = self.request("PROPFIND", path, data, **args)
        if not self._check_status(status, 207, check):
            return status, None
        responses = self.parse_responses(answer)
        if args.get("HTTP_DEPTH", 0) == 0:
            assert len(responses) == 1 and path in responses
        return status, responses

    def proppatch(self, path, data=None, check=True, **args):
        status, _, answer = self.request("PROPPATCH", path, data, **args)
        if not self._check_status(status, 207, check):
            return status, None
        responses = self.parse_responses(answer)
        assert len(responses) == 1 and path in responses
        return status, responses

    def report(self, path, data, check=True, **args):
        status, _, answer = self.request("REPORT", path, data, **args)
        if not self._check_status(status, 207, check):
            return status, None
        return status, self.parse_responses(answer)

    def delete(self, path, check=True, **args):
        status, _, answer = self.request("DELETE", path, **args)
        if not self._check_status(status, 200, check):
            return status, None
        responses = self.parse_responses(answer)
        assert len(responses) == 1 and path in responses
        return status, responses

    def mkcalendar(self, path, data=None, check=True, **args):
        status, _, answer = self.request("MKCALENDAR", path, data, **args)
        self._check_status(status, 201, check)
        return status, answer

    def mkcol(self, path, data=None, check=True, **args):
        status, _, _ = self.request("MKCOL", path, data, **args)
        self._check_status(status, 201, check)
        return status

    def create_addressbook(self, path, check=True, **args):
        return self.mkcol(path, """\
<?xml version="1.0" encoding="UTF-8" ?>
<create xmlns="DAV:" xmlns:CR="urn:ietf:params:xml:ns:carddav">
    <set>
        <prop>
            <resourcetype>
                <collection />
                <CR:addressbook />
            </resourcetype>
        </prop>
    </set>
</create>""", check=check, **args)
