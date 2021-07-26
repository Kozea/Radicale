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
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple, Union

import defusedxml.ElementTree as DefusedET

import radicale
from radicale import app, config, xmlutils

RESPONSES = Dict[str, Union[int, Dict[str, Tuple[int, ET.Element]]]]

# Enable debug output
radicale.log.logger.setLevel(logging.DEBUG)


class BaseTest:
    """Base class for tests."""

    colpath: str
    configuration: config.Configuration
    application: app.Application

    def setup(self) -> None:
        self.configuration = config.load()
        self.colpath = tempfile.mkdtemp()
        self.configuration.update({
            "storage": {"filesystem_folder": self.colpath,
                        # Disable syncing to disk for better performance
                        "_filesystem_fsync": "False"},
            # Set incorrect authentication delay to a short duration
            "auth": {"delay": "0.001"}}, "test", privileged=True)
        self.application = app.Application(self.configuration)

    def teardown(self) -> None:
        shutil.rmtree(self.colpath)

    def request(self, method: str, path: str, data: Optional[str] = None,
                **kwargs) -> Tuple[int, Dict[str, str], str]:
        """Send a request."""
        login = kwargs.pop("login", None)
        if login is not None and not isinstance(login, str):
            raise TypeError("login argument must be %r, not %r" %
                            (str, type(login)))
        environ: Dict[str, Any] = {k.upper(): v for k, v in kwargs.items()}
        for k, v in environ.items():
            if not isinstance(v, str):
                raise TypeError("type of %r is %r, expected %r" %
                                (k, type(v), str))
        encoding: str = self.configuration.get("encoding", "request")
        if login:
            environ["HTTP_AUTHORIZATION"] = "Basic " + base64.b64encode(
                    login.encode(encoding)).decode()
        environ["REQUEST_METHOD"] = method.upper()
        environ["PATH_INFO"] = path
        if data:
            data_bytes = data.encode(encoding)
            environ["wsgi.input"] = BytesIO(data_bytes)
            environ["CONTENT_LENGTH"] = str(len(data_bytes))
        environ["wsgi.errors"] = sys.stderr
        status = headers = None

        def start_response(status_: str, headers_: List[Tuple[str, str]]
                           ) -> None:
            nonlocal status, headers
            status = status_
            headers = headers_
        answers = list(self.application(environ, start_response))
        assert status is not None and headers is not None

        return (int(status.split()[0]), dict(headers),
                answers[0].decode() if answers else "")

    @staticmethod
    def parse_responses(text: str) -> RESPONSES:
        xml = DefusedET.fromstring(text)
        assert xml.tag == xmlutils.make_clark("D:multistatus")
        path_responses: Dict[str, Union[
            int, Dict[str, Tuple[int, ET.Element]]]] = {}
        for response in xml.findall(xmlutils.make_clark("D:response")):
            href = response.find(xmlutils.make_clark("D:href"))
            assert href.text not in path_responses
            prop_respones: Dict[str, Tuple[int, ET.Element]] = {}
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
    def _check_status(status: int, good_status: int,
                      check: Union[bool, int] = True) -> bool:
        if check is not False:
            expected = good_status if check is True else check
            assert status == expected, "%d != %d" % (status, expected)
        return status == good_status

    def get(self, path: str, check: Union[bool, int] = True, **kwargs
            ) -> Tuple[int, str]:
        assert "data" not in kwargs
        status, _, answer = self.request("GET", path, **kwargs)
        self._check_status(status, 200, check)
        return status, answer

    def post(self, path: str, data: str = None, check: Union[bool, int] = True,
             **kwargs) -> Tuple[int, str]:
        status, _, answer = self.request("POST", path, data, **kwargs)
        self._check_status(status, 200, check)
        return status, answer

    def put(self, path: str, data: str, check: Union[bool, int] = True,
            **kwargs) -> Tuple[int, str]:
        status, _, answer = self.request("PUT", path, data, **kwargs)
        self._check_status(status, 201, check)
        return status, answer

    def propfind(self, path: str, data: Optional[str] = None,
                 check: Union[bool, int] = True, **kwargs
                 ) -> Tuple[int, RESPONSES]:
        status, _, answer = self.request("PROPFIND", path, data, **kwargs)
        if not self._check_status(status, 207, check):
            return status, {}
        assert answer is not None
        responses = self.parse_responses(answer)
        if kwargs.get("HTTP_DEPTH", "0") == "0":
            assert len(responses) == 1 and path in responses
        return status, responses

    def proppatch(self, path: str, data: Optional[str] = None,
                  check: Union[bool, int] = True, **kwargs
                  ) -> Tuple[int, RESPONSES]:
        status, _, answer = self.request("PROPPATCH", path, data, **kwargs)
        if not self._check_status(status, 207, check):
            return status, {}
        assert answer is not None
        responses = self.parse_responses(answer)
        assert len(responses) == 1 and path in responses
        return status, responses

    def report(self, path: str, data: str, check: Union[bool, int] = True,
               **kwargs) -> Tuple[int, RESPONSES]:
        status, _, answer = self.request("REPORT", path, data, **kwargs)
        if not self._check_status(status, 207, check):
            return status, {}
        assert answer is not None
        return status, self.parse_responses(answer)

    def delete(self, path: str, check: Union[bool, int] = True, **kwargs
               ) -> Tuple[int, RESPONSES]:
        assert "data" not in kwargs
        status, _, answer = self.request("DELETE", path, **kwargs)
        if not self._check_status(status, 200, check):
            return status, {}
        assert answer is not None
        responses = self.parse_responses(answer)
        assert len(responses) == 1 and path in responses
        return status, responses

    def mkcalendar(self, path: str, data: Optional[str] = None,
                   check: Union[bool, int] = True, **kwargs
                   ) -> Tuple[int, str]:
        status, _, answer = self.request("MKCALENDAR", path, data, **kwargs)
        self._check_status(status, 201, check)
        return status, answer

    def mkcol(self, path: str, data: Optional[str] = None,
              check: Union[bool, int] = True, **kwargs) -> int:
        status, _, _ = self.request("MKCOL", path, data, **kwargs)
        self._check_status(status, 201, check)
        return status

    def create_addressbook(self, path: str, check: Union[bool, int] = True,
                           **kwargs) -> int:
        assert "data" not in kwargs
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
</create>""", check=check, **kwargs)
