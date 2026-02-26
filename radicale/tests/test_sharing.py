# This file is part of Radicale - CalDAV and CardDAV server
# Copyright © 2026-2026 Peter Bieringer <pb@bieringer.de>
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

import json
import logging
import os
import re
from typing import Dict, Sequence, Tuple, Union

from radicale import sharing, xmlutils
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
                    "owner2:owner2pw", "user2:user2pw"]
        htpasswd_content = "\n".join(htpasswd)
        with open(self.htpasswd_file_path, "w", encoding=encoding) as f:
            f.write(htpasswd_content)

    # Helper functions
    def _sharing_api(self, sharing_type: str, action: str, check: int, login: Union[str, None], data: str, content_type: str, accept: Union[str, None]) -> Tuple[int, Dict[str, str], str]:
        path_base = "/.sharing/v1/" + sharing_type + "/"
        _, headers, answer = self.request("POST", path_base + action, check=check, login=login, data=data, content_type=content_type, accept=accept)
        logging.info("received answer:\n%s", "\n".join(answer.splitlines()))
        return _, headers, answer

    def _sharing_api_form(self, sharing_type: str, action: str, check: int, login: Union[str, None], form_array: Sequence[str], accept: Union[str, None] = None) -> Tuple[int, Dict[str, str], str]:
        data = "&".join(form_array)
        content_type = "application/x-www-form-urlencoded"
        if accept is None:
            accept = "text/plain"
        _, headers, answer = self._sharing_api(sharing_type, action, check, login, data, content_type, accept)
        return _, headers, answer

    def _sharing_api_json(self, sharing_type: str, action: str, check: int, login: Union[str, None], json_dict: dict, accept: Union[str, None] = None) -> Tuple[int, Dict[str, str], str]:
        data = json.dumps(json_dict)
        content_type = "application/json"
        if accept is None:
            accept = "application/json"
        _, headers, answer = self._sharing_api(sharing_type, action, check, login, data, content_type, accept)
        return _, headers, answer

    # Test functions
    def test_sharing_api_base_no_auth(self) -> None:
        """POST request at '/.sharing' without authentication."""
        # disabled
        for path in ["/.sharing", "/.sharing/"]:
            _, headers, _ = self.request("POST", path, check=404)
        # enabled (permutations)
        self.configure({"sharing": {
                                    "collection_by_map": "True",
                                    "collection_by_token": "False"}
                        })
        path = "/.sharing/"
        _, headers, _ = self.request("POST", path, check=401)
        self.configure({"sharing": {
                                    "collection_by_map": "False",
                                    "collection_by_token": "True"}
                        })
        path = "/.sharing/"
        _, headers, _ = self.request("POST", path, check=401)
        self.configure({"sharing": {
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"}
                        })
        path = "/.sharing/"
        _, headers, _ = self.request("POST", path, check=401)

    def test_sharing_api_base_with_auth(self) -> None:
        """POST request at '/.sharing' with authentication."""
        self.configure({"auth": {"type": "htpasswd",
                                 "htpasswd_filename": self.htpasswd_file_path,
                                 "htpasswd_encryption": "plain"},
                        "sharing": {
                                    "collection_by_map": "True",
                                    "collection_by_token": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        # path with no valid API hook
        for path in ["/.sharing/", "/.sharing/v9/"]:
            _, headers, _ = self.request("POST", path, check=404, login="owner:ownerpw")

        # path with valid API but no hook
        for path in ["/.sharing/v1/"]:
            _, headers, _ = self.request("POST", path, check=404, login="owner:ownerpw")

        # path with valid API and hook but not enabled "map"
        self.configure({"sharing": {
                                    "collection_by_map": "False",
                                    "collection_by_token": "True"}
                        })
        sharetype = "map"
        for action in sharing.API_HOOKS_V1:
            path = "/.sharing/v1/" + sharetype + "/" + action
            _, headers, _ = self.request("POST", path, check=404, login="owner:ownerpw")

        # path with valid API and hook but not enabled "token"
        self.configure({"sharing": {
                                    "collection_by_map": "True",
                                    "collection_by_token": "False"}
                        })
        sharetype = "token"
        for action in sharing.API_HOOKS_V1:
            path = "/.sharing/v1/" + sharetype + "/" + action
            _, headers, _ = self.request("POST", path, check=404, login="owner:ownerpw")

        # check info hook
        logging.info("\n*** check API hook: info/all")
        json_dict = {}
        _, headers, answer = self._sharing_api_json("all", "info", check=200, login="owner:ownerpw", json_dict=json_dict)
        answer_dict = json.loads(answer)
        assert answer_dict['FeatureEnabledCollectionByMap'] is True
        assert answer_dict['FeatureEnabledCollectionByToken'] is False
        assert answer_dict['PermittedCreateCollectionByMap'] is True
        assert answer_dict['PermittedCreateCollectionByToken'] is True

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
            _, headers, _ = self.request("POST", path + "NA", check=404, login="owner:ownerpw")
            #  valid API
            _, headers, _ = self.request("POST", path, check=400, login="owner:ownerpw")

        logging.info("\n*** check API hook: info/token -> 200")
        json_dict = {}
        _, headers, answer = self._sharing_api_json("token", "info", check=200, login="owner:ownerpw", json_dict=json_dict)
        answer_dict = json.loads(answer)
        assert answer_dict['FeatureEnabledCollectionByToken'] is True
        assert 'FeatureEnabledCollectionByMap' not in answer_dict
        assert 'PermittedCreateCollectionByMap' not in answer_dict

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

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
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
                assert "Status=not-found" in answer
                assert "Lines=0" in answer

                logging.info("\n*** list (json->text)")
                json_dict = {}
                _, headers, answer = self._sharing_api_json(sharing_type, "list", check=200, login="owner:ownerpw", json_dict=json_dict, accept="text/plain")
                assert "Status=not-found" in answer
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
            assert "Status=success" in answer
            assert "PathOrToken=" in answer
            # extract token
            match = re.search('PathOrToken=(.+)', answer)
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
            _, headers, answer = self._sharing_api_form("all", "list", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=success" in answer
            assert "Lines=2" in answer

            logging.info("\n*** delete token -> 200")
            form_array = ["PathOrToken=" + token]
            _, headers, answer = self._sharing_api_form("token", "delete", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=success" in answer

            logging.info("\n*** delete share -> 200")
            form_array = []
            form_array.append("PathOrToken=/user/collectionL2-shared-by-owner/")
            form_array.append("PathMapped=/owner/collectionL2/")
            _, headers, answer = self._sharing_api_form("map", "delete", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=success" in answer

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

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            logging.info("\n*** create token without PathMapped (form) -> should fail")
            form_array = []
            _, headers, answer = self._sharing_api_form("token", "create", 400, login="owner:ownerpw", form_array=form_array)

            logging.info("\n*** create token without PathMapped (json) -> should fail")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("token", "create", 400, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** create token#1 (form->text)")
            form_array = ["PathMapped=/owner/collection1/"]
            _, headers, answer = self._sharing_api_form("token", "create", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=success" in answer
            assert "PathOrToken=" in answer
            # extract token
            match = re.search('PathOrToken=(.+)', answer)
            if match:
                token1 = match.group(1)
                logging.info("received token %r", token1)
            else:
                assert False

            logging.info("\n*** create token#2 (json->text)")
            json_dict = {'PathMapped': "/owner/collection2/"}
            _, headers, answer = self._sharing_api_json("token", "create", check=200, login="owner:ownerpw", json_dict=json_dict, accept="text/plain")
            assert "Status=success" in answer
            assert "Token=" in answer
            # extract token
            match = re.search('Token=(.+)', answer)
            if match:
                token2 = match.group(1)
                logging.info("received token %r", token2)
            else:
                assert False

            logging.info("\n*** lookup token#1 (form->text)")
            form_array = ["PathOrToken=" + token1]
            _, headers, answer = self._sharing_api_form("token", "list", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=success" in answer
            assert "Lines=1" in answer
            assert "/owner/collection1/" in answer

            logging.info("\n*** lookup token#2 (json->text")
            json_dict = {'PathOrToken': token2}
            _, headers, answer = self._sharing_api_json("token", "list", check=200, login="owner:ownerpw", json_dict=json_dict, accept="text/plain")
            assert "Status=success" in answer
            assert "Lines=1" in answer
            assert "/owner/collection2/" in answer

            logging.info("\n*** lookup token#2 (json->json)")
            json_dict = {'PathOrToken': token2}
            _, headers, answer = self._sharing_api_json("token", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['PathMapped'] == "/owner/collection2/"

            logging.info("\n*** lookup tokens (form->text)")
            form_array = []
            _, headers, answer = self._sharing_api_form("token", "list", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=success" in answer
            assert "Lines=2" in answer
            assert "/owner/collection1/" in answer
            assert "/owner/collection2/" in answer

            logging.info("\n*** lookup tokens (form->csv)")
            form_array = []
            _, headers, answer = self._sharing_api_form("token", "list", check=200, login="owner:ownerpw", form_array=form_array, accept="text/csv")
            assert "Status=success" not in answer
            assert "Lines=2" not in answer
            assert ",".join(sharing.DB_FIELDS_V1) in answer
            assert "/owner/collection1/" in answer
            assert "/owner/collection2/" in answer

            logging.info("\n*** delete token#1 (form->text)")
            form_array = ["PathOrToken=" + token1]
            _, headers, answer = self._sharing_api_form("token", "delete", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=success" in answer

            logging.info("\n*** lookup token#1 (form->text) -> should not be there anymore")
            form_array = ["PathOrToken=" + token1]
            _, headers, answer = self._sharing_api_form("token", "list", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=not-found" in answer
            assert "Lines=0" in answer

            logging.info("\n*** lookup tokens (form->text) -> still one should be there")
            form_array = []
            _, headers, answer = self._sharing_api_form("token", "list", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=success" in answer
            assert "Lines=1" in answer

            logging.info("\n*** disable token#2 (form->text)")
            form_array = ["PathOrToken=" + token2]
            _, headers, answer = self._sharing_api_form("token", "disable", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=success" in answer

            logging.info("\n*** lookup token#2 (json->json) -> check for not enabled")
            json_dict = {'PathOrToken': token2}
            _, headers, answer = self._sharing_api_json("token", "list", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['EnabledByOwner'] is False

            logging.info("\n*** enable token#2 (json->json)")
            json_dict = {}
            json_dict['PathOrToken'] = token2
            _, headers, answer = self._sharing_api_json("token", "enable", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** lookup token#2 (form->text) -> check for enabled")
            form_array = []
            form_array.append("PathOrToken=" + token2)
            _, headers, answer = self._sharing_api_form("token", "list", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=success" in answer
            assert "Lines=1" in answer
            assert "True,True,True,True" in answer

            logging.info("\n*** hide token#2 (form->text)")
            form_array = []
            form_array.append("PathOrToken=" + token2)
            _, headers, answer = self._sharing_api_form("token", "hide", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=success" in answer

            logging.info("\n*** lookup token#2 (form->text) -> check for hidden")
            form_array = []
            form_array.append("PathOrToken=" + token2)
            _, headers, answer = self._sharing_api_form("token", "list", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=success" in answer
            assert "Lines=1" in answer
            assert "True,True,True,True" in answer

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

    def test_sharing_api_token_usage(self) -> None:
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

        path_token = "/.token/"
        path_base = "/owner/calendar.ics/"
        path_base2 = "/owner/calendar2.ics/"

        logging.info("\n*** prepare")
        self.mkcalendar(path_base, login="owner:ownerpw")
        event = get_file_content("event1.ics")
        path = path_base + "/event1.ics"
        self.put(path, event, login="owner:ownerpw")

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
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
            assert "Status=success" in answer
            assert "PathOrToken=" in answer
            # extract token
            match = re.search('PathOrToken=(.+)', answer)
            if match:
                token = match.group(1)
                logging.info("received token %r", token)
            else:
                assert False

            logging.info("\n*** create token#2")
            form_array = []
            form_array.append("PathMapped=" + path_base2)
            _, headers, answer = self._sharing_api_form("token", "create", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=success" in answer
            assert "PathOrToken=" in answer
            # extract token
            match = re.search('PathOrToken=(.+)', answer)
            if match:
                token2 = match.group(1)
                logging.info("received token %r", token2)
            else:
                assert False

            logging.info("\n*** enable token (form->text)")
            form_array = ["PathOrToken=" + token]
            _, headers, answer = self._sharing_api_form("token", "enable", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=success" in answer

            logging.info("\n*** fetch collection using invalid token (without credentials)")
            _, headers, answer = self.request("GET", path_token + "v1/invalidtoken", check=401)

            logging.info("\n*** fetch collection using token (without credentials)")
            _, headers, answer = self.request("GET", path_token + token, check=200)
            assert "UID:event" in answer

            logging.info("\n*** disable token (form->text)")
            form_array = ["PathOrToken=" + token]
            _, headers, answer = self._sharing_api_form("token", "disable", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=success" in answer

            logging.info("\n*** fetch collection using disabled token (without credentials)")
            _, headers, answer = self.request("GET", path_token + token, check=401)

            logging.info("\n*** enable token (form->text)")
            form_array = ["PathOrToken=" + token]
            _, headers, answer = self._sharing_api_form("token", "enable", check=200, login="owner:ownerpw", form_array=form_array)
            assert "Status=success" in answer

            logging.info("\n*** fetch collection using token (without credentials)")
            _, headers, answer = self.request("GET", path_token + token, check=200)
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

            logging.info("\n*** fetch collection using deleted token (without credentials)")
            _, headers, answer = self.request("GET", path_token + token, check=401)

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

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            logging.info("\n*** create map without PathMapped (json) -> should fail")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "create", 400, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** create map without PathMapped but User (json) -> should fail")
            json_dict = {'User': "user"}
            _, headers, answer = self._sharing_api_json("map", "create", 400, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** create map without PathMapped but User and PathOrToken (json) -> should fail")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathOrToken'] = "/owner/calendar.ics"
            _, headers, answer = self._sharing_api_json("map", "create", 400, login="owner:ownerpw", json_dict=json_dict)

    def test_sharing_api_map_usage(self) -> None:
        """share-by-map API usage tests."""
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

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
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

            logging.info("\n*** enable map by owner for owner (json->json) -> 403")
            json_dict = {}
            json_dict['User'] = "owner"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "enable", check=403, login="owner:ownerpw", json_dict=json_dict)

            logging.info("\n*** enable map by owner for user (json->json) -> 200")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** enable map by user (json->json)")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** enable map by user for owner (json->json) -> should fail")
            json_dict = {}
            json_dict['User'] = "owner"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "enable", check=403, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** fetch collection (without credentials)")
            _, headers, answer = self.request("GET", path_mapped, check=401)

            logging.info("\n*** fetch collection (with credentials) as owner")
            _, headers, answer = self.request("GET", path_mapped, check=200, login="owner:ownerpw")
            assert "UID:event" in answer

            logging.info("\n*** fetch item (with credentials) as owner")
            _, headers, answer = self.request("GET", path_mapped_item1, check=200, login="owner:ownerpw")
            assert "UID:event" in answer

            logging.info("\n*** fetch collection (with credentials) as user")
            _, headers, answer = self.request("GET", path_mapped, check=403, login="user:userpw")

            logging.info("\n*** fetch collection via map (with credentials) as user")
            _, headers, answer = self.request("GET", path_shared, check=200, login="user:userpw")
            assert "UID:event1" in answer
            assert "UID:event2" in answer

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

            logging.info("\n*** delete map by owner (json->json) -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared
            _, headers, answer = self._sharing_api_json("map", "delete", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

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

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
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

            logging.info("\n*** create map user2/owner1 -> fail")
            json_dict = {}
            json_dict['User'] = "user2"
            json_dict['PathMapped'] = path_mapped2
            json_dict['PathOrToken'] = path_share1
            _, headers, answer = self._sharing_api_json("map", "create", check=403, login="owner2:owner2pw", json_dict=json_dict)

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
        path_shared_w = "/user/calendar-shared-by-owner-w.ics/"
        path_shared_rw = "/user/calendar-shared-by-owner-rw.ics/"
        path_mapped = "/owner/calendar.ics/"

        logging.info("\n*** prepare and test access")
        self.mkcalendar(path_mapped, login="owner:ownerpw")
        event = get_file_content("event1.ics")
        path = path_mapped + "/event1.ics"
        self.put(path, event, login="owner:ownerpw")

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # check
            logging.info("\n*** fetch event as owner (init) -> ok")
            _, headers, answer = self.request("GET", path_mapped + "event1.ics", check=200, login="owner:ownerpw")

            # create maps
            logging.info("\n*** create map user/owner:r -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = "True"
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** create map user/owner:w -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_w
            json_dict['Permissions'] = "w"
            json_dict['Enabled'] = "True"
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** create map user/owner:rw -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_rw
            json_dict['Permissions'] = "rw"
            json_dict['Enabled'] = "True"
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
            _, headers, answer = self.request("GET", path_shared_r, check=404, login="user:userpw")

            logging.info("\n*** fetch collection via map:rw -> n/a")
            _, headers, answer = self.request("GET", path_shared_r, check=404, login="user:userpw")

            # enable maps by user
            logging.info("\n*** enable map by user:r")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** enable map by user:w")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_w
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** enable map by user:rw")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_rw
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            # list adjusted maps
            logging.info("\n*** list (json->text)")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict, accept="text/csv")

            # check permissions, no map is enabled by user -> 404
            logging.info("\n*** fetch collection via map:r -> ok")
            _, headers, answer = self.request("GET", path_shared_r, check=200, login="user:userpw")

            logging.info("\n*** fetch collection via map:w -> fail")
            _, headers, answer = self.request("GET", path_shared_w, check=403, login="user:userpw")

            logging.info("\n*** fetch collection via map:rw -> ok")
            _, headers, answer = self.request("GET", path_shared_rw, check=200, login="user:userpw")

            # list adjusted maps
            logging.info("\n*** list (json->text)")
            json_dict = {}
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner:ownerpw", json_dict=json_dict, accept="text/csv")

            # PUT
            logging.info("\n*** put to collection by user via map:r -> fail")
            event = get_file_content("event2.ics")
            path = path_shared_r + "/event2.ics"
            self.put(path, event, check=403, login="user:userpw")

            logging.info("\n*** put to collection by user via map:w -> ok")
            event = get_file_content("event2.ics")
            path = path_shared_w + "event2.ics"
            self.put(path, event, check=201, login="user:userpw")

            # check result
            logging.info("\n*** fetch event via map:r -> ok")
            _, headers, answer = self.request("GET", path_shared_r + "event2.ics", check=200, login="user:userpw")

            logging.info("\n*** fetch event as owner -> ok")
            _, headers, answer = self.request("GET", path_mapped + "event2.ics", check=200, login="owner:ownerpw")

            logging.info("\n*** put to collection by user via map:rw -> ok")
            event = get_file_content("event3.ics")
            path = path_shared_rw + "event3.ics"
            self.put(path, event, check=201, login="user:userpw")

            # check result
            logging.info("\n*** fetch event via map:r -> ok")
            _, headers, answer = self.request("GET", path_shared_r + "event2.ics", check=200, login="user:userpw")

            logging.info("\n*** fetch event via map:r -> ok")
            _, headers, answer = self.request("GET", path_shared_r + "event3.ics", check=200, login="user:userpw")

            logging.info("\n*** fetch event via map:rw -> ok")
            _, headers, answer = self.request("GET", path_shared_rw + "event2.ics", check=200, login="user:userpw")

            logging.info("\n*** fetch event via map:rw -> ok")
            _, headers, answer = self.request("GET", path_shared_rw + "event3.ics", check=200, login="user:userpw")

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
            _, headers, answer = self.request("DELETE", path_shared_rw + "event2.ics", check=200, login="user:userpw")

            logging.info("\n*** DELETE from collection by user via map:w -> ok")
            _, headers, answer = self.request("DELETE", path_shared_w + "event3.ics", check=200, login="user:userpw")

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

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
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
            json_dict['Enabled'] = "True"
            json_dict['Hidden'] = "False"
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

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
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
            json_dict['Enabled'] = "True"
            json_dict['Hidden'] = "False"
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

    def test_sharing_api_map_propfind(self) -> None:
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

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
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
            json_dict['Enabled'] = "True"
            json_dict['Hidden'] = "False"
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

    def test_sharing_api_map_proppatch(self) -> None:
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
        path_shared_w = "/user/calendarPP-shared-by-owner-w.ics/"
        path_shared_rw = "/user/calendarPP-shared-by-owner-rw.ics/"

        logging.info("\n*** prepare and test access")
        self.mkcalendar(path_mapped, login="owner:ownerpw")
        event = get_file_content("event1.ics")
        path = os.path.join(path_mapped, "event1.ics")
        self.put(path, event, login="owner:ownerpw")

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
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
            _, responses = self.proppatch(path_shared_w, proppatch, login="user:userpw", check=404)
            _, responses = self.proppatch(path_shared_rw, proppatch, login="user:userpw", check=404)

            # create map
            logging.info("\n*** create map user/owner:r -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = "True"
            json_dict['Hidden'] = "False"
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** create map user/owner:w -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_w
            json_dict['Permissions'] = "w"
            json_dict['Enabled'] = "True"
            json_dict['Hidden'] = "False"
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** create map user/owner:rw -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_rw
            json_dict['Permissions'] = "rw"
            json_dict['Enabled'] = "True"
            json_dict['Hidden'] = "False"
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            # check PROPPATCH as user
            logging.info("\n*** PROPPATCH collection as user -> 403")
            proppatch = get_file_content("proppatch_set_calendar_color.xml")
            _, responses = self.proppatch(path_shared_r, proppatch, login="user:userpw", check=404)
            _, responses = self.proppatch(path_shared_w, proppatch, login="user:userpw", check=404)
            _, responses = self.proppatch(path_shared_rw, proppatch, login="user:userpw", check=404)

            # enable map by user
            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_w
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** enable map by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped
            json_dict['PathOrToken'] = path_shared_rw
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            # check PROPPATCH as user
            proppatch = get_file_content("proppatch_remove_calendar_color.xml")
            logging.info("\n*** PROPPATCH collection as user:r -> 403")
            _, responses = self.proppatch(path_shared_r, proppatch, login="user:userpw", check=403)

            logging.info("\n*** PROPPATCH collection as user:w -> ok")
            _, responses = self.proppatch(path_shared_w, proppatch, login="user:userpw")
            logging.info("response: %r", responses)

            logging.info("\n*** PROPPATCH collection as user:rw -> ok")
            _, responses = self.proppatch(path_shared_rw, proppatch, login="user:userpw")
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
        path_mapped2 = "/owner/calendar2M.ics/"
        path_shared1_r = "/user/calendar1M-shared-by-owner-r.ics/"
        path_shared1_rw = "/user/calendar1M-shared-by-owner-rw.ics/"
        path_shared2_rw = "/user/calendar2M-shared-by-owner-rw.ics/"

        logging.info("\n*** prepare and test access")
        self.mkcalendar(path_mapped1, login="owner:ownerpw")
        event = get_file_content("event1.ics")
        self.put(os.path.join(path_mapped1, "event1.ics"), event, login="owner:ownerpw")

        self.mkcalendar(path_mapped2, login="owner:ownerpw")
        event = get_file_content("event2.ics")
        self.put(os.path.join(path_mapped2, "event2.ics"), event, login="owner:ownerpw")

        self.mkcalendar(path_user, login="user:userpw")
        event = get_file_content("event3.ics")
        self.put(os.path.join(path_user, "event3.ics"), event, login="user:userpw")

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
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
            json_dict['PathMapped'] = path_mapped1
            json_dict['PathOrToken'] = path_shared1_r
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = "True"
            json_dict['Hidden'] = "False"
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** create map user/owner:rw -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped1
            json_dict['PathOrToken'] = path_shared1_rw
            json_dict['Permissions'] = "rw"
            json_dict['Enabled'] = "True"
            json_dict['Hidden'] = "False"
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner:ownerpw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** create map user/owner:rw -> ok")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped2
            json_dict['PathOrToken'] = path_shared2_rw
            json_dict['Permissions'] = "rw"
            json_dict['Enabled'] = "True"
            json_dict['Hidden'] = "False"
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
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped1
            json_dict['PathOrToken'] = path_shared1_r
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** enable map shared1_rw by user")
            json_dict = {}
            json_dict['User'] = "user"
            json_dict['PathMapped'] = path_mapped1
            json_dict['PathOrToken'] = path_shared1_rw
            _, headers, answer = self._sharing_api_json("map", "enable", check=200, login="user:userpw", json_dict=json_dict)

            logging.info("\n*** enable map shared2_rw by user")
            json_dict = {}
            json_dict['User'] = "user"
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
            logging.info("\n*** GET event1 as user -> ok")
            _, headers, answer = self.request("GET", os.path.join(path_shared1_r, "event1.ics"), check=200, login="user:userpw")

            logging.info("\n*** GET event1 as user -> ok")
            _, headers, answer = self.request("GET", os.path.join(path_shared1_rw, "event1.ics"), check=200, login="user:userpw")

            logging.info("\n*** GET event1 as user -> 404")
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

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
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
            json_dict['Enabled'] = "True"
            json_dict['Hidden'] = "False"
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
            assert "Status=success" in answer
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
            assert "Status=success" in answer
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

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
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
            json_dict['Enabled'] = "True"
            json_dict['Hidden'] = "False"
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
            json_dict['Enabled'] = "True"
            json_dict['Hidden'] = "False"
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
            json_dict['Enabled'] = "True"
            json_dict['Hidden'] = "False"
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
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})
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

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # create map
            logging.info("\n*** create map user1/owner1 -> ok")
            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_owner1
            json_dict['PathOrToken'] = path_user1_shared1
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = "True"
            json_dict['Hidden'] = "False"
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** mkcalendar user1 for shared -> conflict")
            self.mkcalendar(path_user1_shared1, login="user1:user1pw", check=409)

            # create map
            logging.info("\n*** create map user2/owner1 -> ok")
            json_dict = {}
            json_dict['User'] = "user2"
            json_dict['PathMapped'] = path_owner1
            json_dict['PathOrToken'] = path_user2_shared1
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = "True"
            json_dict['Hidden'] = "False"
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"

            logging.info("\n*** mkcol user2 for shared -> conflict")
            self.mkcalendar(path_user2_shared1, login="user2:user2pw", check=409)

            # create map
            logging.info("\n*** create map user2/owner2 -> 409")
            json_dict = {}
            json_dict['User'] = "user2"
            json_dict['PathMapped'] = path_owner1
            json_dict['PathOrToken'] = path_user2
            json_dict['Permissions'] = "r"
            json_dict['Enabled'] = "True"
            json_dict['Hidden'] = "False"
            _, headers, answer = self._sharing_api_json("map", "create", check=409, login="owner1:owner1pw", json_dict=json_dict)

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

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
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
collection: {user}/cal-T(/.*)?
permissions: RrWwT
[owner1-t]
user: owner1
collection: {user}/cal-t(/.*)?
permissions: RrWwt
[owner1-M]
user: owner1
collection: {user}/cal-M(/.*)?
permissions: RrWwM
[owner1-m]
user: owner1
collection: {user}/cal-m(/.*)?
permissions: RrWwm
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
                                    "response_content_on_debug": "False",
                                    "rights_rule_doesnt_match_on_debug": "True",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "from_file"}})

        json_dict: dict

        path_user1 = "/user1/calendarPGu1.ics/"
        path_owner1_T = "/owner1/cal-T/"
        path_owner1_t = "/owner1/cal-t/"
        path_owner1_M = "/owner1/cal-M/"
        path_owner1_m = "/owner1/cal-m/"

        logging.info("\n*** prepare")
        self.mkcalendar(path_owner1_T, login="owner1:owner1pw")
        self.mkcalendar(path_owner1_t, login="owner1:owner1pw")
        self.mkcalendar(path_owner1_M, login="owner1:owner1pw")
        self.mkcalendar(path_owner1_m, login="owner1:owner1pw")

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
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
            json_dict['PathOrToken'] = path_user1 + "dM" + db_type
            _, headers, answer = self._sharing_api_json("map", "create", check=403, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1, globally disabled / not granted T -> 403")
            json_dict['PathMapped'] = path_owner1_T
            json_dict['PathOrToken'] = path_user1 + "dT" + db_type
            _, headers, answer = self._sharing_api_json("map", "create", check=403, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1, globally disabled / not granted t -> 403")
            json_dict['PathMapped'] = path_owner1_t
            json_dict['PathOrToken'] = path_user1 + "dt" + db_type
            _, headers, answer = self._sharing_api_json("map", "create", check=403, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1, globally disabled / granted m -> 200")
            json_dict['PathMapped'] = path_owner1_m
            json_dict['PathOrToken'] = path_user1 + "dm" + db_type
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1, globally enabled")
            self.configure({"sharing": {"permit_create_map": "True"}})

            logging.info("\n*** create map user1/owner1, globally enabled / not granted M -> 403")
            json_dict['PathMapped'] = path_owner1_M
            json_dict['PathOrToken'] = path_user1 + "eM" + db_type
            _, headers, answer = self._sharing_api_json("map", "create", check=403, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1, globally enabled / ignore T -> 200")
            json_dict['PathMapped'] = path_owner1_T
            json_dict['PathOrToken'] = path_user1 + "eT" + db_type
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1, globally enabled / ignore t -> 200")
            json_dict['PathMapped'] = path_owner1_t
            json_dict['PathOrToken'] = path_user1 + "et" + db_type
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** create map user1/owner1, globally enabled / ignore m -> 200")
            json_dict['PathMapped'] = path_owner1_m
            json_dict['PathOrToken'] = path_user1 + "em" + db_type
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
                                    "response_content_on_debug": "False",
                                    "request_content_on_debug": "True"},
                        "rights": {"type": "owner_only"}})

        json_dict: dict

        path_user1 = "/user1/calendarPGu1.ics/"
        path_owner1 = "/owner1/calendarPGo1.ics/"

        logging.info("\n*** prepare")
        self.mkcalendar(path_owner1, login="owner1:owner1pw")

        for db_type in sharing.INTERNAL_TYPES:
            if db_type == "none":
                continue
            logging.info("\n*** test: %s", db_type)
            self.configure({"sharing": {"type": db_type}})

            # create map
            self.configure({"sharing": {"default_permissions_create_map": "r"}})

            json_dict = {}
            json_dict['User'] = "user1"
            json_dict['PathMapped'] = path_owner1

            logging.info("\n*** create map user1/owner1 r -> 200")
            json_dict['PathOrToken'] = path_user1 + "r"
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** list (json->json)")
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['Permissions'] == "r"

            logging.info("\n*** create map user1/owner1 rw -> 200")
            json_dict['PathOrToken'] = path_user1 + "rw"
            json_dict['Permissions'] = "rw"
            _, headers, answer = self._sharing_api_json("map", "create", check=200, login="owner1:owner1pw", json_dict=json_dict)

            logging.info("\n*** list (json->json)")
            _, headers, answer = self._sharing_api_json("map", "list", check=200, login="owner1:owner1pw", json_dict=json_dict)
            answer_dict = json.loads(answer)
            assert answer_dict['Status'] == "success"
            assert answer_dict['Lines'] == 1
            assert answer_dict['Content'][0]['Permissions'] == "rw"

            logging.info("\n*** create map user1/owner1 with adjusted default permissions -> 200")
            self.configure({"sharing": {"default_permissions_create_map": "RrWw"}})
            json_dict['PathOrToken'] = path_user1 + "RrRw"
            del json_dict['Permissions']
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
