"""
Tests for the privacy HTTP endpoints.
"""

import json
import os
import tempfile
from http import client
from unittest.mock import MagicMock, patch

import pytest

from radicale import config
from radicale.privacy.http import PrivacyHTTP


@pytest.fixture
def http_app():
    """Fixture to provide a privacy HTTP app instance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create collection-root directory
        collection_root = os.path.join(tmpdir, "collection-root")
        os.makedirs(collection_root, exist_ok=True)

        # Create htpasswd file for authentication
        # htpasswd_file = os.path.join(tmpdir, ".htpasswd")
        # with open(htpasswd_file, "w") as f:
        #     f.write("test@example.com:password\n")

        test_db_path = os.path.join(tmpdir, "test.db")
        configuration = config.load()
        configuration.update({
            "privacy": {
                "database_path": test_db_path
            },
            "storage": {
                "type": "multifilesystem",
                "filesystem_folder": tmpdir  # Use tmpdir as base, let storage add collection-root
            },
            "auth": {
                "type": "token",
            },
            # "auth": {
            #     "type": "htpasswd",
            #     "htpasswd_filename": htpasswd_file,
            #     "htpasswd_encryption": "plain"
            # },
            "rights": {
                "type": "authenticated"
            }
        }, "test")

        app = PrivacyHTTP(configuration)
        # Patch authentication for all tests
        app._get_authenticated_user = lambda environ: ("test@example.com", None)
        yield app


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_get_settings_success(http_app):
    """Test successful GET request for settings."""
    # Mock the API response
    with patch.object(http_app._privacy_core, 'get_settings') as mock_get:
        mock_get.return_value = (True, {
            "disallow_photo": True,
            "disallow_gender": True,
            "disallow_birthday": False,
            "disallow_address": True,
            "disallow_company": True,
            "disallow_title": False,
        })

        # Create mock WSGI environment
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/privacy/settings/test@example.com"
        }

        # Call the handler with matching user
        status, headers, body = http_app.do_GET(environ, "/", "/privacy/settings/test@example.com", "test@example.com")

        # Verify response
        assert status == client.OK
        assert headers["Content-Type"] == "application/json"
        data = json.loads(body)
        assert data["disallow_photo"] is True
        assert data["disallow_gender"] is True
        assert data["disallow_birthday"] is False
        assert data["disallow_address"] is True
        assert data["disallow_company"] is True
        assert data["disallow_title"] is False


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_get_settings_error(http_app):
    """Test GET request for settings with error."""
    # Mock the API response
    with patch.object(http_app._privacy_core, 'get_settings') as mock_get:
        mock_get.return_value = (False, "User settings not found")

        # Create mock WSGI environment
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/privacy/settings/nonexistent@example.com",
            "HTTP_AUTHORIZATION": "Bearer test_token"  # Add authorization header
        }

        # Mock the authentication to return the same user as in the path
        with patch.object(http_app, '_get_authenticated_user', return_value=("nonexistent@example.com", None)):
            # Call the handler with matching user
            status, headers, body = http_app.do_GET(environ, "/", "/privacy/settings/nonexistent@example.com", "nonexistent@example.com")

            # Verify response
            assert status == client.BAD_REQUEST
            assert headers["Content-Type"] == "application/json"
            data = json.loads(body)
            assert data["error"] == "User settings not found"


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_get_matching_cards_success(http_app):
    """Test successful GET request for matching cards."""
    # Mock the API response
    with patch.object(http_app._privacy_core, 'get_matching_cards') as mock_get:
        mock_get.return_value = (True, {
            "matches": [
                {
                    "vcard_uid": "card1",
                    "collection_path": "user1/contacts",
                    "matching_fields": ["email"],
                    "fields": {
                        "email": ["test@example.com"]
                    }
                }
            ]
        })

        # Create mock WSGI environment
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/privacy/cards/test@example.com"
        }

        # Call the handler with matching user
        status, headers, body = http_app.do_GET(environ, "/", "/privacy/cards/test@example.com", "test@example.com")

        # Verify response
        assert status == client.OK
        assert headers["Content-Type"] == "application/json"
        data = json.loads(body)
        assert "matches" in data
        assert len(data["matches"]) == 1
        assert data["matches"][0]["vcard_uid"] == "card1"


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_create_settings_success(http_app):
    """Test successful POST request for creating settings."""
    # Mock the API response
    with patch.object(http_app._privacy_core, 'create_settings') as mock_create:
        mock_create.return_value = (True, {"status": "created"})

        # Create mock WSGI environment with request body
        settings = {
            "disallow_photo": True,
            "disallow_gender": True,
            "disallow_birthday": False,
            "disallow_address": True,
            "disallow_company": True,
            "disallow_title": False,
        }
        settings_json = json.dumps(settings).encode()
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/privacy/settings/test@example.com",
            "CONTENT_LENGTH": str(len(settings_json)),
            "wsgi.input": MagicMock(read=lambda size: settings_json)
        }

        # Call the handler with matching user
        status, headers, body = http_app.do_POST(environ, "/", "/privacy/settings/test@example.com", "test@example.com")

        # Verify response
        assert status == client.CREATED
        assert headers["Content-Type"] == "application/json"
        data = json.loads(body)
        assert data["status"] == "created"


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_update_settings_success(http_app):
    """Test successful PUT request for updating settings."""
    # Mock the API response
    with patch.object(http_app._privacy_core, 'update_settings') as mock_update:
        mock_update.return_value = (True, {"status": "updated"})

        # Create mock WSGI environment with request body
        settings = {
            "disallow_photo": True,
            "disallow_birthday": True
        }
        settings_json = json.dumps(settings).encode()
        environ = {
            "REQUEST_METHOD": "PUT",
            "PATH_INFO": "/privacy/settings/test@example.com",
            "CONTENT_LENGTH": str(len(settings_json)),
            "wsgi.input": MagicMock(read=lambda size: settings_json)
        }

        # Call the handler with matching user
        status, headers, body = http_app.do_PUT(environ, "/", "/privacy/settings/test@example.com", "test@example.com")

        # Verify response
        assert status == client.OK
        assert headers["Content-Type"] == "application/json"
        data = json.loads(body)
        assert data["status"] == "updated"


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_delete_settings_success(http_app):
    """Test successful DELETE request for settings."""
    # Mock the API response
    with patch.object(http_app._privacy_core, 'delete_settings') as mock_delete:
        mock_delete.return_value = (True, {"status": "deleted"})

        # Create mock WSGI environment
        environ = {
            "REQUEST_METHOD": "DELETE",
            "PATH_INFO": "/privacy/settings/test@example.com"
        }

        # Call the handler with matching user
        status, headers, body = http_app.do_DELETE(environ, "/", "/privacy/settings/test@example.com", "test@example.com")

        # Verify response
        assert status == client.OK
        assert headers["Content-Type"] == "application/json"
        data = json.loads(body)
        assert data["status"] == "deleted"


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_reprocess_cards_success(http_app):
    """Test successful POST request for reprocessing cards."""
    # Mock the API response
    with patch.object(http_app._privacy_core, 'reprocess_cards') as mock_reprocess:
        mock_reprocess.return_value = (True, {
            "status": "success",
            "reprocessed_cards": 2,
            "reprocessed_card_uids": ["card1", "card2"]
        })

        # Create mock WSGI environment
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/privacy/cards/test@example.com/reprocess"
        }

        # Call the handler with matching user
        status, headers, body = http_app.do_POST(environ, "/", "/privacy/cards/test@example.com/reprocess", "test@example.com")

        # Verify response
        assert status == client.OK
        assert headers["Content-Type"] == "application/json"
        data = json.loads(body)
        assert data["status"] == "success"
        assert data["reprocessed_cards"] == 2
        assert len(data["reprocessed_card_uids"]) == 2


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_invalid_path(http_app):
    """Test request with invalid path."""
    # Create mock WSGI environment with invalid path
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/privacy/invalid/test@example.com"
    }

    # Call the handler with matching user
    status, headers, body = http_app.do_GET(environ, "/", "/privacy/invalid/test@example.com", "test@example.com")

    # Verify response
    assert status == client.BAD_REQUEST


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_missing_content_length(http_app):
    """Test POST request with missing content length."""
    # Create mock WSGI environment without content length
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/privacy/settings/test@example.com",
        "CONTENT_LENGTH": ""  # Empty content length
    }

    # Call the handler with matching user
    status, headers, body = http_app.do_POST(environ, "/", "/privacy/settings/test@example.com", "test@example.com")

    # Verify response
    assert status == client.BAD_REQUEST
    assert headers["Content-Type"] == "application/json"
    data = json.loads(body)
    assert "error" in data


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_invalid_json(http_app):
    """Test POST request with invalid JSON."""
    # Create mock WSGI environment with invalid JSON
    invalid_json = b"invalid json"
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/privacy/settings/test@example.com",
        "CONTENT_LENGTH": str(len(invalid_json)),
        "wsgi.input": MagicMock(read=lambda size: invalid_json)
    }

    # Call the handler with matching user
    status, headers, body = http_app.do_POST(environ, "/", "/privacy/settings/test@example.com", "test@example.com")

    # Verify response
    assert status == client.BAD_REQUEST
    assert headers["Content-Type"] == "application/json"
    data = json.loads(body)
    assert "error" in data


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_unauthorized_access(http_app):
    """Test unauthorized access to settings."""
    # Create mock WSGI environment
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/privacy/settings/test@example.com"
    }

    # Call the handler with different user than the one in the path
    with patch.object(http_app, '_get_authenticated_user', return_value=("other@example.com", None)):
        status, headers, body = http_app.do_GET(environ, "/", "/privacy/settings/test@example.com", "other@example.com")

    # Verify response
    assert status == client.FORBIDDEN
    assert headers["Content-Type"] == "application/json"
    data = json.loads(body)
    assert "error" in data or "Action on the requested resource refused." in body.decode()
