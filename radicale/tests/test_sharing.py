# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026-2026 Peter Bieringer <pb@bieringer.de>
# Copyright © 2026-2026 Max Berger <max@berger.name>
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
Radicale tests related to sharing.

"""

import datetime
import json
import logging
import os
import pytest
import re
import sys
import tempfile
from typing import Dict, Sequence, Tuple, Union

from radicale import pathutils, sharing, xmlutils
from radicale.tests import BaseTest
from radicale.tests.helpers import get_file_content


class TestSharingApiSanity(BaseTest):
    """Tests with sharing."""

    htpasswd_file_path: str

    # Setup
    def setup_method(self) -> None:
        BaseTest.setup_method(self)
        self.htpasswd_file_path = os.path.join(self.colpath, ".htpasswd")
        encoding: str = self.configuration.get("encoding", "stock")
        htpasswd = ["owner:ownerpw", "user:userpw",
                    "owner1:owner1pw", "user1:user1pw",
                    "us😀er:user😀pw",
                    "owner2:owner2pw", "user2:user2pw"]
        htpasswd_content = "\n".join(htpasswd)
        with open(self.htpasswd_file_path, "w", encoding=encoding) as f:
            f.write(htpasswd_content)

    # Helper functions
    def _sharing_api(self, sharing_type: str, action: str, check: int, login: Union[str, None], data: str, content_type: str, accept: Union[str, None], prefix: Union[str, None] = None) -> Tuple[int, Dict[str, str], str]:
        path_base = "/.sharing/v1/" + sharing_type + "/"
        if prefix is not None:
            path_base = prefix + path_base
            _, headers, answer = self.request("POST", path_base + action, check=check, login=login, data=data, content_type=content_type, accept=accept, x_forwarded_for="127.0.0.2")
        else:
            _, headers, answer = self.request("POST", path_base + action, check=check, login=login, data=data, content_type=content_type, accept=accept)
        logging.info("received answer:\n%s", "\n".join(answer.splitlines()))
        return _, headers, answer

    def _sharing_api_form(self, sharing_type: str, action: str, check: int, login: Union[str, None], form_array: Sequence[str], accept: Union[str, None] = None, prefix: Union[str, None] = None) -> Tuple[int, Dict[str, str], str]:
        data = "&".join(form_array)
        content_type = "application/x-www-form-urlencoded"
        if accept is None:
            accept = "text/plain"
        _, headers, answer = self._sharing_api(sharing_type, action, check, login, data, content_type, accept, prefix=prefix)
        return _, headers, answer

    def _sharing_api_json(self, sharing_type: str, action: str, check: int, login: Union[str, None], json_dict: dict, accept: Union[str, None] = None, prefix: Union[str, None] = None) -> Tuple[int, Dict[str, str], str]:
        data = json.dumps(json_dict)
        content_type = "application/json"
        if accept is None:
            accept = "application/json"
        _, headers, answer = self._sharing_api(sharing_type, action, check, login, data, content_type, accept, prefix=prefix)
        return _, headers, answer

    def _propfind_allprop(self, path: str, login: str = "", prefix: Union[str, None] = None) -> dict:
        propfind_allprop = get_file_content("allprop.xml")
        if prefix is not None:
            path = prefix + path
            _, responses = self.propfind(path=path, data=propfind_allprop, login=login, x_forwarded_for="127.0.0.2")
        else:
            _, responses = self.propfind(path=path, data=propfind_allprop, login=login)
        logging.info("response: %r", responses)
        response = responses[path]
        assert not isinstance(response, int)
        return response

    def _propfind_privileges(self, path: str, login) -> list[str]:
        response = self._propfind_allprop(path, login)
        status, prop = response["D:current-user-privilege-set"]
        logging.debug("prop: %r", prop)
        privileges = prop.findall(xmlutils.make_clark("D:privilege"))
        assert len(privileges) >= 1
        privileges_list = [xmlutils.make_human_tag(privilege.findall("*")[0].tag) for privilege in privileges]
        return privileges_list

    def _propfind_calendar_color(self, path, login) -> Union[str, None]:
        propfind_calendar_color = get_file_content("propfind_calendar_color.xml")
        _, responses = self.propfind(path=path, data=propfind_calendar_color, login=login)
        logging.info("response: %r", responses)
        response = responses[path]
        assert not isinstance(response, int)
        status, prop = response["ICAL:calendar-color"]
        logging.debug("ICAL:calendar-color: %r", prop.text)
        assert status == 200
        return prop.text

    def _proppatch_calendar_color(self, path, login, color) -> None:
        _, responses = self.proppatch(path=path, data="""\
<?xml version="1.0" encoding="utf-8"?>
<D:propertyupdate xmlns:D="DAV:">
<D:set>
<D:prop>
  <I:calendar-color xmlns:I="http://apple.com/ns/ical/">""" + color + """</I:calendar-color>
</D:prop>
</D:set>
</D:propertyupdate>""", login=login)
        logging.info("response: %r", responses)
        response = responses[path]
        assert not isinstance(response, int) and len(response) == 1
        status, prop = response["ICAL:calendar-color"]
        assert status == 200 and not prop.text
        return

    def _proppatch_calendar_color_remove(self, path, login) -> None:
        _, responses = self.proppatch(path=path, data="""\
<?xml version="1.0" encoding="utf-8"?>
<D:propertyupdate xmlns:D="DAV:">
<D:remove>
<D:prop>
  <I:calendar-color xmlns:I="http://apple.com/ns/ical/" />
</D:prop>
</D:remove>
</D:propertyupdate>""", login=login)
        logging.info("response: %r", responses)
        response = responses[path]
        assert not isinstance(response, int) and len(response) == 1
        status, prop = response["ICAL:calendar-color"]
        assert status == 200 and not prop.text
        return

    def _propfind_calendar_description(self, path, login):
        _, responses = self.propfind(path=path, data="""\
<?xml version="1.0" encoding="utf-8"?>
<D:propfind xmlns:D="DAV:">
  <D:prop>
    <C:calendar-description xmlns:C="urn:ietf:params:xml:ns:caldav" />
  </D:prop>
</D:propfind>""", login=login)
        logging.info("response: %r", responses)
        response = responses[path]
        assert not isinstance(response, int)
        status, prop = response["C:calendar-description"]
        logging.debug("C:calendar-description: %r", prop.text)
        assert status == 200
        return prop.text

    def _proppatch_calendar_description(self, path, login, description) -> None:
        _, responses = self.proppatch(path=path, data="""\
<?xml version="1.0" encoding="utf-8"?>
<D:propertyupdate xmlns:D="DAV:">
<D:set>
<D:prop>
  <C:calendar-description xmlns:C="urn:ietf:params:xml:ns:caldav">""" + description + """</C:calendar-description>
</D:prop>
</D:set>
</D:propertyupdate>""", login=login)
        logging.info("response: %r", responses)
        response = responses[path]
        assert not isinstance(response, int) and len(response) == 1
        status, prop = response["C:calendar-description"]
        assert status == 200 and not prop.text
        return

    def _proppatch_calendar_description_remove(self, path, login) -> None:
        _, responses = self.proppatch(path=path, data="""\
<?xml version="1.0" encoding="utf-8"?>
<D:propertyupdate xmlns:D="DAV:">
<D:remove>
<D:prop>
  <C:calendar-description xmlns:C="urn:ietf:params:xml:ns:caldav" />
</D:prop>
</D:remove>
</D:propertyupdate>""", login=login)
        logging.info("response: %r", responses)
        response = responses[path]
        assert not isinstance(response, int) and len(response) == 1
        status, prop = response["C:calendar-description"]
        assert status == 200 and not prop.text
        return

    # Test functions
    def test_sharing_api_base_csv_custom(self) -> None:
        self.database_path = os.path.join(self.colpath, "collection-db/test.csv")
        self.configure({"sharing": {
                                    "type": "csv",
                                    "database_path": self.database_path,
                                    "collection_by_map": "True",
                                    "collection_by_token": "False"}
                        })

    def test_sharing_api_base_no_auth_basic(self) -> None:
        """POST request at '/.sharing' without authentication."""
        # disabled
        for path in ["/.sharing", "/.sharing/"]:
            _, headers, _ = self.request("POST", path, check=404)

        path = "/.sharing/"

        # no database is active
        logging.info("\n*** check API hook base: map=True token=False")
        self.configure({"sharing": {
                                    "collection_by_map": "True",
                                    "collection_by_token": "False"}
                        })
        _, headers, _ = self.request("POST", path, check=404)

        logging.info("\n*** check API hook base: map=False token=True")
        self.configure({"sharing": {
                                    "collection_by_map": "False",
                                    "collection_by_token": "True"}
                        })
        _, headers, _ = self.request("POST", path, check=404)

        logging.info("\n*** check API hook base: map=True token=True")
        self.configure({"sharing": {
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"}
                        })
        _, headers, _ = self.request("POST", path, check=404)

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # no database is active
            logging.info("\n*** check API hook base: map=True token=False")
            self.configure({"sharing": {
                                        "collection_by_map": "True",
                                        "collection_by_token": "False"}
                            })
            _, headers, _ = self.request("POST", path, check=401)

            logging.info("\n*** check API hook base: map=False token=True")
            self.configure({"sharing": {
                                        "collection_by_map": "False",
                                        "collection_by_token": "True"}
                            })
            _, headers, _ = self.request("POST", path, check=401)

            logging.info("\n*** check API hook base: map=True token=True")
            self.configure({"sharing": {
                                        "collection_by_map": "True",
                                        "collection_by_token": "True"}
                            })
            _, headers, _ = self.request("POST", path, check=401)

    def test_sharing_api_base_no_auth_delay(self) -> None:
        delay = .3
        delay_min = delay * 0.9  # no random jitter during test
        delay_max = delay + 0.2  # no random jitter during test
        if sys.platform == "darwin":  # no reliable sleep times
            delay_max = delay_max * 1.5

        for path in ["/.sharing", "/.sharing/"]:
            time_begin = datetime.datetime.now()
            _, headers, _ = self.request("POST", path, check=404)
            time_end = datetime.datetime.now()
            time_delta = (time_end - time_begin).total_seconds()
            assert time_delta < delay_min  # 404 should have no delay

        path = "/.sharing/"

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # no database is active
            logging.info("\n*** check API hook base: map=True token=False (incl. delay)")
            self.configure({"sharing": {
                                        "collection_by_map": "True",
                                        "collection_by_token": "False"},
                            "auth": {"delay": delay}})
            time_begin = datetime.datetime.now()
            _, headers, _ = self.request("POST", path, check=401)
            time_end = datetime.datetime.now()
            time_delta = (time_end - time_begin).total_seconds()
            assert time_delta > delay_min
            assert time_delta < delay_max

    def test_sharing_api_base_with_auth(self) -> None:
        """POST request at '/.sharing' with authentication."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "rights": {"type": "owner_only"}})

        form_array: Sequence[str]
        json_dict: dict

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            for path in ["/.sharing/", "/.sharing/v9/"]:
                logging.info("\n*** check invalid API URI: %r", path)
                _, headers, _ = self.request("POST", path, check=404, login="owner:ownerpw")

            # path with valid API but no hook
            for path in ["/.sharing/v1/"]:
                logging.info("\n*** check valid API URI without hook: %r", path)
                _, headers, _ = self.request("POST", path, check=404, login="owner:ownerpw")

            # path with valid API and hook but not enabled "map"
            self.configure({"sharing": {
                                        "collection_by_map": "False",
                                        "collection_by_token": "True"}
                            })
            sharetype = "map"
            for action in sharing.API_HOOKS_V1:
                path = "/.sharing/v1/" + sharetype + "/" + action
                logging.info("\n*** check valid API URI hook (but not enabled): %r", path)
                _, headers, _ = self.request("POST", path, check=404, login="owner:ownerpw")

            # path with valid API and hook but not enabled "token"
            self.configure({"sharing": {
                                        "collection_by_map": "True",
                                        "collection_by_token": "False",
                                        "permit_create_map": "False",
                                        "permit_create_token": "False"}
                            })
            sharetype = "token"
            for action in sharing.API_HOOKS_V1:
                path = "/.sharing/v1/" + sharetype + "/" + action
                logging.info("\n*** check valid API URI hook (but not enabled): %r", path)
                _, headers, _ = self.request("POST", path, check=404, login="owner:ownerpw")

            # check info hook
            logging.info("\n*** check API hook: info/all (text)")
            form_array = []
            _, headers, answer = self._sharing_api_form("all", "info", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer
            assert "PermittedCreateCollectionByMap=False" in answer
            assert "PermittedCreateCollectionByToken=False" in answer
            assert "FeatureEnabledCollectionByMap=True" in answer
            assert "FeatureEnabledCollectionByToken=False" in answer

            logging.info("\n*** check API hook: info/all (json)")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("all", "info", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['FeatureEnabledCollectionByMap'] is True, f'FeatureEnabledCollectionByMap {db_type}'
            assert answer_dict['FeatureEnabledCollectionByToken'] is False, f'FeatureEnabledCollectionByToken {db_type}'
            assert answer_dict['PermittedCreateCollectionByMap'] is False, f'PermittedCreateCollectionByMap {db_type}'
            assert answer_dict['PermittedCreateCollectionByToken'] is False, f'PermittedCreateCollectionByToken {db_type}'

            logging.info("\n*** check API hook: info/map")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "info", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['FeatureEnabledCollectionByMap'] is True
            assert 'FeatureEnabledCollectionByToken' not in answer_dict
            assert 'PermittedCreateCollectionByToken' not in answer_dict

            logging.info("\n*** check API hook: info/token -> 404 (not enabled)")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("token", "info", check=404, login="owner:ownerpw", json_dict=json_dict)

            # path with valid API and hook and all enabled
            self.configure({"sharing": {
                                        "collection_by_map": "True",
                                        "collection_by_token": "True"}
                            })
            for sharetype in sharing.SHARE_TYPES:
                path = "/.sharing/v1/" + sharetype + "/" + action
                # invalid API
                logging.info("\n*** check hook -> 404 (invalid)")
                _, headers, _ = self.request("POST", path + "NA", check=404, login="owner:ownerpw")
                #  valid API
                logging.info("\n*** check hook -> 400 (valid but no data)")
                _, headers, _ = self.request("POST", path, check=400, login="owner:ownerpw")

            logging.info("\n*** check API hook: info/token -> 200")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("token", "info", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['FeatureEnabledCollectionByToken'] is True
            assert 'FeatureEnabledCollectionByMap' not in answer_dict
            assert 'PermittedCreateCollectionByMap' not in answer_dict

            # When turning on permission to create
            self.configure({"sharing": {
                                        "collection_by_map": "True",
                                        "collection_by_token": "True",
                                        "permit_create_map": "True",
                                        "permit_properties_overlay": "True",
                                        "permit_create_token": "True"}
                            })
            logging.info("\n*** check API hook: info/all")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("all", "info", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['FeatureEnabledCollectionByMap'] is True, f'FeatureEnabledCollectionByMap {db_type}'
            assert answer_dict['FeatureEnabledCollectionByToken'] is True, f'FeatureEnabledCollectionByToken {db_type}'
            assert answer_dict['PermittedCreateCollectionByMap'] is True, f'PermittedCreateCollectionByMap {db_type}'
            assert answer_dict['PermittedCreateCollectionByToken'] is True, f'PermittedCreateCollectionByToken {db_type}'
            assert answer_dict['SupportedConversions'] == list(sharing.CONVERSIONS_WHITELIST)
            assert answer_dict['PermittedPropertiesOverlay'] is True
            assert answer_dict['SupportedPropertiesOverlay'] == list(sharing.OVERLAY_PROPERTIES_WHITELIST)

            logging.info("\n*** check API hook: info/all (2)")
            self.configure({"sharing": {"permit_properties_overlay": "False"}})
            json_dict = {}
            _, headers, answer = self._sharing_api_json("all", "info", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['PermittedPropertiesOverlay'] is False

    def test_sharing_api_list_with_auth(self) -> None:
        """POST/list with authentication."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "true",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        form_array: Sequence[str]
        json_dict: dict

        self.mkcalendar("/owner/collectionL1/", login="owner:ownerpw")
        self.mkcalendar("/owner/collectionL2/", login="owner:ownerpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            action = "list"
            for sharing_type in sharing.SHARE_TYPES:
                logging.info("\n*** list (without form) -> should fail")
                path = "/.sharing/v1/" + sharing_type + "/" + action
                _, headers, _ = self.request("POST", path, check=400, login="owner:ownerpw")

                logging.info("\n*** list (form->csv)")
                form_array = []
                _, headers, answer = self._sharing_api_form(sharing_type, "list", check=200, login="owner:ownerpw", form_array=form_array)
                assert "Status='not-found'" in answer
                assert "Lines=0" in answer

                logging.info("\n*** list (json->text)")
                json_dict = {}
                _, headers, answer = self._sharing_api_json(sharing_type, "list", check=200, login="owner:ownerpw", json_dict=json_dict, accept="text/plain")
                assert "Status='not-found'" in answer
                assert "Lines=0" in answer

                logging.info("\n*** list (json->json)")
                json_dict = {}
                _, headers, answer = self._sharing_api_json(sharing_type, "list", check=200, login="owner:ownerpw", json_dict=json_dict)
                answer_dict = json.loads(answer)
                assert answer_dict['Status'] == "not-found"
                assert answer_dict['Lines'] == 0

            logging.info("\n*** create a token -> 200")
            form_array = ["PathMapped=/owner/collectionL1/"]
            _, headers, answer = self._sharing_api_form("token", "create", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer
            assert "PathOrToken='" in answer
            # extract token
            match = re.search("PathOrToken='(.+)'", answer)
            if match:
                token = match.group(1)
                logging.info("received token %r", token)
            else:
                assert False

            logging.info("\n*** create a map -> 200")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = "/owner/collectionL2/"
            json_dict['PathOrToken'] = "/user/collectionL2-shared-by-owner/"
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** list/all (form->csv)")
            form_array = []
            _, headers, answer = self._sharing_api_form("all", "list", check=200, login="owner:ownerpw", form_array=form_array, accept="text/csv")
            assert "Status=" not in answer
            assert "Line=" not in answer
            assert "ShareType" in answer
            assert "token" in answer
            assert "map" in answer

            logging.info("\n*** list/all (form->text)")
            form_array = []
            _, headers, answer = self._sharing_api_form("all", "list", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer
            assert "Lines=2" in answer
            assert "Fields=" in answer
            assert "Content[0]=" in answer
            assert "Content[1]=" in answer

            logging.info("\n*** delete token -> 200")
            form_array = ["PathOrToken=" + token]
            _, headers, answer = self._sharing_api_form("token", "delete", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer

            logging.info("\n*** delete share -> 200")
            form_array = []
            form_array.append("PathOrToken=/user/collectionL2-shared-by-owner/")
            form_array.append("PathMapped=/owner/collectionL2/")
            _, headers, answer = self._sharing_api_form("map", "delete", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer

    def test_sharing_api_token_basic(self) -> None:
        """share-by-token API tests."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        form_array: Sequence[str]
        json_dict: dict

        path_base1 = "/owner/collection1.ics/"
        path_base2 = "/owner/collection2.ics/"

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            logging.info("\n*** create token without PathMapped (form) -> 400")
            form_array = []
            _, headers, answer = self._sharing_api_form("token", "create", 400, login="owner:ownerpw", form_array=form_array)

            logging.info("\n*** create token without PathMapped (json) -> 400")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("token", "create", 400, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** create token#1 without existing collection (form->text) -> 404")
            form_array = ["PathMapped=" + path_base1]
            _, headers, answer = self._sharing_api_form("token", "create", check=404, login="owner:ownerpw", form_array=form_array)

            logging.info("\n*** create collection*")
            self.mkcalendar(path_base1, login="owner:ownerpw")
            self.mkcalendar(path_base2, login="owner:ownerpw")

            logging.info("\n*** create token#1 with existing collection (form->text) but no trailing / -> 400")
            form_array = ["PathMapped=" + path_base1.rstrip('/')]
            _, headers, answer = self._sharing_api_form("token", "create", check=400, login="owner:ownerpw", form_array=form_array)

            logging.info("\n*** create token#1 with existing collection (form->text) -> 200")
            form_array = ["PathMapped=" + path_base1]
            _, headers, answer = self._sharing_api_form("token", "create", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer
            assert "PathOrToken='" in answer
            # extract token
            match = re.search("PathOrToken='(.+)'", answer)
            if match:
                token1 = match.group(1)
                logging.info("received token %r", token1)
            else:
                assert False

            logging.info("\n*** create token#2 (json->text)")
            json_dict = {'PathMapped': path_base2}
            _, headers, answer = self._sharing_api_json("token", "create", check=200, login="owner:ownerpw", json_dict=json_dict, accept="text/plain")
            assert "Status='success'" in answer
            assert "Token=" in answer
            # extract token
            match = re.search("Token='(.+)'", answer)
            if match:
                token2 = match.group(1)
                logging.info("received token %r", token2)
            else:
                assert False

            logging.info("\n*** lookup token#1 (form->text)")
            form_array = ["PathOrToken=" + token1]
            _, headers, answer = self._sharing_api_form("token", "list", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer
            assert "Lines=1" in answer
            assert path_base1 in answer

            logging.info("\n*** lookup token#2 (json->text")
            json_dict = {'PathOrToken': token2}
            _, headers, answer = self._sharing_api_json("token", "list", check=200, login="owner:ownerpw", json_dict=json_dict, accept="text/plain")
            assert "Status='success'" in answer
            assert "Lines=1" in answer
            assert path_base2 in answer

            logging.info("\n*** lookup token#2 (json->json)")
            json_dict = {'PathOrToken': token2}
            _, headers, answer = self._sharing_api_json("token", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['PathMapped'] == path_base2

            logging.info("\n*** lookup tokens (form->text)")
            form_array = []
            _, headers, answer = self._sharing_api_form("token", "list", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer
            assert "Lines=2" in answer
            assert path_base1 in answer
            assert path_base2 in answer

            logging.info("\n*** lookup tokens (form->csv)")
            form_array = []
            _, headers, answer = self._sharing_api_form("token", "list", check=200, login="owner:ownerpw", form_array=form_array, accept="text/csv")
            assert "Status='success'" not in answer
            assert "Lines=2" not in answer
            assert ";".join(sharing.DB_FIELDS_V1) in answer
            assert path_base1 in answer
            assert path_base2 in answer

            logging.info("\n*** delete token#1 (form->text)")
            form_array = ["PathOrToken=" + token1]
            _, headers, answer = self._sharing_api_form("token", "delete", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer

            logging.info("\n*** lookup token#1 (form->text) -> should not be there anymore")
            form_array = ["PathOrToken=" + token1]
            _, headers, answer = self._sharing_api_form("token", "list", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='not-found'" in answer
            assert "Lines=0" in answer

            logging.info("\n*** lookup tokens (form->text) -> still one should be there")
            form_array = []
            _, headers, answer = self._sharing_api_form("token", "list", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer
            assert "Lines=1" in answer

            logging.info("\n*** disable token#2 as owner (form->text)")
            form_array = ["PathOrToken=" + token2]
            _, headers, answer = self._sharing_api_form("token", "disable", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer

            logging.info("\n*** lookup token#2 (json->json) -> check for not enabled")
            json_dict = {'PathOrToken': token2}
            _, headers, answer = self._sharing_api_json("token", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['EnabledByOwner'] is False

            logging.info("\n*** enable token#2 as owner (json->json)")
            json_dict = {}
            json_dict['PathOrToken'] = token2
            _, headers, answer = self._sharing_api_json("token", "enable", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** lookup token#2 (form->text) -> check for enabled")
            form_array = []
            form_array.append("PathOrToken=" + token2)
            _, headers, answer = self._sharing_api_form("token", "list", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer
            assert "Lines=1" in answer
            assert "True;True;True;True" in answer

            logging.info("\n*** hide token#2 (form->text)")
            form_array = []
            form_array.append("PathOrToken=" + token2)
            _, headers, answer = self._sharing_api_form("token", "hide", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer

            logging.info("\n*** lookup token#2 (form->text) -> check for hidden")
            form_array = []
            form_array.append("PathOrToken=" + token2)
            _, headers, answer = self._sharing_api_form("token", "list", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer
            assert "Lines=1" in answer
            assert "True;True;True;True" in answer

            logging.info("\n*** unhide token#2 (json->json)")
            json_dict = {}
            json_dict['PathOrToken'] = token2
            _, headers, answer = self._sharing_api_json("token", "unhide", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** lookup token#2 (json->json) -> check for not hidden")
            json_dict = {}
            json_dict['PathOrToken'] = token2
            _, headers, answer = self._sharing_api_json("token", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['HiddenByOwner'] is False

            logging.info("\n*** delete token#2 (json->json)")
            json_dict = {}
            json_dict['PathOrToken'] = token2
            _, headers, answer = self._sharing_api_json("token", "delete", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** lookup token#2 (json->json) -> should not be there anymore")
            json_dict = {}
            json_dict['PathOrToken'] = token2
            _, headers, answer = self._sharing_api_json("token", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "not-found"
            assert answer_dict['Lines'] == 0

            logging.info("\n*** delete collection*")
            self.delete(path_base1, login="owner:ownerpw")
            self.delete(path_base2, login="owner:ownerpw")

    def test_sharing_api_token_usage_proxy(self) -> None:
        """share-by-token API tests simulating a reverse proxy - real usage."""
        script_name = "/radicale"

        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "True",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "server": {"script_name": script_name},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        path_base = "/owner/calendar.ics/"
        event = get_file_content("event1.ics")
        path = path_base + "/event1.ics"

        logging.info("\n*** prepare")
        self.mkcalendar(path_base, login="owner:ownerpw")
        self.put(path, event, login="owner:ownerpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            logging.info("\n*** test access to collection")
            _, headers, answer = self.request("GET", path_base, check=200, login="owner:ownerpw")
            assert "UID:event" in answer

            logging.info("\n*** test access to item")
            _, headers, answer = self.request("GET", path, check=200, login="owner:ownerpw")
            assert "UID:event" in answer

            logging.info("\n*** create token")
            json_dict = {}
            json_dict["PathMapped"] = script_name + path_base
            json_dict["Enabled"] = True
            json_dict["Hidden"] = False
            _, headers, answer = self._sharing_api_json("token", "create", check=200, login="owner:ownerpw", json_dict=json_dict, prefix=script_name)
            answer_dict = json.loads(answer)
            assert "Status" in answer_dict
            assert "PathOrToken" in answer_dict
            Token = answer_dict["PathOrToken"]
            logging.debug("Token: %r", Token)
            assert Token.startswith(script_name) is True
            path_shared = Token

            # check PROPFIND item as owner (remove prefix again as added later)
            logging.info("\n*** PROPFIND item as owner -> calendar")
            response = self._propfind_allprop(path_shared.removeprefix(script_name), login="owner:ownerpw", prefix=script_name)
            logging.debug("response: %r", response)
            assert "CR:supported-address-data" not in response
            assert "C:supported-calendar-component-set" in response
            assert "D:current-user-privilege-set" in response

    def test_sharing_api_token_usage_basic(self) -> None:
        """share-by-token API tests - real usage."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        form_array: Sequence[str]
        json_dict: dict

        path_base = "/owner/calendar.ics/"
        path_base2 = "/owner/calendar2.ics/"

        logging.info("\n*** prepare")
        self.mkcalendar(path_base, login="owner:ownerpw")
        event = get_file_content("event1.ics")
        path = path_base + "/event1.ics"
        self.put(path, event, login="owner:ownerpw")

        self.mkcalendar(path_base2, login="owner:ownerpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            logging.info("\n*** test access to collection")
            _, headers, answer = self.request("GET", path_base, check=200, login="owner:ownerpw")
            assert "UID:event" in answer

            logging.info("\n*** test access to item")
            _, headers, answer = self.request("GET", path, check=200, login="owner:ownerpw")
            assert "UID:event" in answer

            logging.info("\n*** create token")
            form_array = []
            form_array.append("PathMapped=" + path_base)
            _, headers, answer = self._sharing_api_form("token", "create", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer
            assert "PathOrToken=" in answer
            # extract token
            match = re.search("PathOrToken='(.+)'", answer)
            if match:
                token = match.group(1)
                logging.info("received token %r", token)
            else:
                assert False

            logging.info("\n*** create token#2")
            form_array = []
            form_array.append("PathMapped=" + path_base2)
            _, headers, answer = self._sharing_api_form("token", "create", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer
            assert "PathOrToken=" in answer
            # extract token
            match = re.search("PathOrToken='(.+)'", answer)
            if match:
                token2 = match.group(1)
                logging.info("received token %r", token2)
            else:
                assert False

            logging.info("\n*** enable token (form->text)")
            form_array = ["PathOrToken=" + token]
            _, headers, answer = self._sharing_api_form("token", "enable", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer

            logging.info("\n*** fetch collection using invalid token")
            _, headers, answer = self.request("GET", "/.token/v1/invalidtoken/", check=403)

            logging.info("\n*** fetch collection using token")
            _, headers, answer = self.request("GET", token, check=200)
            assert "UID:event" in answer

            logging.info("\n*** disable token (form->text)")
            form_array = ["PathOrToken=" + token]
            _, headers, answer = self._sharing_api_form("token", "disable", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer

            logging.info("\n*** fetch collection using disabled token")
            _, headers, answer = self.request("GET", token, check=403)

            logging.info("\n*** enable token (form->text)")
            form_array = ["PathOrToken=" + token]
            _, headers, answer = self._sharing_api_form("token", "enable", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer

            logging.info("\n*** fetch collection using token")
            _, headers, answer = self.request("GET", token, check=200)
            assert "UID:event" in answer

            logging.info("\n*** delete token#2 (json->json)")
            json_dict = {}
            json_dict['PathOrToken'] = token2
            _, headers, answer = self._sharing_api_json("token", "delete", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['ApiVersion'] == 1
            assert answer_dict['Status'] == "success"

            logging.info("\n*** delete token (json->json)")
            json_dict = {'PathOrToken': token}
            _, headers, answer = self._sharing_api_json("token", "delete", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['ApiVersion'] == 1
            assert answer_dict['Status'] == "success"

            logging.info("\n*** delete token (form->text) -> no longer available")
            form_array = ["PathOrToken=" + token]
            _, headers, answer = self._sharing_api_form("token", "delete", check=404, login="owner:ownerpw", form_array=form_array)

            logging.info("\n*** fetch collection using deleted token")
            _, headers, answer = self.request("GET", token, check=403)

    def test_sharing_api_token_usage_delay(self) -> None:
        """share-by-token API tests - real usage."""
        delay = .3
        delay_min = delay * 0.9  # no random jitter during test
        delay_max = delay + 0.2  # no random jitter during test
        if sys.platform == "darwin":  # no reliable sleep times
            delay_max = delay_max * 1.5

        self.configure({"auth": {"type": "htpasswd",
                                 "delay": delay,
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        form_array: Sequence[str]
        json_dict: dict

        path_base = "/owner/calendar.ics/"

        logging.info("\n*** prepare")
        self.mkcalendar(path_base, login="owner:ownerpw")
        event = get_file_content("event1.ics")
        path = path_base + "/event1.ics"
        self.put(path, event, login="owner:ownerpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            logging.info("\n*** create token")
            form_array = []
            form_array.append("PathMapped=" + path_base)
            form_array.append("Enabled=True")
            _, headers, answer = self._sharing_api_form("token", "create", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer
            assert "PathOrToken=" in answer
            # extract token
            match = re.search("PathOrToken='(.+)'", answer)
            if match:
                token = match.group(1)
                logging.info("received token %r", token)
            else:
                assert False

            logging.info("\n*** fetch collection using invalid token")
            time_begin = datetime.datetime.now()
            _, headers, answer = self.request("GET", "/.token/v1/invalidtoken/", check=403)
            time_end = datetime.datetime.now()
            time_delta = (time_end - time_begin).total_seconds()
            assert time_delta > delay_min
            assert time_delta < delay_max

            logging.info("\n*** fetch collection using token")
            time_begin = datetime.datetime.now()
            _, headers, answer = self.request("GET", token, check=200)
            time_end = datetime.datetime.now()
            time_delta = (time_end - time_begin).total_seconds()
            assert time_delta < delay_min  # no delay
            assert "UID:event" in answer

            logging.info("\n*** disable token (form->text)")
            form_array = ["PathOrToken=" + token]
            _, headers, answer = self._sharing_api_form("token", "disable", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer

            logging.info("\n*** fetch collection using disabled token")
            time_begin = datetime.datetime.now()
            _, headers, answer = self.request("GET", token, check=403)
            time_end = datetime.datetime.now()
            time_delta = (time_end - time_begin).total_seconds()
            assert time_delta > delay_min
            assert time_delta < delay_max

            logging.info("\n*** delete token (json->json)")
            json_dict = {'PathOrToken': token}
            _, headers, answer = self._sharing_api_json("token", "delete", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['ApiVersion'] == 1
            assert answer_dict['Status'] == "success"

            logging.info("\n*** fetch collection using deleted token with delay")
            time_begin = datetime.datetime.now()
            _, headers, answer = self.request("GET", token, check=403)
            time_end = datetime.datetime.now()
            time_delta = (time_end - time_begin).total_seconds()
            assert time_delta > delay_min
            assert time_delta < delay_max

    def test_sharing_api_map_basic(self) -> None:
        """share-by-map API basic tests."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        path_owner = "/owner/calendar.ics/"
        path_user = "/user/calendar-owner.ics/"
        path_user2 = "/user/calendar-owner2.ics/"
        self.mkcalendar(path_owner, login="owner:ownerpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            self.configure({"sharing": {"permit_create_map": "False"}})

            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            logging.info("\n*** create map without PathMapped (json) -> 400")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "create", 400, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** create map without PathMapped but User (json) -> 400")
            json_dict = {'User': "user"}
            _, headers, answer = self._sharing_api_json("map", "create", 400, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** create map without PathMapped but User and PathOrToken (json) -> 400")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathOrToken'] = path_user
            _, headers, answer = self._sharing_api_json("map", "create", 400, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** create map with PathMapped, User, PathOrToken without trailing / (json) -> 400")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathOrToken'] = path_user
            json_dict['PathMapped'] = path_owner.rstrip('/')
            _, headers, answer = self._sharing_api_json("map", "create", 400, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** create map with PathMapped without trailing /, User, PathOrToken (json) -> 400")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathOrToken'] = path_user.rstrip('/')
            json_dict['PathMapped'] = path_owner
            _, headers, answer = self._sharing_api_json("map", "create", 400, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** create map with PathMapped, User, PathOrToken - not permitted (json) -> 403")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathOrToken'] = path_user
            json_dict['PathMapped'] = path_owner
            _, headers, answer = self._sharing_api_json("map", "create", 403, login="owner:ownerpw", json_dict=json_dict)

            self.configure({"sharing": {"permit_create_map": "True"}})

            logging.info("\n*** create map with PathMapped, User, PathOrToken (json) -> 200")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathOrToken'] = path_user
            json_dict['PathMapped'] = path_owner
            _, headers, answer = self._sharing_api_json("map", "create", 200, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** create map with PathMapped, User, PathOrToken2 (json) -> 409")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathOrToken'] = path_user2
            json_dict['PathMapped'] = path_owner
            _, headers, answer = self._sharing_api_json("map", "create", 409, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** create map with PathMapped, User, PathOrToken=PathOwner (json) -> 409")
            json_dict = {}
            json_dict['User'] = "owner"
            json_dict['PathOrToken'] = path_owner
            json_dict['PathMapped'] = path_owner
            _, headers, answer = self._sharing_api_json("map", "create", 409, login="owner:ownerpw", json_dict=json_dict)

    def test_sharing_api_map_usage(self) -> None:
        """share-by-map API usage tests."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "permit_properties_overlay": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_header_on_debug": "True",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "False"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        file_item1 = "event1.ics"
        file_item2 = "event2.ics"
        path_shared = "/user/calendarU-shared-by-owner.ics/"
        path_shared_item1 = os.path.join(path_shared, file_item1)
        path_shared_item2 = os.path.join(path_shared, file_item2)
        path_mapped = "/owner/calendarU.ics/"
        path_mapped_item1 = os.path.join(path_mapped, file_item1)
        path_mapped_item2 = os.path.join(path_mapped, file_item2)

        logging.info("\n*** prepare and test access")
        self.mkcalendar(path_mapped, login="owner:ownerpw")
        event = get_file_content(file_item1)
        self.put(path_mapped_item1, event, check=201, login="owner:ownerpw")
        event = get_file_content(file_item2)
        self.put(path_mapped_item2, event, check=201, login="owner:ownerpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            logging.info("\n*** test access to collection")
            _, headers, answer = self.request("GET", path_mapped, check=200, login="owner:ownerpw")
            assert "UID:event1" in answer
            assert "UID:event2" in answer

            logging.info("\n*** test access to item")
            _, headers, answer = self.request("GET", path_mapped_item1, check=200, login="owner:ownerpw")
            assert "UID:event1" in answer

            logging.info("\n*** create map with PathMapped and User and PathOrToken (json)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            json_dict['Properties'] = {"D:displayname": "Test"}
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** lookup map without filter (json->json)")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['PathOrToken'] == path_shared
            assert answer_dict['Content'][0]['PathMapped'] == path_mapped
            assert answer_dict['Content'][0]['ShareType'] == "map"
            assert answer_dict['Content'][0]['Owner'] == "owner"
            assert answer_dict['Content'][0]['User'] == "user"
            assert answer_dict['Content'][0]['EnabledByOwner'] is False
            assert answer_dict['Content'][0]['EnabledByUser'] is False
            assert answer_dict['Content'][0]['HiddenByOwner'] is True
            assert answer_dict['Content'][0]['HiddenByUser'] is True
            assert answer_dict['Content'][0]['Permissions'] == "r"
            assert answer_dict['Content'][0]['Properties'] == {"D:displayname": "Test"}

            logging.info("\n*** enable map by owner (json->json) -> 200")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** enable map by user (json->json)")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** fetch collection (without credentials)")
            _, headers, answer = self.request("GET", path_mapped, check=401)

            logging.info("\n*** fetch collection (with credentials) as owner")
            _, headers, answer = self.request("GET", path_mapped, check=200, login="owner:ownerpw")
            assert "UID:event" in answer
            assert 'Content-Disposition' in headers
            # fallback title
            assert 'Calendar.ics' in headers['Content-Disposition']

            logging.info("\n*** fetch item (with credentials) as owner")
            _, headers, answer = self.request("GET", path_mapped_item1, check=200, login="owner:ownerpw")
            assert "UID:event" in answer

            logging.info("\n*** fetch collection (with credentials) as user")
            _, headers, answer = self.request("GET", path_mapped, check=403, login="user:userpw")

            logging.info("\n*** fetch collection via map (with credentials) as user")
            _, headers, answer = self.request("GET", path_shared, check=200, login="user:userpw")
            assert "UID:event1" in answer
            assert "UID:event2" in answer
            assert 'Content-Disposition' in headers
            # title from Properties
            assert 'Test.ics' in headers['Content-Disposition']

            logging.info("\n*** fetch item via map (with credentials) as user")
            _, headers, answer = self.request("GET", path_shared_item1, check=200, login="user:userpw")
            # only requested event has to be in the answer
            assert "UID:event1" in answer
            assert "UID:event2" not in answer

            logging.info("\n*** fetch item via map (with credentials) as user")
            _, headers, answer = self.request("GET", path_shared_item2, check=200, login="user:userpw")
            # only requested event has to be in the answer
            assert "UID:event2" in answer
            assert "UID:event1" not in answer

            logging.info("\n*** disable map by owner (json->json)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "disable", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** fetch collection via map (with credentials) as user -> n/a")
            _, headers, answer = self.request("GET", path_shared, check=404, login="user:userpw")

            logging.info("\n*** enable map by owner (json->json)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** fetch collection via map (with credentials) as user")
            _, headers, answer = self.request("GET", path_shared, check=200, login="user:userpw")

            logging.info("\n*** disable map by user (json->json)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "disable", check=200, login="user:userpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** fetch collection via map (with credentials) as user -> n/a")
            _, headers, answer = self.request("GET", path_shared, check=404, login="user:userpw")

            logging.info("\n*** delete map by user (json->json) -> fail")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "delete", check=403, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** update map by user related to user flags (json->json)")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            json_dict['Enabled'] = True
            json_dict['Hidden'] = True
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** list as user and check user flags (json->json)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="user:userpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['EnabledByUser'] is True
            assert answer_dict['Content'][0]['HiddenByUser'] is True

            logging.info("\n*** update map by user related to user flags (json->json)")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            json_dict['Enabled'] = False
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** list as user and check EnabledByUser==False (json->json)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="user:userpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['EnabledByUser'] is False

            logging.info("\n*** update map by owner related to owner flags (json->json)")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            json_dict['Enabled'] = False
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** list as user and check owner flags (json->json)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="user:userpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['EnabledByOwner'] is False
            assert answer_dict['Content'][0]['HiddenByOwner'] is False

            logging.info("\n*** update map by owner related to owner flag Enabled->True (json->json)")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            json_dict['Enabled'] = True
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** list as user and check owner flags (json->json)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="user:userpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['EnabledByOwner'] is True

            logging.info("\n*** update map by owner related to Properties -> 200")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            json_dict['Properties'] = {"ICAL:calendar-color": "#CCCCCC"}
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** list as user and check Properties (json->json)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="user:userpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['Properties']["ICAL:calendar-color"] == "#CCCCCC"

            logging.info("\n*** update map by user related to Properties -> 200")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            json_dict['Properties'] = {"ICAL:calendar-color": "#DDDDDD"}
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** list as user and check Properties (json->json)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="user:userpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['Properties']["ICAL:calendar-color"] == "#DDDDDD"

            logging.info("\n*** delete map by owner (json->json) -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "delete", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

    def test_sharing_api_map_update_delete_permissions(self) -> None:
        """share-by-map API usage tests."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "permit_properties_overlay": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "request_content_on_debug": "False"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        path_shared = "/user/calendarUP-shared-by-owner.ics/"
        path_shared2 = "/user/calendarUP-shared-by-owner2.ics/"
        path_mapped = "/owner/calendarUP.ics/"
        path_mapped2 = "/owner/calendarUP2.ics/"
        path_mapped_o2 = "/owner2/calendarUP3.ics/"

        logging.info("\n*** prepare and test access")
        self.mkcalendar(path_mapped, login="owner:ownerpw")
        self.mkcalendar(path_mapped2, login="owner:ownerpw")
        self.mkcalendar(path_mapped_o2, login="owner2:owner2pw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            logging.info("\n*** create map with PathMapped and User and PathOrToken (json)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** update map by owner: User (json->json) -> 200")
            json_dict = {}
            json_dict['User'] = "owner"
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** update map by owner: PathMapped (json->json) -> 200")
            json_dict = {}
            json_dict['PathMapped'] = path_mapped2
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** update map by owner: PathOrToken (json->json) -> 404 (is primary key, therefore not found)")
            json_dict = {}
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared2
            _, headers, answer = self._sharing_api_json("map", "update", check=404, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** update map by owner: PathMapped(owner2) (json->json) -> 403")
            json_dict = {}
            json_dict['PathMapped'] = path_mapped_o2
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "update", check=403, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** update map by owner: PathOrToken (json->json) -> 404")
            json_dict = {}
            json_dict['PathOrToken'] = path_mapped
            _, headers, answer = self._sharing_api_json("map", "update", check=404, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** update map by owner: Permissions without PathOrToken (json->json) -> 400")
            json_dict = {}
            json_dict['Permissions'] = "rw"
            _, headers, answer = self._sharing_api_json("map", "update", check=400, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** update map by owner: Permissions (json->json) -> 200")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            json_dict['Permissions'] = "rw"
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** update map by owner: Enabled (json->json) -> 200")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            json_dict['Enabled'] = True
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** update map by owner: Hidden (json->json) -> 200")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** update map by owner: Properties (json->json) -> 200")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            json_dict['Properties'] = {}
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** update map by user: Enabled user-mispatch (json->json) -> 403")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            json_dict['Enabled'] = True
            _, headers, answer = self._sharing_api_json("map", "update", check=403, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** update map by owner: User (json->json) -> 200")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** update map by user: User (same) (json->json) -> 403")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "update", check=403, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** update map by user: PathMapped (json->json) -> 403")
            json_dict = {}
            json_dict['PathMapped'] = path_shared
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "update", check=403, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** update map by user: PathOrToken (json->json) -> 404")
            json_dict = {}
            json_dict['PathOrToken'] = path_mapped
            _, headers, answer = self._sharing_api_json("map", "update", check=404, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** update map by user: Permissions (json->json) -> 403")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            json_dict['Permissions'] = "rw"
            _, headers, answer = self._sharing_api_json("map", "update", check=403, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** update map by user: Enabled (json->json) -> 200")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            json_dict['Enabled'] = True
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** update map by user: Hidden (json->json) -> 200")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** update map by user: Properties (json->json) -> 200")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            json_dict['Properties'] = {}
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** delete map by user (json->json) -> 403")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "delete", check=403, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** delete map by owner (json->json) -> ok")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "delete", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** delete map by owner 2nd time (json->json) -> 404")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "delete", check=404, login="owner:ownerpw", json_dict=json_dict)

    def test_sharing_api_map_usercheck(self) -> None:
        """share-by-map API usage tests related to usercheck."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        path_share1 = "/user1/calendar-shared-by-owner1.ics/"
        path_mapped1 = "/owner1/calendar1.ics/"
        path_share2 = "/user2/calendar-shared-by-owner2.ics/"
        path_mapped2 = "/owner2/calendar2.ics/"

        logging.info("\n*** prepare")
        self.mkcalendar(path_mapped1, login="%s:%s" % ("owner1", "owner1pw"))
        event = get_file_content("event1.ics")
        path = path_mapped1 + "/event1.ics"
        self.put(path, event, login="%s:%s" % ("owner1", "owner1pw"))

        self.mkcalendar(path_mapped2, login="%s:%s" % ("owner2", "owner2pw"))
        event = get_file_content("event1.ics")
        path = path_mapped2 + "/event1.ics"
        self.put(path, event, login="%s:%s" % ("owner2", "owner2pw"))

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            logging.info("\n*** create map user1/owner1 as owner(wrong owner) -> fail")
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_mapped1
            json_dict['PathOrToken'] = path_share1
            _, headers, answer = self._sharing_api_json("map", "create", check=403, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1:r -> ok")
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_mapped1
            json_dict['PathOrToken'] = path_share1
            json_dict['Permissions'] = "r"
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** create map user1/owner1 (repeat) -> fail")
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_mapped1
            json_dict['PathOrToken'] = path_share1
            _, headers, answer = self._sharing_api_json("map", "create", check=409, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user2/owner2:rw -> ok")
            json_dict = {}
            json_dict['User'] = "user2"
            json_dict['PathMapped'] = path_mapped2
            json_dict['PathOrToken'] = path_share2
            json_dict['Permissions'] = "rw"
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner2:owner2pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** create map user2/owner1 -> 409 (conflict)")
            json_dict = {}
            json_dict['User'] = "user2"
            json_dict['PathMapped'] = path_mapped2
            json_dict['PathOrToken'] = path_share1
            _, headers, answer = self._sharing_api_json("map", "create", check=409, login="owner2:owner2pw", json_dict=json_dict)

            logging.info("\n*** delete map user1 -> ok")
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_mapped1
            json_dict['PathOrToken'] = path_share1
            _, headers, answer = self._sharing_api_json("map", "delete", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** delete map user2 -> ok")
            json_dict = {}
            json_dict['User'] = "user2"
            json_dict['PathMapped'] = path_mapped2
            json_dict['PathOrToken'] = path_share2
            _, headers, answer = self._sharing_api_json("map", "delete", check=200, login="owner2:owner2pw", json_dict=json_dict)

    def test_sharing_api_map_permissions(self) -> None:
        """share-by-map API usage tests related to permissions."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "request_content_on_debug": "False"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        path_shared_r = "/user/calendar-shared-by-owner-r.ics/"
        path_shared_w = "/user1/calendar-shared-by-owner-w.ics/"
        path_shared_rw = "/user2/calendar-shared-by-owner-rw.ics/"
        path_mapped = "/owner/calendar.ics/"

        logging.info("\n*** prepare and test access")
        self.mkcalendar(path_mapped, login="owner:ownerpw")
        event = get_file_content("event1.ics")
        path = path_mapped + "/event1.ics"
        self.put(path, event, login="owner:ownerpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # check
            logging.info("\n*** fetch event as owner (init) -> ok")
            _, headers, answer = self.request("GET", path_mapped + "event1.ics", check=200, login="owner:ownerpw")

            # create maps
            logging.info("\n*** create map user/owner:r -> 400 (Enabled is not boolean)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = "True"
            _, headers, answer = self._sharing_api_json("map", "create", check=400, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** create map user/owner:r -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** create map user1/owner:w -> ok")
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_w
            json_dict['Permissions'] = "w"
            json_dict['Enabled'] = True
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** create map user2/owner:rw -> ok")
            json_dict = {}
            json_dict['User'] = "user2"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_rw
            json_dict['Permissions'] = "rw"
            json_dict['Enabled'] = True
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # list created maps
            logging.info("\n*** list (json->text)")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict, accept="text/csv")

            # check permissions, no map is enabled by user -> 404
            logging.info("\n*** fetch collection via map:r -> n/a")
            _, headers, answer = self.request("GET", path_shared_r, check=404, login="user:userpw")

            logging.info("\n*** fetch collection via map:w -> n/a")
            _, headers, answer = self.request("GET", path_shared_w, check=404, login="user1:user1pw")

            logging.info("\n*** fetch collection via map:rw -> n/a")
            _, headers, answer = self.request("GET", path_shared_rw, check=404, login="user2:user2pw")

            # enable maps by user
            logging.info("\n*** enable map by user:r")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** enable map by user1:w")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared_w
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user1:user1pw", json_dict=json_dict)

            logging.info("\n*** enable map by user2:rw")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared_rw
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user2:user2pw", json_dict=json_dict)

            # list adjusted maps
            logging.info("\n*** list (json->text)")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict, accept="text/csv")

            # check permissions, no map is enabled by user -> 404
            logging.info("\n*** fetch collection via map:r -> ok")
            _, headers, answer = self.request("GET", path_shared_r, check=200, login="user:userpw")

            logging.info("\n*** fetch collection via map:w -> fail")
            _, headers, answer = self.request("GET", path_shared_w, check=403, login="user1:user1pw")

            logging.info("\n*** fetch collection via map:rw -> ok")
            _, headers, answer = self.request("GET", path_shared_rw, check=200, login="user2:user2pw")

            # list adjusted maps
            logging.info("\n*** list (json->text)")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict, accept="text/csv")

            # PUT
            logging.info("\n*** put to collection by user via map:r -> fail")
            event = get_file_content("event2.ics")
            path = path_shared_r + "/event2.ics"
            self.put(path, event, check=403, login="user:userpw")

            logging.info("\n*** put to collection by user1 via map:w -> ok")
            event = get_file_content("event2.ics")
            path = path_shared_w + "event2.ics"
            self.put(path, event, check=201, login="user1:user1pw")

            # check result
            logging.info("\n*** fetch event via map:r -> ok")
            _, headers, answer = self.request("GET", path_shared_r + "event2.ics", check=200, login="user:userpw")

            logging.info("\n*** fetch event as owner -> ok")
            _, headers, answer = self.request("GET", path_mapped + "event2.ics", check=200, login="owner:ownerpw")

            logging.info("\n*** put to collection by user2 via map:rw -> ok")
            event = get_file_content("event3.ics")
            path = path_shared_rw + "event3.ics"
            self.put(path, event, check=201, login="user2:user2pw")

            # check result
            logging.info("\n*** fetch event via map:r -> ok")
            _, headers, answer = self.request("GET", path_shared_r + "event2.ics", check=200, login="user:userpw")

            logging.info("\n*** fetch event via map:r -> ok")
            _, headers, answer = self.request("GET", path_shared_r + "event3.ics", check=200, login="user:userpw")

            logging.info("\n*** fetch event via map:rw -> ok")
            _, headers, answer = self.request("GET", path_shared_rw + "event2.ics", check=200, login="user2:user2pw")

            logging.info("\n*** fetch event via map:rw -> ok")
            _, headers, answer = self.request("GET", path_shared_rw + "event3.ics", check=200, login="user2:user2pw")

            logging.info("\n*** fetch event as owner -> ok")
            _, headers, answer = self.request("GET", path_mapped + "event1.ics", check=200, login="owner:ownerpw")

            logging.info("\n*** fetch event as owner -> ok")
            _, headers, answer = self.request("GET", path_mapped + "event2.ics", check=200, login="owner:ownerpw")

            logging.info("\n*** fetch event as owner -> ok")
            _, headers, answer = self.request("GET", path_mapped + "event3.ics", check=200, login="owner:ownerpw")

            # DELETE
            logging.info("\n*** DELETE from collection by user via map:r -> fail")
            _, headers, answer = self.request("DELETE", path_shared_r + "event1.ics", check=403, login="user:userpw")

            logging.info("\n*** DELETE from collection by user via map:rw -> ok")
            _, headers, answer = self.request("DELETE", path_shared_rw + "event2.ics", check=200, login="user2:user2pw")

            logging.info("\n*** DELETE from collection by user via map:w -> ok")
            _, headers, answer = self.request("DELETE", path_shared_w + "event3.ics", check=200, login="user1:user1pw")

            # check results
            logging.info("\n*** fetch event as owner -> ok")
            _, headers, answer = self.request("GET", path_mapped + "event1.ics", check=200, login="owner:ownerpw")

            logging.info("\n*** fetch event as owner -> fail")
            _, headers, answer = self.request("GET", path_mapped + "event2.ics", check=404, login="owner:ownerpw")

            logging.info("\n*** fetch event as owner -> fail")
            _, headers, answer = self.request("GET", path_mapped + "event3.ics", check=404, login="owner:ownerpw")

    def test_sharing_api_map_report_access(self) -> None:
        """share-by-map API usage tests related to report."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        path_shared = "/user/calendar2-shared-by-owner.ics/"
        path_mapped = "/owner/calendar2.ics/"
        path_shared_item = os.path.join(path_shared, "event1.ics")
        path_mapped_item = os.path.join(path_mapped, "event1.ics")

        logging.info("\n*** prepare and test access")
        self.mkcalendar(path_mapped, login="owner:ownerpw")
        event = get_file_content("event1.ics")
        self.put(path_mapped_item, event, login="owner:ownerpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # check GET
            logging.info("\n*** GET event as owner (init) -> ok")
            _, headers, answer = self.request("GET", path_mapped + "event1.ics", check=200, login="owner:ownerpw")

            # check REPORT as owner
            logging.info("\n*** REPORT collection owner -> ok")
            _, responses = self.report(path_mapped, """\
<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop xmlns:D="DAV:">
        <D:getetag />
    </D:prop>
</C:calendar-query>""", login="owner:ownerpw")
            assert len(responses) == 1
            logging.info("response: %r", responses)
            response = responses[path_mapped_item]
            assert isinstance(response, dict)
            status, prop = response["D:getetag"]
            assert status == 200 and prop.text

            # create map
            logging.info("\n*** create map user/owner -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # check REPORT as user
            logging.info("\n*** REPORT collection user -> 404")
            _, responses = self.report(path_shared, """\
<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop xmlns:D="DAV:">
        <D:getetag />
    </D:prop>
</C:calendar-query>""", login="user:userpw", check=404)

            # enable map by user
            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            # check REPORT as user
            logging.info("\n*** REPORT collection user -> ok")
            _, responses = self.report(path_shared, """\
<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop xmlns:D="DAV:">
        <D:getetag />
    </D:prop>
</C:calendar-query>""", login="user:userpw")
            assert len(responses) == 1
            logging.info("response: %r", responses)
            response = responses[path_shared_item]
            assert isinstance(response, dict)
            status, prop = response["D:getetag"]
            assert status == 200 and prop.text

    def test_sharing_api_map_hidden(self) -> None:
        """share-by-map API usage tests related to report checking hidden."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        path_user_base = "/user/"
        path_mapped_base = "/owner/"
        path_user = path_user_base + "calendarRH.ics/"
        path_mapped = path_mapped_base + "calendarRH.ics/"
        path_mapped2 = path_mapped_base + "calendarRH2.ics/"
        path_shared = path_user_base + "calendarRH-shared-by-owner.ics/"
        path_mapped_item = os.path.join(path_mapped, "event1.ics")
        path_user_item = os.path.join(path_user, "event2.ics")

        logging.info("\n*** prepare and test access")
        self.mkcalendar(path_mapped, login="owner:ownerpw")
        event = get_file_content("event1.ics")
        self.put(path_mapped_item, event, login="owner:ownerpw")

        self.mkcalendar(path_mapped2, login="owner:ownerpw")

        self.mkcalendar(path_user, login="user:userpw")
        event = get_file_content("event2.ics")
        self.put(path_user_item, event, login="user:userpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # check GET
            logging.info("\n*** GET event1 as owner -> 200")
            _, headers, answer = self.request("GET", path_mapped_item, check=200, login="owner:ownerpw")

            logging.info("\n*** GET event2 as user -> 200")
            _, headers, answer = self.request("GET", path_user_item, check=200, login="user:userpw")

            logging.info("\n*** GET collections as user -> 403")
            _, headers, answer = self.request("GET", path_user_base, check=403, login="user:userpw")

            # check PROPFIND as user
            logging.info("\n*** PROPFIND collection user -> ok")
            _, responses = self.propfind(path_user_base, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <calendar-home-set xmlns="urn:ietf:params:xml:ns:caldav" />
</propfind>""", login="user:userpw", HTTP_DEPTH="1")
            assert len(responses) == 2
            logging.info("response: %r", responses)
            response = responses[path_user]
            assert isinstance(response, dict)

            # create map
            logging.info("\n*** create map user/owner -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # check PROPFIND as owner
            logging.info("\n*** PROPFIND collection owner -> ok")
            _, responses = self.propfind(path_mapped_base, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <calendar-home-set xmlns="urn:ietf:params:xml:ns:caldav" />
</propfind>""", login="owner:ownerpw", HTTP_DEPTH="1")
            assert len(responses) == 3
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert isinstance(response, dict)
            response = responses[path_mapped2]
            assert isinstance(response, dict)

            # check PROPFIND as user
            logging.info("\n*** PROPFIND collection user -> ok")
            _, responses = self.propfind(path_user_base, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <calendar-home-set xmlns="urn:ietf:params:xml:ns:caldav" />
</propfind>""", login="user:userpw", HTTP_DEPTH="1")
            assert len(responses) == 2
            logging.info("response: %r", responses)
            response = responses[path_user]
            assert isinstance(response, dict)

            # enable map by user
            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            # check PROPFIND as user
            logging.info("\n*** PROPFIND collection user -> ok")
            _, responses = self.propfind(path_user_base, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <calendar-home-set xmlns="urn:ietf:params:xml:ns:caldav" />
</propfind>""", login="user:userpw", HTTP_DEPTH="1")
            assert len(responses) == 2
            logging.info("response: %r", responses)
            response = responses[path_user]
            assert isinstance(response, dict)

            # unhide map by user
            logging.info("\n*** unhide map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "unhide", check=200, login="user:userpw", json_dict=json_dict)

            # check PROPFIND as user
            logging.info("\n*** PROPFIND collection user -> ok (now 3 items)")
            _, responses = self.propfind(path_user_base, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <calendar-home-set xmlns="urn:ietf:params:xml:ns:caldav" />
</propfind>""", login="user:userpw", HTTP_DEPTH="1")
            assert len(responses) == 3
            logging.info("response: %r", responses)
            response = responses[path_user]
            assert isinstance(response, dict)
            response = responses[path_shared]
            assert isinstance(response, dict)

    def test_sharing_api_map_propfind_base(self) -> None:
        """share-by-map API usage tests related to propfind."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        path_shared = "/user/calendar-shared-by-owner.ics/"
        path_mapped = "/owner/calendar.ics/"

        logging.info("\n*** prepare and test access")
        self.mkcalendar(path_mapped, login="owner:ownerpw")
        event = get_file_content("event1.ics")
        path = os.path.join(path_mapped, "event1.ics")
        self.put(path, event, login="owner:ownerpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # check GET
            logging.info("\n*** GET event as owner (init) -> ok")
            _, headers, answer = self.request("GET", path_mapped + "event1.ics", check=200, login="owner:ownerpw")

            # check PROPFIND as owner
            logging.info("\n*** PROPFIND collection owner -> ok")
            _, responses = self.propfind(path_mapped, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int) and len(response) == 1
            status, prop = response["D:current-user-principal"]
            assert status == 200 and len(prop) == 1
            element = prop.find(xmlutils.make_clark("D:href"))
            assert element is not None and element.text == "/owner/"

            # create map
            logging.info("\n*** create map user/owner -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # check PROPFIND as user
            logging.info("\n*** PROPFIND collection user -> 404")
            _, responses = self.propfind(path_shared, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", login="user:userpw", check=404)

            # enable map by user
            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            # check PROPFIND as user
            logging.info("\n*** PROPFIND collection user -> ok")
            _, responses = self.propfind(path_shared, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", login="user:userpw", check=207)
            logging.info("response: %r", responses)
            response = responses[path_shared]
            assert not isinstance(response, int) and len(response) == 1
            status, prop = response["D:current-user-principal"]
            assert status == 200 and len(prop) == 1
            element = prop.find(xmlutils.make_clark("D:href"))
            assert element is not None and element.text == "/user/"

    def test_sharing_api_map_proppatch_acl(self) -> None:
        """share-by-map API usage tests related to report."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        path_mapped = "/owner/calendarPP.ics/"
        path_shared_r = "/user/calendarPP-shared-by-owner-r.ics/"
        path_shared_w = "/user1/calendarPP-shared-by-owner-w.ics/"
        path_shared_rw = "/user2/calendarPP-shared-by-owner-rw.ics/"

        logging.info("\n*** prepare and test access")
        self.mkcalendar(path_mapped, login="owner:ownerpw")
        event = get_file_content("event1.ics")
        path = os.path.join(path_mapped, "event1.ics")
        self.put(path, event, login="owner:ownerpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # check GET
            logging.info("\n*** GET event as owner (init) -> ok")
            _, headers, answer = self.request("GET", path_mapped + "event1.ics", check=200, login="owner:ownerpw")

            # check PROPFIND as owner
            logging.info("\n*** PROPFIND collection owner -> ok")
            _, responses = self.propfind(path_mapped, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int) and len(response) == 1
            status, prop = response["D:current-user-principal"]
            assert status == 200 and len(prop) == 1
            element = prop.find(xmlutils.make_clark("D:href"))
            assert element is not None and element.text == "/owner/"

            # check PROPPATCH as owner
            logging.info("\n*** PROPPATCH collection owner -> ok")
            proppatch = get_file_content("proppatch_set_calendar_color.xml")
            _, responses = self.proppatch(path_mapped, proppatch, login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int) and len(response) == 1
            status, prop = response["ICAL:calendar-color"]
            assert status == 200 and not prop.text

            # check PROPPATCH as user
            logging.info("\n*** PROPPATCH collection as user -> 404")
            proppatch = get_file_content("proppatch_remove_calendar_color.xml")
            _, responses = self.proppatch(path_shared_r, proppatch, login="user:userpw", check=404)
            _, responses = self.proppatch(path_shared_w, proppatch, login="user1:user1pw", check=404)
            _, responses = self.proppatch(path_shared_rw, proppatch, login="user2:user2pw", check=404)

            # create map
            logging.info("\n*** create map user/owner:r -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** create map user1/owner:w -> ok")
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_w
            json_dict['Permissions'] = "w"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** create map user2/owner:rw -> ok")
            json_dict = {}
            json_dict['User'] = "user2"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_rw
            json_dict['Permissions'] = "rw"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # check PROPPATCH as user
            logging.info("\n*** PROPPATCH collection as user -> 403")
            proppatch = get_file_content("proppatch_set_calendar_color.xml")
            _, responses = self.proppatch(path_shared_r, proppatch, login="user:userpw", check=404)
            _, responses = self.proppatch(path_shared_w, proppatch, login="user1:user1pw", check=404)
            _, responses = self.proppatch(path_shared_rw, proppatch, login="user2:user2pw", check=404)

            # enable map by user
            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** enable map by user1")
            json_dict = {}
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_w
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user1:user1pw", json_dict=json_dict)

            logging.info("\n*** enable map by user2")
            json_dict = {}
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_rw
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user2:user2pw", json_dict=json_dict)

            # check PROPPATCH as user
            proppatch = get_file_content("proppatch_remove_calendar_color.xml")
            logging.info("\n*** PROPPATCH collection as user:r -> 403")
            _, responses = self.proppatch(path_shared_r, proppatch, login="user:userpw", check=403)

            logging.info("\n*** PROPPATCH collection as user:w -> ok")
            _, responses = self.proppatch(path_shared_w, proppatch, login="user1:user1pw")
            logging.info("response: %r", responses)

            logging.info("\n*** PROPPATCH collection as user:rw -> ok")
            _, responses = self.proppatch(path_shared_rw, proppatch, login="user2:user2pw")
            logging.info("response: %r", responses)

            # check PROPFIND as owner
            logging.info("\n*** PROPFIND collection owner -> ok")
            _, responses = self.propfind(path_mapped, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int) and len(response) == 1
            status, prop = response["D:current-user-principal"]
            assert status == 200 and len(prop) == 1
            element = prop.find(xmlutils.make_clark("D:href"))
            assert element is not None and element.text == "/owner/"
            assert "ICAL:calendar-color" not in response

    def test_sharing_api_map_move(self) -> None:
        """share-by-map API usage tests related to MOVE."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        path_user = "/user/calendarM.ics/"
        path_mapped1 = "/owner/calendar1M.ics/"
        path_mapped1r = "/owner/calendar1MR.ics/"
        path_mapped2 = "/owner/calendar2M.ics/"
        path_shared1_r = "/user/calendar1M-shared-by-owner-r.ics/"
        path_shared1_rw = "/user/calendar1M-shared-by-owner-rw.ics/"
        path_shared2_rw = "/user/calendar2M-shared-by-owner-rw.ics/"

        logging.info("\n*** prepare and test access")
        self.mkcalendar(path_mapped1, login="owner:ownerpw")
        event = get_file_content("event1.ics")
        self.put(os.path.join(path_mapped1, "event1.ics"), event, login="owner:ownerpw")

        self.mkcalendar(path_mapped1r, login="owner:ownerpw")

        self.mkcalendar(path_mapped2, login="owner:ownerpw")
        event = get_file_content("event2.ics")
        self.put(os.path.join(path_mapped2, "event2.ics"), event, login="owner:ownerpw")

        self.mkcalendar(path_user, login="user:userpw")
        event = get_file_content("event3.ics")
        self.put(os.path.join(path_user, "event3.ics"), event, login="user:userpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # check GET as owner
            logging.info("\n*** GET mapped1/event1 as owner (init) -> ok")
            _, headers, answer = self.request("GET", os.path.join(path_mapped1, "event1.ics"), check=200, login="owner:ownerpw")

            logging.info("\n*** GET mapped2/event2 as owner (init) -> ok")
            _, headers, answer = self.request("GET", os.path.join(path_mapped2, "event2.ics"), check=200, login="owner:ownerpw")

            # check MOVE as owner
            logging.info("\n*** MOVE event1 to mapped2 as owner -> ok")
            self.request("MOVE", os.path.join(path_mapped1, "event1.ics"), check=201,
                         login="owner:ownerpw",
                         HTTP_DESTINATION="http://127.0.0.1/"+os.path.join(path_mapped2, "event1.ics"))

            logging.info("\n*** GET mapped2/event1 as owner (after move) -> ok")
            _, headers, answer = self.request("GET", os.path.join(path_mapped2, "event1.ics"), check=200, login="owner:ownerpw")

            # check GET as user
            logging.info("\n*** GET event1 as user -> 404")
            _, headers, answer = self.request("GET", os.path.join(path_shared1_r, "event1.ics"), check=404, login="user:userpw")

            logging.info("\n*** GET event2 as user -> 404")
            _, headers, answer = self.request("GET", os.path.join(path_shared2_rw, "event2.ics"), check=404, login="user:userpw")

            # create map
            logging.info("\n*** create map user/owner:r -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped1r
            json_dict['PathOrToken'] = path_shared1_r
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** create map user/owner:rw -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped1
            json_dict['PathOrToken'] = path_shared1_rw
            json_dict['Permissions'] = "rw"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** create map user/owner:rw -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped2
            json_dict['PathOrToken'] = path_shared2_rw
            json_dict['Permissions'] = "rw"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # check MOVE as user
            logging.info("\n*** MOVE event1 of shared1 to shared2 as user -> 404 (not enabled)")
            self.request("MOVE", os.path.join(path_shared1_r, "event1.ics"), check=404,
                         login="user:userpw",
                         HTTP_DESTINATION="http://127.0.0.1/"+os.path.join(path_shared2_rw, "event1.ics"))

            logging.info("\n*** MOVE event1 of shared2 to shared1 as user -> 404 (not enabled)")
            self.request("MOVE", os.path.join(path_shared2_rw, "event1.ics"), check=404,
                         login="user:userpw",
                         HTTP_DESTINATION="http://127.0.0.1/"+os.path.join(path_shared1_r, "event1.ics"))

            # enable map by user
            logging.info("\n*** enable map shared1_r by user")
            json_dict = {}
            json_dict['PathMapped'] = path_mapped1r
            json_dict['PathOrToken'] = path_shared1_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** enable map shared1_rw by user")
            json_dict = {}
            json_dict['PathMapped'] = path_mapped1
            json_dict['PathOrToken'] = path_shared1_rw
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** enable map shared2_rw by user")
            json_dict = {}
            json_dict['PathMapped'] = path_mapped2
            json_dict['PathOrToken'] = path_shared2_rw
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            # check GET as user
            logging.info("\n*** GET event1 as user -> 404")
            _, headers, answer = self.request("GET", os.path.join(path_shared1_r, "event1.ics"), check=404, login="user:userpw")

            logging.info("\n*** GET event1 as user -> 404")
            _, headers, answer = self.request("GET", os.path.join(path_shared1_rw, "event1.ics"), check=404, login="user:userpw")

            logging.info("\n*** GET event1 as user -> ok")
            _, headers, answer = self.request("GET", os.path.join(path_shared2_rw, "event1.ics"), check=200, login="user:userpw")

            # check MOVE as user between shares
            logging.info("\n*** MOVE event1 of shared1_r to shared2_rw as user -> 403 (not permitted to move from r)")
            self.request("MOVE", os.path.join(path_shared1_r, "event1.ics"), check=403,
                         login="user:userpw",
                         HTTP_DESTINATION="http://127.0.0.1/"+os.path.join(path_shared2_rw, "event1.ics"))

            logging.info("\n*** MOVE event1 of shared2_rw to shared1_r as user -> 403 (not permitted to move to r)")
            self.request("MOVE", os.path.join(path_shared2_rw, "event1.ics"), check=403,
                         login="user:userpw",
                         HTTP_DESTINATION="http://127.0.0.1/"+os.path.join(path_shared1_r, "event1.ics"))

            logging.info("\n*** MOVE event1 of shared1_rw to shared2_rw as user -> 404 (already moved by owner)")
            self.request("MOVE", os.path.join(path_shared1_rw, "event1.ics"), check=404,
                         login="user:userpw",
                         HTTP_DESTINATION="http://127.0.0.1/"+os.path.join(path_shared2_rw, "event1.ics"))

            logging.info("\n*** MOVE event1 of shared2_rw to shared1_rw as user -> 201")
            self.request("MOVE", os.path.join(path_shared2_rw, "event1.ics"), check=201,
                         login="user:userpw",
                         HTTP_DESTINATION="http://127.0.0.1/"+os.path.join(path_shared1_rw, "event1.ics"))

            # check GET as user
            logging.info("\n*** GET event1 from r as user -> 404")
            _, headers, answer = self.request("GET", os.path.join(path_shared1_r, "event1.ics"), check=404, login="user:userpw")

            logging.info("\n*** GET event1 from 1/rw as user -> ok")
            _, headers, answer = self.request("GET", os.path.join(path_shared1_rw, "event1.ics"), check=200, login="user:userpw")

            logging.info("\n*** GET event1 from 2/rw as user -> 404")
            _, headers, answer = self.request("GET", os.path.join(path_shared2_rw, "event1.ics"), check=404, login="user:userpw")

            # check MOVE as user between shares and own calendar
            logging.info("\n*** GET event3 as user -> 200")
            _, headers, answer = self.request("GET", os.path.join(path_user, "event3.ics"), check=200, login="user:userpw")

            logging.info("\n*** GET event3 as user from shared2_rw -> 404")
            _, headers, answer = self.request("GET", os.path.join(path_shared2_rw, "event3.ics"), check=404, login="user:userpw")

            logging.info("\n*** MOVE event3 of own to shared2_rw as user -> 201")
            self.request("MOVE", os.path.join(path_user, "event3.ics"), check=201,
                         login="user:userpw",
                         HTTP_DESTINATION="http://127.0.0.1/"+os.path.join(path_shared2_rw, "event3.ics"))

            logging.info("\n*** GET event3 as user from shared2_rw -> 200")
            _, headers, answer = self.request("GET", os.path.join(path_shared2_rw, "event3.ics"), check=200, login="user:userpw")

            logging.info("\n*** GET event3 as user -> 404")
            _, headers, answer = self.request("GET", os.path.join(path_user, "event3.ics"), check=404, login="user:userpw")

            logging.info("\n*** MOVE event3 to own from shared2_rw as user -> 201")
            self.request("MOVE", os.path.join(path_shared2_rw, "event3.ics"), check=201,
                         login="user:userpw",
                         HTTP_DESTINATION="http://127.0.0.1/"+os.path.join(path_user, "event3.ics"))

    def test_sharing_api_update(self) -> None:
        """sharing API usage tests related to update."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "False",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})
        form_array: Sequence[str]
        json_dict: dict

        path_mapped1 = "/owner/calendar1U.ics/"
        path_mapped2 = "/owner/calendar2U.ics/"
        path_shared1 = "/user/calendar1U-shared-by-owner.ics/"

        logging.info("\n*** prepare and test access")
        self.mkcalendar(path_mapped1, login="owner:ownerpw")
        event = get_file_content("event1.ics")
        self.put(os.path.join(path_mapped1, "event1.ics"), event, login="owner:ownerpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # check GET as owner
            logging.info("\n*** GET mapped1 as owner (init) -> 200")
            _, headers, answer = self.request("GET", path_mapped1, check=200, login="owner:ownerpw")

            logging.info("\n*** GET shared1 as user (init) -> 404")
            _, headers, answer = self.request("GET", path_shared1, check=404, login="user:userpw")

            logging.info("\n*** create map user/owner:w -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped1
            json_dict['PathOrToken'] = path_shared1
            json_dict['Permissions'] = "w"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** GET shared1 as user (still not enabled by user) -> 404")
            _, headers, answer = self.request("GET", path_shared1, check=404, login="user:userpw")

            # enable map by user
            logging.info("\n*** enable map shared1 by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped1
            json_dict['PathOrToken'] = path_shared1
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** list/all (form->csv)")
            form_array = []
            _, headers, answer = self._sharing_api_form("map", "list", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer
            assert "Lines=1" in answer

            # read collection
            logging.info("\n*** GET shared1 as user (no read permissions set by owner) -> 403")
            _, headers, answer = self.request("GET", path_shared1, check=403, login="user:userpw")

            # update map
            logging.info("\n*** update map user/owner:r -> ok")
            json_dict = {}
            json_dict['PathMapped'] = path_mapped1
            json_dict['PathOrToken'] = path_shared1
            json_dict['Permissions'] = "r"
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** list/all (form->csv)")
            form_array = []
            _, headers, answer = self._sharing_api_form("map", "list", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status='success'" in answer
            assert "Lines=1" in answer

            # read collection
            logging.info("\n*** GET shared1 as user (read permissions set by owner) -> 200")
            _, headers, answer = self.request("GET", path_shared1, check=200, login="user:userpw")

            # update map
            logging.info("\n*** update map user/owner:path_mapped2 -> ok")
            json_dict = {}
            json_dict['PathMapped'] = path_mapped2
            json_dict['PathOrToken'] = path_shared1
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # read collection
            logging.info("\n*** GET shared1 as user (path not matching) -> 404")
            _, headers, answer = self.request("GET", path_shared1, check=404, login="user:userpw")

            logging.info("\n*** create mapped2 collection")
            self.mkcalendar(path_mapped2, login="owner:ownerpw")
            event = get_file_content("event2.ics")
            self.put(os.path.join(path_mapped2, "event2.ics"), event, login="owner:ownerpw")

            # read collection
            logging.info("\n*** GET shared1 as user (path now matching) -> 200")
            _, headers, answer = self.request("GET", path_shared1, check=200, login="user:userpw")

            # cleanup
            self.delete(path_mapped2, login="owner:ownerpw")

    def test_sharing_api_list_filter(self) -> None:
        """sharing API usage tests related to update."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "False",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})
        json_dict: dict

        path_user1 = "/user1/calendarLFu1.ics/"
        path_user2 = "/user2/calendarLFu2.ics/"
        path_user1_shared1 = "/user1/calendarLFo1-shared.ics/"
        path_user1_shared2 = "/user1/calendarLFo2-shared.ics/"
        path_user2_shared1 = "/user2/calendarLFo1-shared.ics/"
        path_owner1 = "/owner1/calendarLFo1.ics/"
        path_owner2 = "/owner2/calendarLFo2.ics/"

        logging.info("\n*** prepare")
        self.mkcalendar(path_owner1, login="owner1:owner1pw")
        self.mkcalendar(path_owner2, login="owner2:owner2pw")
        self.mkcalendar(path_user1, login="user1:user1pw")
        self.mkcalendar(path_user2, login="user2:user2pw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # list current
            logging.info("\n*** list owner1 -> empty")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "not-found"

            logging.info("\n*** list owner2 -> empty")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner2:owner2pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "not-found"

            logging.info("\n*** list user1 -> empty")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="user1:user1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "not-found"

            logging.info("\n*** list user2 -> empty")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="user2:user2pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "not-found"

            # create map#1
            logging.info("\n*** create map user1/owner1 -> ok")
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_owner1
            json_dict['PathOrToken'] = path_user1_shared1
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** list owner1")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1

            logging.info("\n*** list user1")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="user1:user1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1

            # create map#2
            logging.info("\n*** create map user1/owner2 -> ok")
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_owner2
            json_dict['PathOrToken'] = path_user1_shared2
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner2:owner2pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** list user1 -> 2 entries")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="user1:user1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 2

            # create map#3
            logging.info("\n*** create map user2/owner1 -> ok")
            json_dict = {}
            json_dict['User'] = "user2"
            json_dict['PathMapped'] = path_owner1
            json_dict['PathOrToken'] = path_user2_shared1
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** list owner1 -> 2 entries")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 2

            logging.info("\n*** list user1 filter for PathMapped -> 1 entries")
            json_dict = {}
            json_dict['PathMapped'] = path_owner1
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="user1:user1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1

            logging.info("\n*** list user1 filter for PathShared -> 1 entries")
            json_dict = {}
            json_dict['PathOrToken'] = path_user1_shared1
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="user1:user1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1

    def test_sharing_api_create_conflict(self) -> None:
        """sharing API usage tests related to conflicts."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "False",
                                    "rights_rule_doesnt_match_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        rights_file_path = os.path.join(self.colpath, "rights")
        with open(rights_file_path, "w") as f:
            f.write("""\
[default-collection]
user: .+
collection: .+
permissions: RrWw
[default]
user: .+
collection: {user}(/.*)?
permissions: RrWw""")
        self.configure({"rights": {"file": rights_file_path}})

        json_dict: dict

        path_user1 = "/user1/calendarCCu1.ics/"
        path_user2 = "/user2/calendarCCu2.ics/"
        path_user1_shared1 = "/user1/calendarCCo1-shared.ics/"
        path_user2_shared1 = "/user2/calendarCCo1-shared.ics/"
        path_owner1 = "/owner1/calendarCCo1.ics/"
        path_owner2 = "/owner2/calendarCCo2.ics/"

        logging.info("\n*** prepare")
        self.mkcalendar(path_owner1, login="owner1:owner1pw")
        self.mkcalendar(path_owner2, login="owner2:owner2pw")
        self.mkcalendar(path_user1, login="user1:user1pw")
        self.mkcalendar(path_user2, login="user2:user2pw")

        # create calendar a 2nd time
        logging.info("\n*** mkcalendar user2 -> conflict")
        self.mkcalendar(path_user2, login="user2:user2pw", check=409)

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # owner_only
            self.configure({"rights": {"type": "owner_only"}})

            # create map
            logging.info("\n*** create map user1/owner1 -> ok")
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_owner1
            json_dict['PathOrToken'] = path_user1_shared1
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** mkcalendar as user1 for user1/shared1 -> conflict")
            self.mkcalendar(path_user1_shared1, login="user1:user1pw", check=409)

            # create map
            logging.info("\n*** create map user2/owner1 -> ok")
            json_dict = {}
            json_dict['User'] = "user2"
            json_dict['PathMapped'] = path_owner1
            json_dict['PathOrToken'] = path_user2_shared1
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** mkcol as user2 for user2/shared1 -> conflict")
            self.mkcalendar(path_user2_shared1, login="user2:user2pw", check=409)

            # create map
            logging.info("\n*** create map user2/owner2 -> 409")
            json_dict = {}
            json_dict['User'] = "user2"
            json_dict['PathMapped'] = path_owner1
            json_dict['PathOrToken'] = path_user2
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=409, login="owner1:owner1pw", json_dict=json_dict)

            # from_file
            self.configure({"rights": {"type": "from_file"}})

            logging.info("\n*** mkcalendar as user1 for user2/shared1 with rights from file -> conflict")
            self.mkcalendar(path_user2_shared1, login="user1:user1pw", check=409)

            logging.info("\n*** mkcol as user1 for user2/shared1 with rights from file -> conflict")
            self.mkcol(path_user2_shared1, login="user1:user1pw", check=409)

    def test_sharing_api_permissions_global(self) -> None:
        """sharing API usage tests related to global permissions."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "False",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})
        json_dict: dict

        path_user1 = "/user1/calendarPGu1.ics/"
        path_owner1 = "/owner1/calendarPGo1.ics/"

        logging.info("\n*** prepare")
        self.mkcalendar(path_owner1, login="owner1:owner1pw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # create map
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_owner1
            json_dict['PathOrToken'] = path_user1

            logging.info("\n*** create map user1/owner1 but globally disabled -> 403")
            self.configure({"sharing": {"permit_create_map": "False"}})
            _, headers, answer = self._sharing_api_json("map", "create", check=403, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1 but globally enabled -> 200")
            self.configure({"sharing": {"permit_create_map": "True"}})
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            # create token
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_owner1

            logging.info("\n*** create token owner1 but globally disabled -> 403")
            self.configure({"sharing": {"permit_create_token": "False"}})
            _, headers, answer = self._sharing_api_json("token", "create", check=403, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create token owner1 but globally enabled -> 200")
            self.configure({"sharing": {"permit_create_token": "True"}})
            _, headers, answer = self._sharing_api_json("token", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

    def test_sharing_api_permissions_rights(self) -> None:
        """sharing API usage tests related to rights permissions."""
        rights_file_path = os.path.join(self.colpath, "rights")
        with open(rights_file_path, "w") as f:
            f.write("""\
[default-collection]
user: .+
collection: {user}
permissions: RrWw
[owner1-T]
user: owner1
collection: {user}/cal-T-uc(/.*)?
permissions: RrWwT
[owner1-t]
user: owner1
collection: {user}/cal-t-lc(/.*)?
permissions: RrWwt
[owner1-M]
user: owner1
collection: {user}/cal-M-uc(/.*)?
permissions: RrWwM
[owner1-m]
user: owner1
collection: {user}/cal-m-lc(/.*)?
permissions: RrWwm
[owner1-P]
user: owner1
collection: {user}/cal-P-uc(/.*)?
permissions: RrWwP
[owner1-p]
user: owner1
collection: {user}/cal-p-lc(/.*)?
permissions: RrWwp
[default]
user: .+
collection: {user}(/.*)?
permissions: RrWw""")

        self.configure({"rights": {"file": rights_file_path}})
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "rights_rule_doesnt_match_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "from_file"}})

        json_dict: dict

        path_user1 = "/user1/calendarPGu1.ics/"
        path_owner1_T = "/owner1/cal-T-uc/"
        path_owner1_t = "/owner1/cal-t-lc/"
        path_owner1_M = "/owner1/cal-M-uc/"
        path_owner1_m = "/owner1/cal-m-lc/"
        path_owner1_P = "/owner1/cal-P-uc/"
        path_owner1_p = "/owner1/cal-p-lc/"

        logging.info("\n*** prepare")
        self.mkcalendar(path_owner1_T, login="owner1:owner1pw")
        self.mkcalendar(path_owner1_t, login="owner1:owner1pw")
        self.mkcalendar(path_owner1_M, login="owner1:owner1pw")
        self.mkcalendar(path_owner1_m, login="owner1:owner1pw")
        self.mkcalendar(path_owner1_P, login="owner1:owner1pw")
        self.mkcalendar(path_owner1_p, login="owner1:owner1pw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # create map
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathOrToken'] = path_user1

            logging.info("\n*** create map user1/owner1, globally disabled")
            self.configure({"sharing": {"permit_create_map": "False"}})

            logging.info("\n*** create map user1/owner1, globally disabled / not granted M -> 403")
            json_dict['PathMapped'] = path_owner1_M
            json_dict['PathOrToken'] = path_user1.replace(".ics", "dM-uc" + db_type + ".ics")
            _, headers, answer = self._sharing_api_json("map", "create", check=403, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1, globally disabled / not granted T -> 403")
            json_dict['PathMapped'] = path_owner1_T
            json_dict['PathOrToken'] = path_user1.replace(".ics", "dT-uc" + db_type + ".ics")
            _, headers, answer = self._sharing_api_json("map", "create", check=403, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1, globally disabled / not granted t -> 403")
            json_dict['PathMapped'] = path_owner1_t
            json_dict['PathOrToken'] = path_user1.replace(".ics", "dt-lc" + db_type + ".ics")
            _, headers, answer = self._sharing_api_json("map", "create", check=403, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1, globally disabled / granted m -> 200")
            json_dict['PathMapped'] = path_owner1_m
            json_dict['PathOrToken'] = path_user1.replace(".ics", "dm-lc" + db_type + ".ics")
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** delete map user1/owner1, globally disabled / granted m -> 200")
            json_dict['PathMapped'] = path_owner1_m
            json_dict['PathOrToken'] = path_user1.replace(".ics", "dm-lc" + db_type + ".ics")
            _, headers, answer = self._sharing_api_json("map", "delete", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1, globally enabled")
            self.configure({"sharing": {"permit_create_map": "True"}})

            logging.info("\n*** create map user1/owner1, globally enabled / not granted M -> 403")
            json_dict['PathMapped'] = path_owner1_M
            json_dict['PathOrToken'] = path_user1.replace(".ics", "eM-uc" + db_type + ".ics")
            _, headers, answer = self._sharing_api_json("map", "create", check=403, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1, globally enabled / ignore T -> 200")
            json_dict['PathMapped'] = path_owner1_T
            json_dict['PathOrToken'] = path_user1.replace(".ics", "eT-uc" + db_type + ".ics")
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1, globally enabled / ignore t -> 200")
            json_dict['PathMapped'] = path_owner1_t
            json_dict['PathOrToken'] = path_user1.replace(".ics", "et-lc" + db_type + ".ics")
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1, globally enabled / ignore m -> 200")
            json_dict['PathMapped'] = path_owner1_m
            json_dict['PathOrToken'] = path_user1.replace(".ics", "em-lc" + db_type + ".ics")
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            # create token
            json_dict = {}

            logging.info("\n*** create token owner1, globally disabled")
            self.configure({"sharing": {"permit_create_token": "False"}})

            logging.info("\n*** create token owner1, globally disabled / not granted M -> 403")
            json_dict['PathMapped'] = path_owner1_M
            _, headers, answer = self._sharing_api_json("token", "create", check=403, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create token owner1, globally disabled / not granted m -> 403")
            json_dict['PathMapped'] = path_owner1_m
            _, headers, answer = self._sharing_api_json("token", "create", check=403, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create token owner1, globally disabled / not granted T -> 403")
            json_dict['PathMapped'] = path_owner1_T
            _, headers, answer = self._sharing_api_json("token", "create", check=403, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create token owner1, globally disabled / granted t -> 200")
            json_dict['PathMapped'] = path_owner1_t
            _, headers, answer = self._sharing_api_json("token", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create token owner1, globally enabled")
            self.configure({"sharing": {"permit_create_token": "True"}})

            logging.info("\n*** create token owner1, globally enabled / ignore M -> 200")
            json_dict['PathMapped'] = path_owner1_M
            _, headers, answer = self._sharing_api_json("token", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create token owner1, globally enabled / ignore m -> 200")
            json_dict['PathMapped'] = path_owner1_m
            _, headers, answer = self._sharing_api_json("token", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create token owner1, globally enabled / not granted T -> 403")
            json_dict['PathMapped'] = path_owner1_T
            _, headers, answer = self._sharing_api_json("token", "create", check=403, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create token owner1, globally enabled / ignore t -> 200")
            json_dict['PathMapped'] = path_owner1_t
            _, headers, answer = self._sharing_api_json("token", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** check PROPFIND privileges list on collections directly: RADICALE:share-token T (permit=True)")
            privileges_T = self._propfind_privileges(path_owner1_T, login="owner1:owner1pw")
            assert "RADICALE:share-token" in privileges_T

            logging.info("\n*** check PROPFIND privileges list on collections directly: RADICALE:share-token t (permit=True)")
            privileges_t = self._propfind_privileges(path_owner1_t, login="owner1:owner1pw")
            assert "RADICALE:share-token" not in privileges_t

            logging.info("\n*** check PROPFIND privileges list on collections directly: RADICALE:share-token * (permit=True)")
            privileges_p = self._propfind_privileges(path_owner1_p, login="owner1:owner1pw")
            assert "RADICALE:share-token" in privileges_p

            logging.info("\n*** check PROPFIND privileges list on collections directly: RADICALE:share-map M (permit=True)")
            privileges_M = self._propfind_privileges(path_owner1_M, login="owner1:owner1pw")
            assert "RADICALE:share-map" in privileges_M

            logging.info("\n*** check PROPFIND privileges list on collections directly: RADICALE:share-map m (permit=True)")
            privileges_m = self._propfind_privileges(path_owner1_m, login="owner1:owner1pw")
            assert "RADICALE:share-map" not in privileges_m

            logging.info("\n*** check PROPFIND privileges list on collections directly: RADICALE:share-map * (permit=True)")
            privileges_t = self._propfind_privileges(path_owner1_t, login="owner1:owner1pw")
            assert "RADICALE:share-map" in privileges_t

            self.configure({"sharing": {"permit_create_token": "False", "permit_create_map": "False"}})

            logging.info("\n*** check PROPFIND privileges list on collections directly: RADICALE:share-token T (permit=False)")
            privileges_T = self._propfind_privileges(path_owner1_T, login="owner1:owner1pw")
            assert "RADICALE:share-token" in privileges_T

            logging.info("\n*** check PROPFIND privileges list on collections directly: RADICALE:share-token t (permit=False)")
            privileges_t = self._propfind_privileges(path_owner1_t, login="owner1:owner1pw")
            assert "RADICALE:share-token" not in privileges_t

            logging.info("\n*** check PROPFIND privileges list on collections directly: RADICALE:share-token * (permit=False)")
            privileges_t = self._propfind_privileges(path_owner1_t, login="owner1:owner1pw")
            assert "RADICALE:share-token" not in privileges_t

            logging.info("\n*** check PROPFIND privileges list on collections directly: RADICALE:share-map M (permit=False)")
            privileges_M = self._propfind_privileges(path_owner1_M, login="owner1:owner1pw")
            assert "RADICALE:share-map" in privileges_M

            logging.info("\n*** check PROPFIND privileges list on collections directly: RADICALE:share-map m (permit=False)")
            privileges_m = self._propfind_privileges(path_owner1_m, login="owner1:owner1pw")
            assert "RADICALE:share-map" not in privileges_m

            logging.info("\n*** check PROPFIND privileges list on collections directly: RADICALE:share-map * (permit=False)")
            privileges_t = self._propfind_privileges(path_owner1_t, login="owner1:owner1pw")
            assert "RADICALE:share-map" not in privileges_t

            # continue
            self.configure({"sharing": {"permit_create_token": "True", "permit_create_map": "True"}})

            logging.info("\n*** check PROPFIND privileges list on collections directly by owner")
            privileges_P = self._propfind_privileges(path_owner1_P, login="owner1:owner1pw")
            assert "D:write-properties" in privileges_P

            privileges_p = self._propfind_privileges(path_owner1_p, login="owner1:owner1pw")
            assert "D:write-properties" in privileges_p

            logging.info("\n*** check PROPFIND privileges list on collections directly by user")

            logging.info("\n*** create map user1/owner1 P -> 200")
            path_share = path_user1.replace(".ics", "P-uc" + db_type + ".ics")
            json_dict = {}
            json_dict['PathMapped'] = path_owner1_P
            json_dict['Hidden'] = False
            json_dict['Enabled'] = True
            json_dict['User'] = "user1"
            json_dict['Permissions'] = "r"
            json_dict['PathOrToken'] = path_share
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user1:user1pw", json_dict=json_dict)
            _, headers, answer = self._sharing_api_json("map", "unhide", check=200, login="user1:user1pw", json_dict=json_dict)

            logging.info("\n*** check PROPFIND privileges list on collections directly by user: rights=P r (permit_properties_overlay=False)")
            self.configure({"sharing": {"permit_properties_overlay": "False"}})
            privileges_P = self._propfind_privileges(path_share, login="user1:user1pw")
            assert "D:write-properties" in privileges_P

            logging.info("\n*** check PROPFIND privileges list on collections directly by user: r (permit_properties_overlay=True)")
            self.configure({"sharing": {"permit_properties_overlay": "True"}})
            privileges_P = self._propfind_privileges(path_share, login="user1:user1pw")
            assert "D:write-properties" in privileges_P

            logging.info("\n*** update map with illegal combination pP")
            json_dict = {}
            json_dict['PathMapped'] = path_owner1_P
            json_dict['PathOrToken'] = path_share
            json_dict['User'] = "user1"
            json_dict['Permissions'] = "rpP"
            _, headers, answer = self._sharing_api_json("map", "update", check=400, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** update map with illegal combination eE")
            json_dict = {}
            json_dict['PathMapped'] = path_owner1_P
            json_dict['PathOrToken'] = path_share
            json_dict['User'] = "user1"
            json_dict['Permissions'] = "reE"
            _, headers, answer = self._sharing_api_json("map", "update", check=400, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** update map with only p")
            json_dict = {}
            json_dict['PathMapped'] = path_owner1_p
            json_dict['PathOrToken'] = path_share
            json_dict['User'] = "user1"
            json_dict['Permissions'] = "rp"
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** check PROPFIND privileges list on collections directly by user: rights=P rp (permit_properties_overlay=False)")
            self.configure({"sharing": {"permit_properties_overlay": "False"}})
            privileges_P = self._propfind_privileges(path_share, login="user1:user1pw")
            assert "D:write-properties" not in privileges_P

            logging.info("\n*** check PROPFIND privileges list on collections directly by user: rights=P rp (permit_properties_overlay=True)")
            self.configure({"sharing": {"permit_properties_overlay": "True"}})
            privileges_P = self._propfind_privileges(path_share, login="user1:user1pw")
            assert "D:write-properties" not in privileges_P

            json_dict = {}
            json_dict['PathMapped'] = path_owner1_P
            json_dict['PathOrToken'] = path_share
            json_dict['User'] = "user1"
            _, headers, answer = self._sharing_api_json("map", "delete", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1 p -> 200")
            path_share = path_user1.replace(".ics", "p-lc" + db_type + ".ics")
            json_dict = {}
            json_dict['PathMapped'] = path_owner1_p
            json_dict['Hidden'] = False
            json_dict['Enabled'] = True
            json_dict['User'] = "user1"
            json_dict['Permissions'] = "r"
            json_dict['PathOrToken'] = path_share
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user1:user1pw", json_dict=json_dict)
            _, headers, answer = self._sharing_api_json("map", "unhide", check=200, login="user1:user1pw", json_dict=json_dict)

            logging.info("\n*** check PROPFIND privileges list on collections directly by user: rights=p r (permit_properties_overlay=False)")
            self.configure({"sharing": {"permit_properties_overlay": "False"}})
            privileges_p = self._propfind_privileges(path_share, login="user1:user1pw")
            assert "D:write-properties" not in privileges_p

            logging.info("\n*** check PROPFIND privileges list on collections directly by user: rights=p r (permit_properties_overlay=True)")
            self.configure({"sharing": {"permit_properties_overlay": "True"}})
            privileges_p = self._propfind_privileges(path_share, login="user1:user1pw")
            assert "D:write-properties" not in privileges_p

            json_dict = {}
            json_dict['PathMapped'] = path_owner1_p
            json_dict['PathOrToken'] = path_share
            json_dict['User'] = "user1"
            json_dict['Permissions'] = "rP"
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** check PROPFIND privileges list on collections directly by user: rights=p rP (permit_properties_overlay=False)")
            self.configure({"sharing": {"permit_properties_overlay": "False"}})
            privileges_P = self._propfind_privileges(path_share, login="user1:user1pw")
            assert "D:write-properties" in privileges_P

            logging.info("\n*** check PROPFIND privileges list on collections directly by user: rights=p rP (permit_properties_overlay=True)")
            self.configure({"sharing": {"permit_properties_overlay": "True"}})
            privileges_P = self._propfind_privileges(path_share, login="user1:user1pw")
            assert "D:write-properties" in privileges_P

    def test_sharing_api_permissions_default(self) -> None:
        """sharing API usage tests related to global permissions."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        path_owner1 = "/owner1/calendarPGo1.ics/"
        path_owner1 = "/owner1/calendarPGo1.ics/"
        path_owner2 = "/owner2/calendarPGo1.ics/"
        path_owner1_rw = "/owner1/calendarPGo1rw.ics/"
        path_owner1_RrWw = "/owner1/calendarPGo1RrWw.ics/"
        path_user1_r = "/user1/calendarPGu1-r.ics/"
        path_user1_rw = "/user1/calendarPGu1-rw.ics/"
        path_user1_RrWw = "/user1/calendarPGu1-RrWw.ics/"

        logging.info("\n*** prepare")
        self.mkcalendar(path_owner1, login="owner1:owner1pw")
        self.mkcalendar(path_owner1_rw, login="owner1:owner1pw")
        self.mkcalendar(path_owner1_RrWw, login="owner1:owner1pw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # create map
            self.configure({"sharing": {"default_permissions_create_map": "r"}})

            logging.info("\n*** create map user1/owner1 with path of owner 2-> 403")
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_owner2
            json_dict['PathOrToken'] = path_user1_r
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=403, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1 r -> 200")
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_owner1
            json_dict['PathOrToken'] = path_user1_r
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            # enable map by user
            logging.info("\n*** enable map by user1")
            json_dict = {}
            json_dict['PathOrToken'] = path_user1_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user1:user1pw", json_dict=json_dict)

            logging.info("\n*** list (json->json)")
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['Permissions'] == "r"

            # check PROPFIND/privileges item as user
            logging.info("\n*** PROPFIND/privileges item as user")
            privileges_list = self._propfind_privileges(path_user1_r, login="user1:user1pw")
            assert "D:read" in privileges_list
            assert "D:write-content" not in privileges_list
            assert "D:write-properties" not in privileges_list
            assert "D:write" not in privileges_list
            assert "D:all" not in privileges_list

            logging.info("\n*** create map user1/owner1 rw -> 200")
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_owner1_rw
            json_dict['PathOrToken'] = path_user1_rw
            json_dict['Permissions'] = "rw"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** list (json->json)")
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['Permissions'] == "rw"

            # enable map by user
            logging.info("\n*** enable map by user1")
            json_dict = {}
            json_dict['PathOrToken'] = path_user1_rw
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user1:user1pw", json_dict=json_dict)

            # check PROPFIND/privileges item as user
            logging.info("\n*** PROPFIND/privileges item as user")
            privileges_list = self._propfind_privileges(path_user1_rw, login="user1:user1pw")
            assert "D:read" in privileges_list
            assert "D:write-content" in privileges_list
            assert "D:write-properties" not in privileges_list
            assert "D:write" not in privileges_list
            assert "D:all" not in privileges_list

            logging.info("\n*** create map user1/owner1 with adjusted default permissions -> 200")
            self.configure({"sharing": {"default_permissions_create_map": "RrWw"}})
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_owner1_RrWw
            json_dict['PathOrToken'] = path_user1_RrWw
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** list (json->json)")
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['Permissions'] == "RrWw"

            # create token
            self.configure({"sharing": {"default_permissions_create_token": "r"}})

            json_dict = {}
            json_dict['PathMapped'] = path_owner1

            logging.info("\n*** create token user1/owner1 r -> 200")
            _, headers, answer = self._sharing_api_json("token", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            Token = answer_dict['PathOrToken']

            logging.info("\n*** list (json->json)")
            json_dict['PathOrToken'] = Token
            _, headers, answer = self._sharing_api_json("token", "list", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['Permissions'] == "r"

            logging.info("\n*** create token user1/owner1 rw -> 200")
            json_dict['Permissions'] = "rw"
            del json_dict['PathOrToken']
            _, headers, answer = self._sharing_api_json("token", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            Token = answer_dict['PathOrToken']

            logging.info("\n*** list (json->json)")
            del json_dict['Permissions']
            json_dict['PathOrToken'] = Token
            _, headers, answer = self._sharing_api_json("token", "list", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['Permissions'] == "rw"

            logging.info("\n*** create token user1/owner1 with adjusted default permissions -> 200")
            self.configure({"sharing": {"default_permissions_create_token": "RrWw"}})
            del json_dict['PathOrToken']
            _, headers, answer = self._sharing_api_json("token", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            Token = answer_dict['PathOrToken']

            logging.info("\n*** list (json->json)")
            json_dict['PathOrToken'] = Token
            _, headers, answer = self._sharing_api_json("token", "list", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['Permissions'] == "RrWw"

    def test_sharing_api_map_report_base(self) -> None:
        """share-by-map API usage tests related to report."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "permit_properties_overlay": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        path_mapped = "/owner/abook1.vcf/"
        path_shared_r = "/user/abook-shared-by-owner.vcf/"

        logging.info("\n*** prepare and test access")
        self.create_addressbook(path_mapped, login="owner:ownerpw")
        contact = get_file_content("contact1.vcf")
        path_mapped_item = path_mapped + "contact.vcf"
        path_shared_item = path_shared_r + "contact.vcf"
        self.put(path_mapped_item, contact, login="owner:ownerpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # create map
            logging.info("\n*** create map user/owner:r -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # enable map by user
            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            # check REPORT as owner
            logging.info("\n*** REPORT collection owner -> ok")
            _, responses = self.report(path_mapped, """\
<?xml version="1.0"?>
<CR:addressbook-multiget xmlns="DAV:" xmlns:CR="urn:ietf:params:xml:ns:carddav">
   <prop>
     <getetag />
     <CR:address-data />
   </prop>
   <href>""" + path_mapped_item + """</href>
</CR:addressbook-multiget>""", login="owner:ownerpw")
            assert len(responses) == 1
            logging.info("response: %r", responses)
            response = responses[path_mapped_item]
            assert isinstance(response, dict)
            status, prop = response["D:getetag"]
            assert status == 200 and prop.text

            # check REPORT as user
            logging.info("\n*** REPORT collection user -> ok")
            _, responses = self.report(path_shared_r, """\
<?xml version="1.0"?>
<CR:addressbook-multiget xmlns="DAV:" xmlns:CR="urn:ietf:params:xml:ns:carddav">
   <prop>
     <getetag />
     <CR:address-data />
   </prop>
   <href>""" + path_shared_r + """</href>
</CR:addressbook-multiget>""", login="user:userpw")
            assert len(responses) == 1
            logging.info("response: %r", responses)
            response = responses[path_shared_item]
            assert isinstance(response, dict)
            status, prop = response["D:getetag"]
            assert status == 200 and prop.text

    def test_sharing_api_map_propfind_overlay_api_base(self) -> None:
        """share-by-map API usage tests related to proppatch."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "permit_properties_overlay": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        form_array: Sequence[str]
        json_dict: dict

        path_mapped = "/owner/calendarPFO.ics/"
        path_shared_r = "/user/calendarPFO-shared-by-owner-r.ics/"

        logging.info("\n*** prepare and test access")
        self.mkcalendar(path_mapped, login="owner:ownerpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # check PROPFIND as owner
            logging.info("\n*** PROPFIND collection owner -> ok")
            _, responses = self.propfind(path_mapped, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int) and len(response) == 1
            status, prop = response["D:current-user-principal"]
            assert status == 200 and len(prop) == 1
            element = prop.find(xmlutils.make_clark("D:href"))
            assert element is not None and element.text == "/owner/"

            # execute PROPPATCH as owner
            logging.info("\n*** PROPPATCH collection owner -> ok")
            _, responses = self.proppatch(path_mapped, """\
<?xml version="1.0" encoding="utf-8"?>
<D:propertyupdate xmlns:D="DAV:">
  <D:set>
    <D:prop>
      <I:calendar-color xmlns:I="http://apple.com/ns/ical/">#AAAAAA</I:calendar-color>
      <C:calendar-description xmlns:C="urn:ietf:params:xml:ns:caldav">ICAL-OWNER</C:calendar-description>
    </D:prop>
  </D:set>
</D:propertyupdate>""", login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int) and len(response) == 2
            status, prop = response["ICAL:calendar-color"]
            assert status == 200 and not prop.text
            status, prop = response["C:calendar-description"]
            assert status == 200 and not prop.text

            # verify PROPPATCH by owner
            logging.info("\n*** PROPFIND collection owner -> ok")
            propfind_calendar_color = get_file_content("propfind_multiple.xml")
            _, responses = self.propfind(path_mapped, propfind_calendar_color, login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int)
            status, prop = response["C:calendar-description"]
            logging.debug("calendar-description: %r", prop.text)
            assert status == 200 and prop.text == "ICAL-OWNER"
            status, prop = response["ICAL:calendar-color"]
            logging.debug("calendar-color: %r", prop.text)
            assert status == 200 and prop.text == "#AAAAAA"

            # create map
            logging.info("\n*** create map user/owner:r -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # enable map by user
            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            # verify PROPFIND as user
            logging.info("\n*** PROPFIND collection owner -> ok")
            propfind_calendar_color = get_file_content("propfind_multiple.xml")
            _, responses = self.propfind(path_mapped, propfind_calendar_color, login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int)
            status, prop = response["C:calendar-description"]
            logging.debug("calendar-description: %r", prop.text)
            assert status == 200 and prop.text == "ICAL-OWNER"
            status, prop = response["ICAL:calendar-color"]
            logging.debug("calendar-color: %r", prop.text)
            assert status == 200 and prop.text == "#AAAAAA"

            # update map by user
            logging.info("\n*** update map by user (json)")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Properties'] = {"C:calendar-description": "ICAL-USER", "ICAL:calendar-color": "#BBBBBB"}
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** list (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1

            logging.info("\n*** list (json->csv)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict, accept="text/csv")

            logging.info("\n*** list (json->txt)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict, accept="text/plain")

            # verify overlay as user
            logging.info("\n*** PROPFIND collection user (overlay) -> ok")
            propfind_calendar_color = get_file_content("propfind_multiple.xml")
            _, responses = self.propfind(path_shared_r, propfind_calendar_color, login="user:userpw")
            logging.info("response: %r", responses)
            response = responses[path_shared_r]
            assert not isinstance(response, int)
            status, prop = response["C:calendar-description"]
            logging.debug("calendar-description: %r", prop.text)
            assert status == 200 and prop.text == "ICAL-USER"
            status, prop = response["ICAL:calendar-color"]
            logging.debug("calendar-color: %r", prop.text)
            assert status == 200 and prop.text == "#BBBBBB"

            # verify overlay not visible by owner
            logging.info("\n*** PROPFIND collection owner -> ok")
            propfind_calendar_color = get_file_content("propfind_multiple.xml")
            _, responses = self.propfind(path_mapped, propfind_calendar_color, login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int)
            status, prop = response["C:calendar-description"]
            logging.debug("calendar-description: %r", prop.text)
            assert status == 200 and prop.text == "ICAL-OWNER"
            status, prop = response["ICAL:calendar-color"]
            logging.debug("calendar-color: %r", prop.text)
            assert status == 200 and prop.text == "#AAAAAA"

            # update map by user
            logging.info("\n*** update map by user (form)")
            form_array = []
            form_array.append("PathOrToken=" + path_shared_r)
            form_array.append("Properties='C:calendar-description'='ICAL-USER-NEW'")
            form_array.append("Properties='ICAL:calendar-color'='#CCCCCC'")
            _, headers, answer = self._sharing_api_form("map", "update", check=200, login="user:userpw", form_array=form_array)
            assert "Status='success'" in answer

            # verify overlay as user
            logging.info("\n*** PROPFIND collection user (overlay) -> ok")
            propfind_calendar_color = get_file_content("propfind_multiple.xml")
            _, responses = self.propfind(path_shared_r, propfind_calendar_color, login="user:userpw")
            logging.info("response: %r", responses)
            response = responses[path_shared_r]
            assert not isinstance(response, int)
            status, prop = response["C:calendar-description"]
            logging.debug("calendar-description: %r", prop.text)
            assert status == 200 and prop.text == "ICAL-USER-NEW"
            status, prop = response["ICAL:calendar-color"]
            logging.debug("calendar-color: %r", prop.text)
            assert status == 200 and prop.text == "#CCCCCC"

            # update map by user
            logging.info("\n*** update properties with buggyy ones by user (form)")
            form_array = ["User=" + "user"]
            form_array.append("PathOrToken=" + path_shared_r)
            form_array.append("Properties=BUGGYENTRY=BUGGYVALUE")
            _, headers, answer = self._sharing_api_form("map", "update", check=400, login="user:userpw", form_array=form_array)

    def test_sharing_api_map_propfind_overlay_api_delete(self) -> None:
        """share-by-map API usage tests related to proppatch."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "permit_properties_overlay": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        form_array: Sequence[str]
        json_dict: dict

        path_mapped = "/owner/calendarPFD.ics/"
        path_shared_r = "/user/calendarPFD-shared-by-owner-r.ics/"

        logging.info("\n*** prepare and test access")
        self.mkcalendar(path_mapped, login="owner:ownerpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # check PROPFIND as owner
            logging.info("\n*** PROPFIND collection owner -> ok")
            _, responses = self.propfind(path_mapped, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int) and len(response) == 1
            status, prop = response["D:current-user-principal"]
            assert status == 200 and len(prop) == 1
            element = prop.find(xmlutils.make_clark("D:href"))
            assert element is not None and element.text == "/owner/"

            # create map
            logging.info("\n*** create map user/owner:r -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # enable map by user
            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            # set properties by user
            logging.info("\n*** set properties by user (form)")
            form_array = []
            form_array.append("PathOrToken=" + path_shared_r)
            form_array.append("Properties='ICAL:calendar-color'='#CCCCCC'")
            _, headers, answer = self._sharing_api_form("map", "update", check=200, login="user:userpw", form_array=form_array)

            # check that properties are existing in map
            logging.info("\n*** list and check for properties (json->json)")
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="user:userpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['Properties']['ICAL:calendar-color'] == '#CCCCCC'

            # verify overlay as user
            logging.info("\n*** PROPFIND collection user (overlay) -> ok")
            propfind_calendar_color = get_file_content("propfind_calendar_color.xml")
            _, responses = self.propfind(path_shared_r, propfind_calendar_color, login="user:userpw")
            logging.info("response: %r", responses)
            response = responses[path_shared_r]
            assert not isinstance(response, int)
            status, prop = response["ICAL:calendar-color"]
            logging.debug("calendar-color: %r", prop.text)
            assert status == 200 and prop.text == "#CCCCCC"

            # clear properties by user
            logging.info("\n*** clear properties by user (form)")
            form_array = []
            form_array.append("PathOrToken=" + path_shared_r)
            form_array.append("Properties=")
            _, headers, answer = self._sharing_api_form("map", "update", check=200, login="user:userpw", form_array=form_array)

            # check that properties are cleared
            logging.info("\n*** list and check for cleared properties (json->json)")
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="user:userpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['Properties'] is not None

            # verify overlay as user
            logging.info("\n*** PROPFIND collection user (overlay no longer exists) -> ok")
            propfind_calendar_color = get_file_content("propfind_calendar_color.xml")
            _, responses = self.propfind(path_shared_r, propfind_calendar_color, login="user:userpw")
            logging.info("response: %r", responses)
            response = responses[path_shared_r]
            assert not isinstance(response, int)
            status, prop = response["ICAL:calendar-color"]
            logging.debug("calendar-color: %r", prop.text)
            assert status == 404

    def test_sharing_api_map_propfind_overlay_api_permissions(self) -> None:
        """share-by-map API usage tests related to proppatch."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        path_mapped = "/owner/calendarPFOAP.ics/"
        path_shared_r = "/user/calendarPFOAP-shared-by-owner-r.ics/"

        logging.info("\n*** prepare and test access")
        self.mkcalendar(path_mapped, login="owner:ownerpw")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # check PROPFIND as owner
            logging.info("\n*** PROPFIND collection owner -> ok")
            _, responses = self.propfind(path_mapped, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int) and len(response) == 1
            status, prop = response["D:current-user-principal"]
            assert status == 200 and len(prop) == 1
            element = prop.find(xmlutils.make_clark("D:href"))
            assert element is not None and element.text == "/owner/"

            # execute PROPPATCH as owner
            logging.info("\n*** PROPPATCH collection owner -> ok")
            self._proppatch_calendar_color(path_mapped, login="owner:ownerpw", color="#AAAAAA")

            # verify PROPPATCH by owner
            logging.info("\n*** PROPFIND collection owner (verify collection change) -> ok")
            color = self._propfind_calendar_color(path_mapped, login="owner:ownerpw")
            assert color == "#AAAAAA"

            # create map
            logging.info("\n*** create map user/owner:r -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** list (json->json) db=" + db_type)
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['Permissions'] == "r"

            # enable map by user
            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** list after enable (json->json) db=" + db_type)
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['Permissions'] == "r"

            # verify overlay as user
            logging.info("\n*** PROPFIND collection user (overlay, color back to owner) -> ok")
            color = self._propfind_calendar_color(path_shared_r, login="user:userpw")
            assert color == "#AAAAAA"

            self.configure({"sharing": {"permit_properties_overlay": False}})

            # update map by user
            logging.info("\n*** update map by user (json) -> 403 (no overlay permitted)")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Properties'] = {"ICAL:calendar-color": "#BBBBBB"}
            _, headers, answer = self._sharing_api_json("map", "update", check=403, login="user:userpw", json_dict=json_dict)

            self.configure({"sharing": {"permit_properties_overlay": True}})

            logging.info("\n*** update map by user (json) -> 200 (overlay permitted)")
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="user:userpw", json_dict=json_dict)

            # verify overlay as user
            logging.info("\n*** PROPFIND collection user (overlay) -> ok")
            color = self._propfind_calendar_color(path_shared_r, login="user:userpw")
            assert color == "#BBBBBB"

            # one property have to be visible
            logging.info("\n*** list check for one property (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert 'ICAL:calendar-color' in answer_dict['Content'][0]['Properties']
            assert answer_dict['Content'][0]['Properties']['ICAL:calendar-color'] == "#BBBBBB"

            # update map by owner
            logging.info("\n*** update map by owner (disable property overlay)")
            json_dict = {}
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "rp"
            json_dict['User'] = "user"
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** list after update by owner (json->json) db=" + db_type)
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['Permissions'] == "rp"

            logging.info("\n*** update map by user (json) -> 403 (no overlay permitted by share permissions)")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Properties'] = {"ICAL:calendar-color": "#CCCCCC"}
            _, headers, answer = self._sharing_api_json("map", "update", check=403, login="user:userpw", json_dict=json_dict)

            # one property have to be visible
            logging.info("\n*** list check for one property (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert 'ICAL:calendar-color' in answer_dict['Content'][0]['Properties']
            assert answer_dict['Content'][0]['Properties']['ICAL:calendar-color'] == "#BBBBBB"

            # verify overlay as user
            logging.info("\n*** PROPFIND collection user (overlay) -> ok")
            color = self._propfind_calendar_color(path_shared_r, login="user:userpw")
            assert color == "#BBBBBB"

            # update map by owner
            logging.info("\n*** update map by owner (disable property overlay)")
            json_dict = {}
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "rP"
            json_dict['User'] = "user"
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            # one property have to be visible
            logging.info("\n*** list check for one property (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert 'ICAL:calendar-color' in answer_dict['Content'][0]['Properties']
            assert answer_dict['Content'][0]['Properties']['ICAL:calendar-color'] == "#BBBBBB"

            logging.info("\n*** update map by user (json) -> 200 (overlay permitted by share permissions)")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Properties'] = {"ICAL:calendar-color": "#CCCCCC"}
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="user:userpw", json_dict=json_dict)

            # verify overlay as user
            logging.info("\n*** PROPFIND collection user (overlay) -> ok")
            color = self._propfind_calendar_color(path_shared_r, login="user:userpw")
            assert color == "#CCCCCC"

            self.configure({"sharing": {"permit_properties_overlay": True}})

            # update map by owner
            logging.info("\n*** update map by owner (disable property overlay)")
            json_dict = {}
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "rp"
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            # one property have to be visible
            logging.info("\n*** list check for one property (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert 'ICAL:calendar-color' in answer_dict['Content'][0]['Properties']
            assert answer_dict['Content'][0]['Properties']['ICAL:calendar-color'] == "#CCCCCC"

            logging.info("\n*** update map by user (json) -> 403 (overlay permitted but denied by share permissions)")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Properties'] = {"ICAL:calendar-color": "#EEEEEE"}
            _, headers, answer = self._sharing_api_json("map", "update", check=403, login="user:userpw", json_dict=json_dict)

    def test_sharing_api_map_propfind_overlay_proppatch(self) -> None:
        """share-by-map API usage tests related to proppatch."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": "True",
                                    "permit_create_token": "True",
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        logging.info("\n*** prepare and test access")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            path_mapped = "/owner/calendarPFP-" + db_type + ".ics/"
            path_shared_r = "/user/calendarPFP-shared-by-owner-r-" + db_type + ".ics/"
            self.mkcalendar(path_mapped, login="owner:ownerpw")

            # check PROPFIND as owner
            logging.info("\n*** PROPFIND collection owner -> ok")
            _, responses = self.propfind(path_mapped, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int) and len(response) == 1
            status, prop = response["D:current-user-principal"]
            assert status == 200 and len(prop) == 1
            element = prop.find(xmlutils.make_clark("D:href"))
            assert element is not None and element.text == "/owner/"

            # execute PROPPATCH as owner
            logging.info("\n*** PROPPATCH collection owner -> ok")
            self._proppatch_calendar_color(path_mapped, login="owner:ownerpw", color="#AAAAAA")

            # verify PROPPATCH by owner
            logging.info("\n*** PROPFIND collection owner (verify collection change) -> ok")
            color = self._propfind_calendar_color(path_mapped, login="owner:ownerpw")
            assert color == "#AAAAAA"

            # create map
            logging.info("\n*** create map user/owner:rP -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "rP"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # enable map by user
            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            # check PROPFIND/privileges item as user
            logging.info("\n*** PROPFIND/privileges item as user -> calendar")
            privileges_list = self._propfind_privileges(path_shared_r, login="user:userpw")
            assert "D:read" in privileges_list
            assert "D:write-content" not in privileges_list
            assert "D:write-properties" in privileges_list
            assert "D:write" not in privileges_list
            assert "D:all" not in privileges_list

            # verify PROPPATCH as user
            logging.info("\n*** PROPFIND collection user -> color #AAAAAA")
            color = self._propfind_calendar_color(path_shared_r, login="user:userpw")
            assert color == "#AAAAAA"

            # execute PROPPATCH as user
            logging.info("\n*** PROPPATCH collection user -> ok")
            self._proppatch_calendar_color(path_shared_r, login="user:userpw", color="#BBBBBB")

            logging.info("\n*** list (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1

            logging.info("\n*** list (json->csv)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict, accept="text/csv")

            logging.info("\n*** list (json->txt)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict, accept="text/plain")

            # verify overlay as user
            logging.info("\n*** PROPFIND collection user (overlay) -> ok")
            color = self._propfind_calendar_color(path_shared_r, login="user:userpw")
            assert color == "#BBBBBB"

            # verify overlay not visible by owner
            logging.info("\n*** PROPFIND collection owner (no collection change) -> ok")
            color = self._propfind_calendar_color(path_mapped, login="owner:ownerpw")
            assert color == "#AAAAAA"

            # execute PROPPATCH as user (delete color)
            logging.info("\n*** PROPPATCH collection user (delete color) -> ok")
            self._proppatch_calendar_color_remove(path_shared_r, login="user:userpw")

            # verify overlay as user
            logging.info("\n*** PROPFIND collection user (overlay, color back to owner) -> ok")
            color = self._propfind_calendar_color(path_shared_r, login="user:userpw")
            assert color == "#AAAAAA"

            # update map by owner
            logging.info("\n*** update map by owner (disable property overlay)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "rwe"
            json_dict['User'] = "user"
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            # execute PROPPATCH as user
            logging.info("\n*** PROPPATCH collection user (set color/collection) -> ok")
            self._proppatch_calendar_color(path_shared_r, login="user:userpw", color="#DDDDDD")

            # verify overlay as user
            logging.info("\n*** PROPFIND collection user (collection color changed) -> ok")
            color = self._propfind_calendar_color(path_shared_r, login="user:userpw")
            assert color == "#DDDDDD"

            # verify overlay visible by owner
            logging.info("\n*** PROPFIND collection owner (visible change by user) -> ok")
            color = self._propfind_calendar_color(path_mapped, login="owner:ownerpw")
            assert color == "#DDDDDD"

            # update map by owner
            logging.info("\n*** update map by owner (enable property overlay)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "rwE"
            json_dict['User'] = "user"
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            # execute PROPPATCH as user
            logging.info("\n*** PROPPATCH collection user (set color rw, enforce overlay enabled by default) -> ok")
            self._proppatch_calendar_color(path_shared_r, login="user:userpw", color="#EEEEEE")

            # verify overlay visible by owner
            logging.info("\n*** PROPFIND collection owner (invisible change by user) -> ok")
            color = self._propfind_calendar_color(path_mapped, login="owner:ownerpw")
            assert color == "#DDDDDD"

            # verify overlay as user
            logging.info("\n*** PROPFIND collection user (overlay: color) -> ok")
            color = self._propfind_calendar_color(path_shared_r, login="user:userpw")
            assert color == "#EEEEEE"

            # update map by owner
            logging.info("\n*** update map by owner (enable property overlay)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "rwe"
            json_dict['User'] = "user"
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            # execute PROPPATCH as user
            logging.info("\n*** PROPPATCH collection user (set color rwe, enforce overlay enabled by default) -> ok")
            self._proppatch_calendar_color(path_shared_r, login="user:userpw", color="#EEEE00")

            # verify overlay visible by owner
            logging.info("\n*** PROPFIND collection owner (visible change) -> ok")
            color = self._propfind_calendar_color(path_mapped, login="owner:ownerpw")
            assert color == "#EEEE00"

            self.configure({"sharing": {"enforce_properties_overlay": False}})

            # update map by owner
            logging.info("\n*** update map by owner (enable property overlay)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "rw"
            json_dict['User'] = "user"
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** PROPPATCH collection user (set color rwe but enforce disabled) -> ok")
            self._proppatch_calendar_color(path_shared_r, login="user:userpw", color="#FFFFFF")

            # verify visible by owner
            logging.info("\n*** PROPFIND collection owner (visible change) -> ok")
            color = self._propfind_calendar_color(path_mapped, login="owner:ownerpw")
            assert color == "#FFFFFF"

    def test_sharing_api_map_propfind_overlay_partial(self) -> None:
        """share-by-map API usage tests related to partial overlay."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_create_token": True,
                                    "permit_properties_overlay": "True",
                                    "enforce_properties_overlay": "True",
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        logging.info("\n*** prepare and test access")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            path_mapped = "/owner/calendarPFP-" + db_type + ".ics/"
            path_shared_r = "/user/calendarPFP-shared-by-owner-r-" + db_type + ".ics/"
            self.mkcalendar(path_mapped, login="owner:ownerpw")

            # check PROPFIND as owner
            logging.info("\n*** PROPFIND collection owner -> ok")
            _, responses = self.propfind(path_mapped, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int) and len(response) == 1
            status, prop = response["D:current-user-principal"]
            assert status == 200 and len(prop) == 1
            element = prop.find(xmlutils.make_clark("D:href"))
            assert element is not None and element.text == "/owner/"

            # execute PROPPATCH color as owner
            logging.info("\n*** PROPPATCH color collection owner -> ok")
            self._proppatch_calendar_color(path_mapped, login="owner:ownerpw", color="#AAAAAA")

            # verify PROPPATCH color by owner
            logging.info("\n*** PROPFIND color collection owner (verify collection change) -> ok")
            color = self._propfind_calendar_color(path_mapped, login="owner:ownerpw")
            assert color == "#AAAAAA"

            # execute PROPPATCH description as owner
            logging.info("\n*** PROPPATCH description collection owner -> ok")
            self._proppatch_calendar_description(path_mapped, login="owner:ownerpw", description="OWNER")

            # verify PROPPATCH description by owner
            logging.info("\n*** PROPFIND description collection owner (verify collection change) -> ok")
            description = self._propfind_calendar_description(path_mapped, login="owner:ownerpw")
            assert description == "OWNER"

            # create map
            logging.info("\n*** create map user/owner:rP -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "rP"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # enable map by user
            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            # verify PROPPATCH as user
            logging.info("\n*** PROPFIND color collection user -> #AAAAAA")
            color = self._propfind_calendar_color(path_shared_r, login="user:userpw")
            assert color == "#AAAAAA"

            logging.info("\n*** PROPFIND description collection collection user -> ok")
            description = self._propfind_calendar_description(path_shared_r, login="user:userpw")
            assert description == "OWNER"

            # execute PROPPATCH color as user
            logging.info("\n*** PROPPATCH color collection user -> ok")
            self._proppatch_calendar_color(path_shared_r, login="user:userpw", color="#BBBBBB")

            # one property has to be visible
            logging.info("\n*** list (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert 'ICAL:calendar-color' in answer_dict['Content'][0]['Properties']
            assert answer_dict['Content'][0]['Properties']['ICAL:calendar-color'] == "#BBBBBB"

            # execute PROPPATCH description as user
            logging.info("\n*** PROPPATCH description collection user -> ok")
            self._proppatch_calendar_description(path_shared_r, login="user:userpw", description="USER")

            # both properties have to be visible
            logging.info("\n*** list check for both properties (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert 'ICAL:calendar-color' in answer_dict['Content'][0]['Properties']
            assert answer_dict['Content'][0]['Properties']['ICAL:calendar-color'] == "#BBBBBB"
            assert 'C:calendar-description' in answer_dict['Content'][0]['Properties']
            assert answer_dict['Content'][0]['Properties']['C:calendar-description'] == "USER"

            # verify PROPPATCH as user
            logging.info("\n*** PROPFIND color collection user -> #BBBBBB")
            color = self._propfind_calendar_color(path_shared_r, login="user:userpw")
            assert color == "#BBBBBB"

            logging.info("\n*** PROPFIND description collection collection user -> ok")
            description = self._propfind_calendar_description(path_shared_r, login="user:userpw")
            assert description == "USER"

            # execute PROPPATCH DELETE description as user
            logging.info("\n*** PROPPATCH DELETE description collection user -> ok")
            self._proppatch_calendar_description_remove(path_shared_r, login="user:userpw")

            # one property has to survive
            logging.info("\n*** list check for still one property (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert 'ICAL:calendar-color' in answer_dict['Content'][0]['Properties']
            assert answer_dict['Content'][0]['Properties']['ICAL:calendar-color'] == "#BBBBBB"

            # set properties by user using API
            logging.info("\n*** set properties by user color overwrite (form)")
            form_array = []
            form_array.append("PathOrToken=" + path_shared_r)
            form_array.append("Properties='ICAL:calendar-color'='#CCCCCC'")
            _, headers, answer = self._sharing_api_form("map", "update", check=200, login="user:userpw", form_array=form_array)

            # one property has to survive
            logging.info("\n*** list check for still one property (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert 'ICAL:calendar-color' in answer_dict['Content'][0]['Properties']
            assert answer_dict['Content'][0]['Properties']['ICAL:calendar-color'] == "#CCCCCC"
            assert 'C:calendar-description' not in answer_dict['Content'][0]['Properties']

            # set property by user using API
            logging.info("\n*** set properties by user description extension (form)")
            form_array = []
            form_array.append("PathOrToken=" + path_shared_r)
            form_array.append("Properties='C:calendar-description'='USER-OWNER'")
            _, headers, answer = self._sharing_api_form("map", "update", check=200, login="user:userpw", form_array=form_array)

            # both properties have to be visible
            logging.info("\n*** list check for both properties (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert 'ICAL:calendar-color' in answer_dict['Content'][0]['Properties']
            assert answer_dict['Content'][0]['Properties']['ICAL:calendar-color'] == "#CCCCCC"
            assert 'C:calendar-description' in answer_dict['Content'][0]['Properties']
            assert answer_dict['Content'][0]['Properties']['C:calendar-description'] == "USER-OWNER"

            # delete property by user using API
            logging.info("\n*** delete property by user color (form)")
            form_array = []
            form_array.append("PathOrToken=" + path_shared_r)
            form_array.append("Properties='ICAL:calendar-color'=''")
            _, headers, answer = self._sharing_api_form("map", "update", check=200, login="user:userpw", form_array=form_array)

            # only one property has to be visible
            logging.info("\n*** list check for single properties (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert 'ICAL:calendar-color' not in answer_dict['Content'][0]['Properties']
            assert 'C:calendar-description' in answer_dict['Content'][0]['Properties']
            assert answer_dict['Content'][0]['Properties']['C:calendar-description'] == "USER-OWNER"

            # clear all propertie by user using API
            logging.info("\n*** delete property by user color (form)")
            form_array = []
            form_array.append("PathOrToken=" + path_shared_r)
            form_array.append("Properties=")
            _, headers, answer = self._sharing_api_form("map", "update", check=200, login="user:userpw", form_array=form_array)

            # no property has to be visible
            logging.info("\n*** list check empty properties (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert 'ICAL:calendar-color' not in answer_dict['Content'][0]['Properties']
            assert 'C:calendar-description' not in answer_dict['Content'][0]['Properties']

            # set properties by user using API
            logging.info("\n*** set properties by user (json)")
            json_dict = {}
            json_dict["PathOrToken"] = path_shared_r
            json_dict["Properties"] = {'C:calendar-description': 'USER-OWNER', 'ICAL:calendar-color': '#DDDDDD'}
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="user:userpw", json_dict=json_dict)

            # both properties have to be visible
            logging.info("\n*** list check for both properties (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert 'ICAL:calendar-color' in answer_dict['Content'][0]['Properties']
            assert 'C:calendar-description' in answer_dict['Content'][0]['Properties']

            # delete on property by user using API
            logging.info("\n*** delete property by user color (json)")
            json_dict = {}
            json_dict["PathOrToken"] = path_shared_r
            json_dict["Properties"] = {'C:calendar-description': ''}
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="user:userpw", json_dict=json_dict)

            # one property have to be visible
            logging.info("\n*** list check for one property (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert 'ICAL:calendar-color' in answer_dict['Content'][0]['Properties']
            assert 'C:calendar-description' not in answer_dict['Content'][0]['Properties']

            # delete all propertie by user using API
            logging.info("\n*** delete all properties by user (json)")
            json_dict = {}
            json_dict["PathOrToken"] = path_shared_r
            json_dict["Properties"] = {}
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="user:userpw", json_dict=json_dict)

            # no property has to be visible
            logging.info("\n*** list check empty properties (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert 'ICAL:calendar-color' not in answer_dict['Content'][0]['Properties']
            assert 'C:calendar-description' not in answer_dict['Content'][0]['Properties']

    def test_sharing_api_map_vcf_bday_basic(self) -> None:
        """share-by-map with conversion=bday basic tests."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_properties_overlay": "True",
                                    "enforce_properties_overlay": "True",
                                    "collection_by_map": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "response_header_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        logging.info("\n*** prepare and test access")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            path_mapped = "/owner/adressbook-" + db_type + ".vcf/"
            path_shared_r = "/user/calendar-bday-abook-shared-by-owner-r-" + db_type + ".ics/"
            self.create_addressbook(path_mapped, login="owner:ownerpw")

            contact = get_file_content("contact1.vcf")
            path = path_mapped + "/contact1.vcf"
            self.put(path, contact, login="owner:ownerpw")

            contact = get_file_content("contact2-with-bday.vcf")
            path = path_mapped + "/contact2-with-bday.vcf"
            self.put(path, contact, login="owner:ownerpw")

            contact = get_file_content("contact3-with-bday.vcf")
            path = path_mapped + "/contact3-with-bday.vcf"
            self.put(path, contact, login="owner:ownerpw")

            # check PROPFIND as owner
            logging.info("\n*** PROPFIND collection owner -> ok")
            _, responses = self.propfind(path_mapped, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
<propname />
</propfind>""", login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int)
            assert "CR:supported-address-data" in response

            # execute GET as owner
            logging.info("\n*** GET VCF collection owner -> ok")
            _, headers, answer = self.request("GET", path_mapped, login="owner:ownerpw")
            assert "contact1" in answer
            assert "contact2" in answer
            # title from fallback
            assert 'Content-Disposition' in headers
            assert 'Address%20book.vcf' in headers['Content-Disposition']

            # create map with unsupported permissions
            logging.info("\n*** create map(bday) user/owner:r -> fail")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Conversion'] = "bday"
            json_dict['Permissions'] = "rw"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            json_dict['Properties'] = {"D:displayname": "Test-BDAY"}
            _, headers, answer = self._sharing_api_json("map", "create", check=405, login="owner:ownerpw", json_dict=json_dict)

            # create map
            logging.info("\n*** create map(bday) user/owner:r -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Conversion'] = "bday"
            json_dict['Permissions'] = "rP"
            json_dict['Enabled'] = True
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            json_dict['Properties'] = {"D:displayname": "Test-BDAY"}
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # enable map by user
            logging.info("\n*** enable map(bday) by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            # list by user
            logging.info("\n*** list by user")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="user:userpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            row = answer_dict['Content'][0]
            assert row['ShareType'] == "map"
            assert row['Conversion'] == "bday"

            # check PROPFIND item as user
            logging.info("\n*** PROPFIND item as user -> calendar")
            response = self._propfind_allprop(path_shared_r, login="user:userpw")
            logging.debug("response: %r", response)
            assert "CR:supported-address-data" not in response
            assert "D:sync-token" not in response
            assert "C:supported-calendar-component-set" in response
            assert "D:current-user-privilege-set" in response

            # check PROPFIND/privileges item as user
            logging.info("\n*** PROPFIND/privileges item as user -> calendar")
            privileges_list = self._propfind_privileges(path_shared_r, login="user:userpw")
            assert "D:read" in privileges_list
            assert "D:write-content" not in privileges_list
            assert "D:write-properties" in privileges_list
            assert "D:write" not in privileges_list
            assert "D:all" not in privileges_list

            # verify content as user
            logging.info("\n*** GET collection user -> ok")
            _, headers, answer = self.request("GET", path_shared_r, login="user:userpw")
            assert "BEGIN:VCARD" not in answer
            assert "BEGIN:VCALENDAR" in answer
            assert "RRULE:FREQ=YEARLY" in answer
            assert "DTSTART;VALUE=DATE:19700101" in answer
            assert "DTEND;VALUE=DATE:19700102" in answer
            assert "TRANSP:TRANSPARENT" in answer
            assert "DESCRIPTION:BDAY=1970-01-01" in answer
            # content type must be adjusted
            assert 'Content-Type' in headers
            assert 'text/calendar' in headers['Content-Type']
            # title from Properties
            assert 'Content-Disposition' in headers
            assert 'Test-BDAY.ics' in headers['Content-Disposition']

            # verify report as user
            logging.info("\n*** REPORT collection user -> ok")
            _, responses = self.report(path_shared_r, """\
<?xml version="1.0" encoding="utf-8" ?>
<C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav">
    <D:prop xmlns:D="DAV:">
        <D:getetag/>
    </D:prop>
</C:calendar-query>""", login="user:userpw")
            logging.debug("resonses: %r", responses)
            assert path_shared_r + "contact2-with-bday.ics" in responses
            assert path_shared_r + "contact3-with-bday.ics" in responses
            assert path_shared_r + "contact1.ics" not in responses

            # get elements as user
            logging.info("\n*** REPORT collection entries user -> ok")
            _, responses = self.report(path_shared_r, """\
<?xml version="1.0"?>
<C:calendar-multiget xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
   <prop>
     <getetag />
     <C:calendar-data />
   </prop>
   <href>""" + path_shared_r + "contact2-with-bday.ics" + """</href>
   <href>""" + path_shared_r + "contact3-with-bday.ics" + """</href>
</C:calendar-multiget>""", login="user:userpw")
            logging.debug("resonses: %r", responses)
            assert path_shared_r + "contact2-with-bday.ics" in responses
            assert path_shared_r + "contact3-with-bday.ics" in responses
            assert path_shared_r + "contact1.ics" not in responses

            # timerange filter elements as user
            logging.info("\n*** REPORT collection entries with timerange user -> ok")
            _, responses = self.report(path_shared_r, """\
<?xml version="1.0"?>
 <C:calendar-query xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">
   <prop>
     <getcontenttype />
     <getetag />
     <C:calendar-data />
   </prop>
   <C:filter>
     <C:comp-filter name="VCALENDAR">
       <C:comp-filter name="VEVENT">
         <C:time-range start="20251124T000000Z" end="20260715T000000Z" />
       </C:comp-filter>
     </C:comp-filter>
   </C:filter>
</C:calendar-query>""", login="user:userpw")
            logging.debug("resonses: %r", responses)
            assert path_shared_r + "contact2-with-bday.ics" in responses
            assert path_shared_r + "contact3-with-bday.ics" in responses
            assert path_shared_r + "contact1.ics" not in responses

            logging.info("\n*** PROPFIND collection entries user -> ok")
            _, responses = self.propfind(path_shared_r, """\
<?xml version="1.0"?>
 <propfind xmlns="DAV:">
   <prop>
     <getcontenttype />
     <resourcetype />
     <getetag />
   </prop>
</propfind>""", login="user:userpw", HTTP_DEPTH="1")
            logging.debug("resonses: %r", responses)
            assert path_shared_r + "contact2-with-bday.ics" in responses
            assert path_shared_r + "contact3-with-bday.ics" in responses
            assert path_shared_r + "contact1.ics" not in responses
            response = responses[path_shared_r + "contact2-with-bday.ics"]
            assert not isinstance(response, int)
            status, prop = response["D:getcontenttype"]
            assert "text/calendar" in str(prop.text)

    def test_sharing_api_map_vcf_bday_complex(self) -> None:
        """share-by-map with conversion=bday complex tests."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_properties_overlay": "True",
                                    "enforce_properties_overlay": "True",
                                    "collection_by_map": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        logging.info("\n*** prepare and test access")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            path_mapped = "/owner/adressbook-" + db_type + ".vcf/"
            path_user = "/user/"
            path_shared_bday = path_user + "calendar-bday-abook-shared-by-owner-r-" + db_type + ".ics/"
            path_shared_map = path_user + "abook-shared-by-owner-r-" + db_type + ".vcf/"
            self.create_addressbook(path_mapped, login="owner:ownerpw")

            contact = get_file_content("contact1.vcf")
            path = path_mapped + "/contact1.vcf"
            self.put(path, contact, login="owner:ownerpw")

            contact = get_file_content("contact2-with-bday.vcf")
            path = path_mapped + "/contact2-with-bday.vcf"
            self.put(path, contact, login="owner:ownerpw")

            contact = get_file_content("contact3-with-bday.vcf")
            path = path_mapped + "/contact3-with-bday.vcf"
            self.put(path, contact, login="owner:ownerpw")

            # check PROPFIND as owner
            logging.info("\n*** PROPFIND collection owner -> ok")
            _, responses = self.propfind(path_mapped, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
<propname />
</propfind>""", login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int)
            assert "CR:supported-address-data" in response

            # execute GET as owner
            logging.info("\n*** GET VCF collection owner -> ok")
            _, answer = self.get(path_mapped, login="owner:ownerpw")
            assert "contact1" in answer
            assert "contact2" in answer

            # create bday
            logging.info("\n*** create map(bday) user/owner:r -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_bday
            json_dict['Conversion'] = "bday"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # enable bday by user
            logging.info("\n*** enable map(bday) by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_bday
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            # unhide bday by user
            logging.info("\n*** unhide map(bday) by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_bday
            _, headers, answer = self._sharing_api_json("map", "unhide", check=200, login="user:userpw", json_dict=json_dict)

            # create map
            logging.info("\n*** create map user/owner:r -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_map
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # enable map by user
            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_map
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            # unhide map by user
            logging.info("\n*** unhide map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_map
            _, headers, answer = self._sharing_api_json("map", "unhide", check=200, login="user:userpw", json_dict=json_dict)

            # check PROPFIND item as user
            logging.info("\n*** PROPFIND all as user")
            _, responses = self.propfind(path_user, """\
<?xml version="1.0"?>
<propfind xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:CR="urn:ietf:params:xml:ns:carddav" xmlns:CS="http://calendarserver.org/ns/" xmlns:ICAL="http://apple.com/ns/ical/" xmlns:RADICALE="http://radicale.org/ns/" xmlns:ns3="http://inf-it.com/ns/ab/">
  <prop>
    <resourcetype />
    <RADICALE:displayname />
    <ICAL:calendar-color />
    <ns3:addressbook-color />
    <C:calendar-description />
    <C:supported-calendar-component-set />
    <CR:addressbook-description />
    <CS:source />
    <RADICALE:getcontentcount />
    <getcontentlength />
  </prop>
</propfind>""", login="user:userpw", HTTP_DEPTH="1")
            logging.debug("responses: %r", responses)
            response = responses[path_shared_map]
            assert not isinstance(response, int)
            logging.debug("response %r: %r", path_shared_map, response)
            assert "C:supported-calendar-component-set" in response
            response = responses[path_shared_bday]
            assert not isinstance(response, int)
            logging.debug("response %r: %r", path_shared_bday, response)
            assert "C:supported-calendar-component-set" in response

            # check PROPFIND item as user
            logging.info("\n*** PROPFIND all as user (reduced)")
            _, responses = self.propfind(path_user, """\
<?xml version="1.0"?>
<propfind xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:CR="urn:ietf:params:xml:ns:carddav" xmlns:CS="http://calendarserver.org/ns/" xmlns:ICAL="http://apple.com/ns/ical/" xmlns:RADICALE="http://radicale.org/ns/" xmlns:ns3="http://inf-it.com/ns/ab/">
  <prop>
    <resourcetype />
    <C:calendar-description />
    <CR:addressbook-description />
    <RADICALE:getcontentcount />
    <getcontentlength />
  </prop>
</propfind>""", login="user:userpw", HTTP_DEPTH="1")
            # logging.debug("responses: %r", responses)
            response = responses[path_shared_bday]
            assert not isinstance(response, int)
            logging.debug("response %r: %r", path_shared_bday, response)
            assert "D:getcontentlength" in response
            assert "RADICALE:getcontentcount" in response
            status, prop = response["D:getcontentlength"]
            assert int(str(prop.text)) > 600
            status, prop = response["RADICALE:getcontentcount"]
            assert int(str(prop.text)) == 2

    def test_sharing_api_map_vcf_bday_self(self) -> None:
        """share-by-map with conversion=bday to self tests."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": True,
                                    "permit_properties_overlay": "True",
                                    "enforce_properties_overlay": "True",
                                    "collection_by_map": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_header_on_debug": "True",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        logging.info("\n*** prepare and test access")

        path_owner = "/owner/"

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            path_mapped = path_owner + "abook-" + db_type + ".vcf/"
            path_shared = path_owner + "cal-bday-abook-" + db_type + ".ics/"
            self.create_addressbook(path_mapped, login="owner:ownerpw")

            contact = get_file_content("contact1.vcf")
            path = path_mapped + "/contact1.vcf"
            self.put(path, contact, login="owner:ownerpw")

            contact = get_file_content("contact2-with-bday.vcf")
            path = path_mapped + "/contact2-with-bday.vcf"
            self.put(path, contact, login="owner:ownerpw")

            contact = get_file_content("contact3-with-bday.vcf")
            path = path_mapped + "/contact3-with-bday.vcf"
            self.put(path, contact, login="owner:ownerpw")

            # check PROPFIND as owner
            logging.info("\n*** PROPFIND collection owner -> ok")
            _, responses = self.propfind(path_mapped, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
<propname />
</propfind>""", login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int)
            assert "CR:supported-address-data" in response

            # execute GET as owner
            logging.info("\n*** GET VCF collection owner -> ok")
            _, answer = self.get(path_mapped, login="owner:ownerpw")
            assert "contact1" in answer
            assert "contact2" in answer
            assert "NICKNAME-C3" in answer

            # create map
            logging.info("\n*** create bday owner to itself -> ok")
            json_dict = {}
            json_dict['User'] = "owner"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            json_dict['Conversion'] = "bday"
            json_dict['Enabled'] = False
            json_dict['Hidden'] = True
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)

            # check PROPFIND item as owner
            logging.info("\n*** PROPFIND all as owner")
            _, responses = self.propfind(path_owner, """\
<?xml version="1.0"?>
<propfind xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:CR="urn:ietf:params:xml:ns:carddav" xmlns:CS="http://calendarserver.org/ns/" xmlns:ICAL="http://apple.com/ns/ical/" xmlns:RADICALE="http://radicale.org/ns/" xmlns:ns3="http://inf-it.com/ns/ab/">
  <prop>
    <resourcetype />
    <RADICALE:displayname />
    <ICAL:calendar-color />
    <ns3:addressbook-color />
    <C:calendar-description />
    <C:supported-calendar-component-set />
    <CR:addressbook-description />
    <CS:source />
    <RADICALE:getcontentcount />
    <getcontentlength />
  </prop>
</propfind>""", login="owner:ownerpw", HTTP_DEPTH="1")
            # logging.debug("responses: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int)
            logging.debug("response %r: %r", path_mapped, response)
            assert "C:supported-calendar-component-set" in response
            assert path_shared not in responses

            # enable + unhide
            logging.info("\n*** enable+unhide bday owner to itself -> ok")
            json_dict = {}
            json_dict['PathOrToken'] = path_shared
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            # check PROPFIND item as owner
            logging.info("\n*** PROPFIND all as owner")
            _, responses = self.propfind(path_owner, """\
<?xml version="1.0"?>
<propfind xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:CR="urn:ietf:params:xml:ns:carddav" xmlns:CS="http://calendarserver.org/ns/" xmlns:ICAL="http://apple.com/ns/ical/" xmlns:RADICALE="http://radicale.org/ns/" xmlns:ns3="http://inf-it.com/ns/ab/">
  <prop>
    <resourcetype />
    <RADICALE:displayname />
    <ICAL:calendar-color />
    <ns3:addressbook-color />
    <C:calendar-description />
    <C:supported-calendar-component-set />
    <CR:addressbook-description />
    <CS:source />
    <RADICALE:getcontentcount />
    <getcontentlength />
  </prop>
</propfind>""", login="owner:ownerpw", HTTP_DEPTH="1")
            # logging.debug("responses: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int)
            logging.debug("response %r: %r", path_mapped, response)
            assert "C:supported-calendar-component-set" in response
            assert path_shared in responses

            # check PROPFIND item as owner
            logging.info("\n*** PROPFIND item as owner -> calendar")
            response = self._propfind_allprop(path_shared, login="owner:ownerpw")
            logging.debug("response: %r", response)
            assert "CR:supported-address-data" not in response
            assert "D:sync-token" not in response
            assert "C:supported-calendar-component-set" in response
            assert "D:current-user-privilege-set" in response

            # verify content as owner
            logging.info("\n*** GET collection owner -> ok")
            _, headers, answer = self.request("GET", path_shared, login="owner:ownerpw")
            assert 'Content-Type' in headers
            assert 'text/calendar' in headers['Content-Type']
            # title from default
            assert 'Content-Disposition' in headers
            assert 'Calendar.ics' in headers['Content-Disposition']

    def test_sharing_api_token_vcf_bday(self) -> None:
        """share-by-bday to a token tests."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_token": True,
                                    "permit_properties_overlay": "True",
                                    "enforce_properties_overlay": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_header_on_debug": "True",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        logging.info("\n*** prepare and test access")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})
            self.configure({"sharing": {"permit_properties_overlay": "True"}})

            path_mapped = "/owner/adressbook-" + db_type + ".vcf/"
            self.create_addressbook(path_mapped, login="owner:ownerpw")

            contact = get_file_content("contact1.vcf")
            path = path_mapped + "/contact1.vcf"
            self.put(path, contact, login="owner:ownerpw")

            contact = get_file_content("contact2-with-bday.vcf")
            path = path_mapped + "/contact2-with-bday.vcf"
            self.put(path, contact, login="owner:ownerpw")

            contact = get_file_content("contact3-with-bday.vcf")
            path = path_mapped + "/contact3-with-bday.vcf"
            self.put(path, contact, login="owner:ownerpw")

            # check PROPFIND as owner
            logging.info("\n*** PROPFIND collection owner -> ok")
            _, responses = self.propfind(path_mapped, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
<propname />
</propfind>""", login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int)
            assert "CR:supported-address-data" in response

            # execute GET as owner
            logging.info("\n*** GET VCF collection owner -> ok")
            _, answer = self.get(path_mapped, login="owner:ownerpw")
            assert "contact1" in answer
            assert "contact2" in answer
            assert "NICKNAME-C3" in answer

            # create map
            logging.info("\n*** create token with bday conversion (default permissions) -> ok")
            json_dict = {}
            json_dict['User'] = "owner"
            json_dict['PathMapped'] = path_mapped
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            json_dict['Conversion'] = "bday"
            _, headers, answer = self._sharing_api_json("token", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert "Status" in answer_dict
            assert "PathOrToken" in answer_dict
            Token = answer_dict["PathOrToken"]
            path_shared = Token

            # execute GET with token
            logging.info("\n*** GET bday with token")
            _, answer = self.get(path_shared)
            assert "VCARD" not in answer
            assert "Test-FN-C3 (BDAY)" in answer
            assert "Test-FN (BDAY)" in answer

            # verify content as owner
            logging.info("\n*** GET collection owner -> ok")
            _, headers, answer = self.request("GET", path_shared)
            assert 'Content-Type' in headers
            assert 'text/calendar' in headers['Content-Type']
            # title from default
            assert 'Content-Disposition' in headers
            assert 'Calendar.ics' in headers['Content-Disposition']

            # create map of ics with conversion -> fail
            logging.info("\n*** create token with bday conversion but unsupported permissions -> fail")
            json_dict = {}
            json_dict['User'] = "owner"
            json_dict['PathMapped'] = path_mapped
            json_dict['Enabled'] = True
            json_dict['Permissions'] = "rw"
            json_dict['Hidden'] = False
            json_dict['Conversion'] = "bday"
            _, headers, answer = self._sharing_api_json("token", "create", check=405, login="owner:ownerpw", json_dict=json_dict)

            # check PROPFIND item with token
            logging.info("\n*** PROPFIND item with token -> calendar")
            response = self._propfind_allprop(path_shared)
            logging.debug("response: %r", response)
            assert "CR:supported-address-data" not in response
            assert "D:sync-token" not in response
            assert "C:supported-calendar-component-set" in response
            assert "D:current-user-privilege-set" in response
            status, props = response["D:current-user-privilege-set"]
            privileges = props.findall(xmlutils.make_clark("D:privilege"))
            assert len(privileges) >= 1
            privileges_list = [xmlutils.make_human_tag(privilege.findall("*")[0].tag) for privilege in privileges]
            assert "D:read" in privileges_list
            assert "D:write-content" not in privileges_list
            assert "D:write-properties" not in privileges_list
            assert "D:write" not in privileges_list
            assert "D:all" not in privileges_list

            # execute PROPPATCH color as user
            logging.info("\n*** PROPPATCH color collection with token -> permission denied")
            color = "#BBBBBB"
            _, responses = self.proppatch(path=path_shared, data="""\
<?xml version="1.0" encoding="utf-8"?>
<D:propertyupdate xmlns:D="DAV:">
<D:set>
<D:prop>
  <I:calendar-color xmlns:I="http://apple.com/ns/ical/">""" + color + """</I:calendar-color>
</D:prop>
</D:set>
</D:propertyupdate>""", check=403)

            # update map
            logging.info("\n*** update token with bday conversion ("r" permissions) -> ok")
            json_dict = {}
            json_dict['User'] = "owner"
            json_dict['PathOrToken'] = path_shared
            json_dict['Permissions'] = "r"
            _, headers, answer = self._sharing_api_json("token", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** PROPFIND item with token -> calendar")
            response = self._propfind_allprop(path_shared)
            logging.debug("response: %r", response)
            status, props = response["D:current-user-privilege-set"]
            privileges = props.findall(xmlutils.make_clark("D:privilege"))
            assert len(privileges) >= 1
            privileges_list = [xmlutils.make_human_tag(privilege.findall("*")[0].tag) for privilege in privileges]
            assert "D:read" in privileges_list
            assert "D:write-content" not in privileges_list
            assert "D:write-properties" in privileges_list
            assert "D:write" not in privileges_list
            assert "D:all" not in privileges_list

            # execute PROPPATCH color as user
            logging.info("\n*** PROPPATCH color collection with token -> ok")
            color = "#BBBBBB"
            _, responses = self.proppatch(path=path_shared, data="""\
<?xml version="1.0" encoding="utf-8"?>
<D:propertyupdate xmlns:D="DAV:">
<D:set>
<D:prop>
  <I:calendar-color xmlns:I="http://apple.com/ns/ical/">""" + color + """</I:calendar-color>
</D:prop>
</D:set>
</D:propertyupdate>""", check=207)

            self.configure({"sharing": {"permit_properties_overlay": "False"}})

            logging.info("\n*** PROPFIND item with token (r) -> calendar")
            response = self._propfind_allprop(path_shared)
            logging.debug("response: %r", response)
            status, props = response["D:current-user-privilege-set"]
            privileges = props.findall(xmlutils.make_clark("D:privilege"))
            assert len(privileges) >= 1
            privileges_list = [xmlutils.make_human_tag(privilege.findall("*")[0].tag) for privilege in privileges]
            assert "D:read" in privileges_list
            assert "D:write-content" not in privileges_list
            assert "D:write-properties" not in privileges_list
            assert "D:write" not in privileges_list
            assert "D:all" not in privileges_list

            # execute PROPPATCH color as user
            logging.info("\n*** PROPPATCH color collection with token -> ok")
            color = "#BBBBBB"
            _, responses = self.proppatch(path=path_shared, data="""\
<?xml version="1.0" encoding="utf-8"?>
<D:propertyupdate xmlns:D="DAV:">
<D:set>
<D:prop>
  <I:calendar-color xmlns:I="http://apple.com/ns/ical/">""" + color + """</I:calendar-color>
</D:prop>
</D:set>
</D:propertyupdate>""", check=403)

            # update map to "rP"
            logging.info("\n*** update token with bday conversion ('rP' permissions) -> ok")
            json_dict = {}
            json_dict['User'] = "owner"
            json_dict['PathOrToken'] = path_shared
            json_dict['Permissions'] = "rP"
            _, headers, answer = self._sharing_api_json("token", "update", check=200, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** PROPFIND item with token -> calendar")
            response = self._propfind_allprop(path_shared)
            logging.debug("response: %r", response)
            status, props = response["D:current-user-privilege-set"]
            privileges = props.findall(xmlutils.make_clark("D:privilege"))
            assert len(privileges) >= 1
            privileges_list = [xmlutils.make_human_tag(privilege.findall("*")[0].tag) for privilege in privileges]
            assert "D:read" in privileges_list
            assert "D:write-content" not in privileges_list
            assert "D:write-properties" in privileges_list
            assert "D:write" not in privileges_list
            assert "D:all" not in privileges_list

            # execute PROPPATCH color as user
            logging.info("\n*** PROPPATCH color collection with token -> ok")
            color = "#BBBBBB"
            _, responses = self.proppatch(path=path_shared, data="""\
<?xml version="1.0" encoding="utf-8"?>
<D:propertyupdate xmlns:D="DAV:">
<D:set>
<D:prop>
  <I:calendar-color xmlns:I="http://apple.com/ns/ical/">""" + color + """</I:calendar-color>
</D:prop>
</D:set>
</D:propertyupdate>""", check=207)

            # update map to "rPe"
            logging.info("\n*** update token with bday conversion ('rPe' permissions) -> not supported")
            json_dict = {}
            json_dict['User'] = "owner"
            json_dict['PathOrToken'] = path_shared
            json_dict['Permissions'] = "rPe"
            _, headers, answer = self._sharing_api_json("token", "update", check=405, login="owner:ownerpw", json_dict=json_dict)

            # update map to "rPE"
            logging.info("\n*** update token with bday conversion ('rPE' permissions) -> not supported")
            json_dict = {}
            json_dict['User'] = "owner"
            json_dict['PathOrToken'] = path_shared
            json_dict['Permissions'] = "rPE"
            _, headers, answer = self._sharing_api_json("token", "update", check=405, login="owner:ownerpw", json_dict=json_dict)

            # update map Conversion
            logging.info("\n*** update token remove Conversion -> not supported")
            json_dict = {}
            json_dict['User'] = "owner"
            json_dict['PathOrToken'] = path_shared
            json_dict['Conversion'] = ""
            _, headers, answer = self._sharing_api_json("token", "update", check=400, login="owner:ownerpw", json_dict=json_dict)

    def test_sharing_api_token_ics_bday(self) -> None:
        """share-by-token ics with bday conversion (has to fail)."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_token": True,
                                    "permit_properties_overlay": "True",
                                    "enforce_properties_overlay": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_header_on_debug": "True",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        logging.info("\n*** prepare and test access")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            path_mapped = "/owner/calendar-" + db_type + ".ics/"
            self.mkcalendar(path_mapped, login="owner:ownerpw")

            # create map
            logging.info("\n*** create token of calendar with bday conversion -> fail")
            json_dict = {}
            json_dict['User'] = "owner"
            json_dict['PathMapped'] = path_mapped
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            json_dict['Conversion'] = "bday"
            _, headers, answer = self._sharing_api_json("token", "create", check=405, login="owner:ownerpw", json_dict=json_dict)

    def test_sharing_api_map_properies_overlay_unicode(self) -> None:
        """share-by-map API usage tests related to properties overlay using unicode."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": "True",
                                    "permit_create_token": "True",
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        logging.info("\n*** prepare and test access")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            path_mapped = "/owner/calendarPFP-" + db_type + ".ics/"
            path_shared_r = "/user/calendarPFP-shared-by-owner-r-" + db_type + ".ics/"
            self.mkcalendar(path_mapped, login="owner:ownerpw")

            # check PROPFIND as owner
            logging.info("\n*** PROPFIND collection owner -> ok")
            _, responses = self.propfind(path_mapped, """\
<?xml version="1.0" encoding="utf-8"?>
<propfind xmlns="DAV:">
    <prop>
        <current-user-principal />
    </prop>
</propfind>""", login="owner:ownerpw")
            logging.info("response: %r", responses)
            response = responses[path_mapped]
            assert not isinstance(response, int) and len(response) == 1
            status, prop = response["D:current-user-principal"]
            assert status == 200 and len(prop) == 1
            element = prop.find(xmlutils.make_clark("D:href"))
            assert element is not None and element.text == "/owner/"

            description_owner = "Test-Uni😀code-Single'Quote-UmÄlaut-Double\"Quote"
            description_user = 'Test-Uni😁code-Single\'Quote-Sßz-Double"quote'

            # execute PROPPATCH as owner
            logging.info("\n*** PROPPATCH collection owner -> ok")
            self._proppatch_calendar_description(path_mapped, login="owner:ownerpw", description=description_owner)

            # verify PROPPATCH by owner
            logging.info("\n*** PROPFIND collection owner (verify collection change) -> ok")
            description = self._propfind_calendar_description(path_mapped, login="owner:ownerpw")
            assert description == description_owner

            # create map
            logging.info("\n*** create map user/owner:rP -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "rP"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # enable map by user
            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            # verify PROPFIND as user
            logging.info("\n*** PROPFIND collection user")
            description = self._propfind_calendar_description(path_shared_r, login="user:userpw")
            assert description == description_owner

            # execute PROPPATCH as user
            logging.info("\n*** PROPPATCH collection user -> ok")
            self._proppatch_calendar_description(path_shared_r, login="user:userpw", description=description_user)
            self._proppatch_calendar_color(path_shared_r, login="user:userpw", color="#FFFFFF")

            logging.info("\n*** list (json->json)")
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1

            # verify overlay as user
            logging.info("\n*** PROPFIND collection user (overlay) -> ok")
            description = self._propfind_calendar_description(path_shared_r, login="user:userpw")
            assert description == description_user

            # verify overlay not visible by owner
            logging.info("\n*** PROPFIND collection owner (no collection change) -> ok")
            description = self._propfind_calendar_description(path_mapped, login="owner:ownerpw")
            assert description == description_owner

            # check properties file
            collection_props_path = os.path.join(self.colpath, "collection-root", path_mapped.removeprefix('/'), ".Radicale.props")
            logging.info("collection_props path: %r", collection_props_path)
            with open(collection_props_path) as f:
                props = json.load(f)
            logging.info("collection_props: %r", props)
            assert props['C:calendar-description'] == description_owner

            # reconfigure to trigger restart and reparsing of database
            self.configure({"auth": {"type": "htpasswd"}})

            # verify overlay as user
            logging.info("\n*** PROPFIND collection user (overlay) -> ok")
            description = self._propfind_calendar_description(path_shared_r, login="user:userpw")
            assert description == description_user

    @pytest.mark.skipif(not pathutils.path_supports_unicode(tempfile.mkdtemp()), reason="TEMP is not supporting unicode")
    def test_sharing_api_map_user_unicode(self) -> None:
        """share-by-map API usage tests related to properties overlay using unicode."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": "True",
                                    "permit_create_token": "True",
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        logging.info("\n*** prepare and test access")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            path_mapped = "/owner/calendarPFP-" + db_type + ".ics/"
            path_shared_r = "/us😀er/calendarPFP-shared-by-owner-r-" + db_type + ".ics/"
            self.mkcalendar(path_mapped, login="owner:ownerpw")

            # create map
            logging.info("\n*** create map user/owner:rP -> ok")
            json_dict = {}
            json_dict['User'] = "us😀er"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "rP"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # enable map by user
            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['User'] = "us😀er"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="us😀er:user😀pw", json_dict=json_dict)

    @pytest.mark.skipif(not pathutils.path_supports_unicode(tempfile.mkdtemp()), reason="TEMP is not supporting unicode")
    def test_sharing_api_map_path_unicode(self) -> None:
        """share-by-map API usage tests related to properties overlay using unicode."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": "True",
                                    "permit_create_token": "True",
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        logging.info("\n*** prepare and test access")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            path_mapped = "/owner/calendar😀PFP-" + db_type + ".ics/"
            path_shared_r = "/user/calendar😁PFP-shared-by-owner-r-" + db_type + ".ics/"
            self.mkcalendar(path_mapped, login="owner:ownerpw")

            # create map
            logging.info("\n*** create map user/owner:rP -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "rP"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # enable map by user
            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

    def test_sharing_api_map_strict_user_unicode(self) -> None:
        """share-by-map API usage tests related to properties overlay using unicode in user."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": "True",
                                    "permit_create_token": "True",
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "server": {"validate_user_value": "strict"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        logging.info("\n*** prepare and test access")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            path_mapped = "/owner/calendarPFP-" + db_type + ".ics/"
            path_shared_r = "/user/calendarPFP-shared-by-owner-r-" + db_type + ".ics/"
            self.mkcalendar(path_mapped, login="owner:ownerpw")

            # create map
            logging.info("\n*** create map user/owner:rP -> ok")
            json_dict = {}
            json_dict['User'] = "us😁er"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "rP"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=400, login="owner:ownerpw", json_dict=json_dict)

    def test_sharing_api_map_strict_path_unicode(self) -> None:
        """share-by-map API usage tests related to properties overlay using unicode in user."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "type": "csv",
                                    "permit_create_map": "True",
                                    "permit_create_token": "True",
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "logging": {"request_header_on_debug": "False",
                                    "response_content_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "server": {"validate_path_value": "strict"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        logging.info("\n*** prepare and test access")

        for db_type in list(filter(lambda item: item != "none", sharing.INTERNAL_TYPES)):
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            logging.info("\n*** create collection, already rejected in early state")
            path_mapped = "/owner/calendar😀PFP-" + db_type + ".ics/"
            path_shared_r = "/user/calendarPFP-shared-by-owner-r-" + db_type + ".ics/"
            self.mkcalendar(path_mapped, login="owner:ownerpw", check=400)

            logging.info("\n*** create collection")
            path_mapped = "/owner/calendarPFP-" + db_type + ".ics/"
            path_shared_r = "/user/calendar😁PFP-shared-by-owner-r-" + db_type + ".ics/"
            self.mkcalendar(path_mapped, login="owner:ownerpw")

            # create map
            logging.info("\n*** create map user/owner:rP -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "rP"
            json_dict['Enabled'] = True
            json_dict['Hidden'] = False
            _, headers, answer = self._sharing_api_json("map", "create", check=400, login="owner:ownerpw", json_dict=json_dict)
