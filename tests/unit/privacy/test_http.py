"""
Tests for the privacy HTTP endpoints.
"""

import io
import json
import os
import tempfile
from http import client
from unittest.mock import patch

import pytest

from radicale import config
from radicale.privacy.http import PrivacyHTTP


@pytest.fixture
def http_app():
    """Fixture to provide a privacy HTTP app instance."""
    # Set up environment variable for token auth
    test_token = "test-token-12345"
    old_token = os.environ.get("RADICALE_TOKEN")
    os.environ["RADICALE_TOKEN"] = test_token

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create collection-root directory
            collection_root = os.path.join(tmpdir, "collection-root")
            os.makedirs(collection_root, exist_ok=True)

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
                "rights": {
                    "type": "authenticated"
                }
            }, "test")

            app = PrivacyHTTP(configuration)
            # Store test token for easy access in tests
            app._test_token = test_token
            yield app
    finally:
        # Restore original environment
        if old_token is None:
            os.environ.pop("RADICALE_TOKEN", None)
        else:
            os.environ["RADICALE_TOKEN"] = old_token


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_unauthenticated_request(http_app):
    """Test request without authorization header returns 401."""
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/privacy/settings/test@example.com"
    }

    status, headers, body = http_app.do_GET(environ, "/privacy/settings/test@example.com")

    assert status == client.UNAUTHORIZED
    assert headers["Content-Type"] == "application/json"
    assert headers["WWW-Authenticate"] == "Bearer"
    data = json.loads(body)
    assert "Unauthorized" in data["error"]


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_invalid_token_request(http_app):
    """Test request with invalid token returns 401."""
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/privacy/settings/test@example.com",
        "HTTP_AUTHORIZATION": "Bearer invalid-token"
    }

    status, headers, body = http_app.do_GET(environ, "/privacy/settings/test@example.com")

    assert status == client.UNAUTHORIZED
    assert headers["Content-Type"] == "application/json"
    assert headers["WWW-Authenticate"] == "Bearer"
    data = json.loads(body)
    assert "Unauthorized" in data["error"]


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_malformed_auth_header(http_app):
    """Test request with malformed authorization header returns 401."""
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/privacy/settings/test@example.com",
        "HTTP_AUTHORIZATION": "Basic invalid"  # Not Bearer token
    }

    status, headers, body = http_app.do_GET(environ, "/privacy/settings/test@example.com")

    assert status == client.UNAUTHORIZED
    assert headers["Content-Type"] == "application/json"
    assert headers["WWW-Authenticate"] == "Bearer"
    data = json.loads(body)
    assert "Unauthorized" in data["error"]


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_empty_bearer_token(http_app):
    """Test request with empty Bearer token returns 401."""
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/privacy/settings/test@example.com",
        "HTTP_AUTHORIZATION": "Bearer "  # Empty token
    }

    status, headers, body = http_app.do_GET(environ, "/privacy/settings/test@example.com")

    assert status == client.UNAUTHORIZED
    assert headers["Content-Type"] == "application/json"
    assert headers["WWW-Authenticate"] == "Bearer"
    data = json.loads(body)
    assert "Unauthorized" in data["error"]


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

        # Create mock WSGI environment with authorization header
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/privacy/settings/test@example.com",
            "HTTP_AUTHORIZATION": f"Bearer {http_app._test_token}"
        }

        # Call the handler
        status, headers, body = http_app.do_GET(environ, "/privacy/settings/test@example.com")

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

        # Create mock WSGI environment with authorization header
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/privacy/settings/nonexistent@example.com",
            "HTTP_AUTHORIZATION": f"Bearer {http_app._test_token}"
        }

        # Call the handler
        status, headers, body = http_app.do_GET(environ, "/privacy/settings/nonexistent@example.com")

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

        # Create mock WSGI environment with authorization header
        environ = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/privacy/cards/test@example.com",
            "HTTP_AUTHORIZATION": f"Bearer {http_app._test_token}"
        }

        # Call the handler
        status, headers, body = http_app.do_GET(environ, "/privacy/cards/test@example.com")

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

        # Create mock WSGI environment with request body and authorization header
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
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(settings_json)),
            "HTTP_AUTHORIZATION": f"Bearer {http_app._test_token}",
            "wsgi.input": io.BytesIO(settings_json)
        }

        # Call the handler
        status, headers, body = http_app.do_POST(environ, "/privacy/settings/test@example.com")

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

        # Create mock WSGI environment with request body and authorization header
        settings = {
            "disallow_photo": True,
            "disallow_birthday": True
        }
        settings_json = json.dumps(settings).encode()
        environ = {
            "REQUEST_METHOD": "PUT",
            "PATH_INFO": "/privacy/settings/test@example.com",
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(settings_json)),
            "HTTP_AUTHORIZATION": f"Bearer {http_app._test_token}",
            "wsgi.input": io.BytesIO(settings_json)
        }

        # Call the handler
        status, headers, body = http_app.do_PUT(environ, "/privacy/settings/test@example.com")

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

        # Create mock WSGI environment with authorization header
        environ = {
            "REQUEST_METHOD": "DELETE",
            "PATH_INFO": "/privacy/settings/test@example.com",
            "HTTP_AUTHORIZATION": f"Bearer {http_app._test_token}"
        }

        # Call the handler
        status, headers, body = http_app.do_DELETE(environ, "/privacy/settings/test@example.com")

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

        # Create mock WSGI environment with authorization header
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/privacy/cards/test@example.com/reprocess",
            "HTTP_AUTHORIZATION": f"Bearer {http_app._test_token}"
        }

        # Call the handler
        status, headers, body = http_app.do_POST(environ, "/privacy/cards/test@example.com/reprocess")

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
    # Create mock WSGI environment with invalid path and authorization header
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/privacy/invalid/test@example.com",
        "HTTP_AUTHORIZATION": f"Bearer {http_app._test_token}"
    }

    # Call the handler
    status, headers, body = http_app.do_GET(environ, "/privacy/invalid/test@example.com")

    # Verify response
    assert status == client.NOT_FOUND  # Updated expected status


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_missing_content_length(http_app):
    """Test POST request with missing content length."""
    # Create mock WSGI environment without content length but with authorization header
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/privacy/settings/test@example.com",
        "CONTENT_LENGTH": "",  # Empty content length
        "HTTP_AUTHORIZATION": f"Bearer {http_app._test_token}"
    }

    # Call the handler
    status, headers, body = http_app.do_POST(environ, "/privacy/settings/test@example.com")

    # Verify response
    assert status == client.BAD_REQUEST
    assert headers["Content-Type"] == "application/json"
    data = json.loads(body)
    assert "error" in data


@pytest.mark.skipif(os.name == 'nt', reason="Prolematic on Windows due to file locking")
def test_invalid_json(http_app):
    """Test POST request with invalid JSON."""
    # Create mock WSGI environment with invalid JSON and authorization header
    invalid_json = b"invalid json"
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/privacy/settings/test@example.com",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(invalid_json)),
        "HTTP_AUTHORIZATION": f"Bearer {http_app._test_token}",
        "wsgi.input": io.BytesIO(invalid_json)
    }

    # Call the handler
    status, headers, body = http_app.do_POST(environ, "/privacy/settings/test@example.com")

    # Verify response
    assert status == client.BAD_REQUEST
    assert headers["Content-Type"] == "application/json"
    data = json.loads(body)
    assert "error" in data


# test_unauthorized_access removed - now covered by authentication tests above
