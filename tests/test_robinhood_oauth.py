import json
import time

import httpx
import pytest

from cream_agent.auth.robinhood_oauth import OAuthError, RobinhoodOAuthClient, _extract_resource_metadata_url
from cream_agent.config import secrets

MCP_URL = "https://agent.robinhood.com/mcp/trading"


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CREAM_AGENT_HOME", str(tmp_path))
    secrets._fallback_warned = False


def test_extract_resource_metadata_url_parses_www_authenticate_header():
    header = 'Bearer resource_metadata="https://agent.robinhood.com/.well-known/oauth-protected-resource"'
    assert (
        _extract_resource_metadata_url(header)
        == "https://agent.robinhood.com/.well-known/oauth-protected-resource"
    )


def test_extract_resource_metadata_url_returns_none_when_absent():
    assert _extract_resource_metadata_url("Bearer realm=\"example\"") is None


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def test_discover_protected_resource_metadata_follows_401_challenge():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == MCP_URL:
            return httpx.Response(
                401,
                headers={
                    "WWW-Authenticate": (
                        'Bearer resource_metadata='
                        '"https://agent.robinhood.com/.well-known/oauth-protected-resource"'
                    )
                },
            )
        if request.url.path == "/.well-known/oauth-protected-resource":
            return httpx.Response(
                200, json={"authorization_servers": ["https://auth.robinhood.com"]}
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client = RobinhoodOAuthClient(
        mcp_url=MCP_URL, http_client=httpx.Client(transport=_mock_transport(handler))
    )
    metadata = client._discover_protected_resource_metadata()
    assert metadata["authorization_servers"] == ["https://auth.robinhood.com"]


def test_discover_protected_resource_metadata_falls_back_to_well_known_when_no_401():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == MCP_URL:
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/.well-known/oauth-protected-resource":
            return httpx.Response(200, json={"authorization_servers": ["https://auth.robinhood.com"]})
        raise AssertionError(f"unexpected request: {request.url}")

    client = RobinhoodOAuthClient(
        mcp_url=MCP_URL, http_client=httpx.Client(transport=_mock_transport(handler))
    )
    metadata = client._discover_protected_resource_metadata()
    assert metadata["authorization_servers"] == ["https://auth.robinhood.com"]


def test_discover_authorization_server_metadata():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://auth.robinhood.com/.well-known/oauth-authorization-server"
        return httpx.Response(
            200,
            json={
                "authorization_endpoint": "https://auth.robinhood.com/authorize",
                "token_endpoint": "https://auth.robinhood.com/token",
                "registration_endpoint": "https://auth.robinhood.com/register",
            },
        )

    client = RobinhoodOAuthClient(
        mcp_url=MCP_URL, http_client=httpx.Client(transport=_mock_transport(handler))
    )
    meta = client._discover_authorization_server_metadata("https://auth.robinhood.com")
    assert meta["token_endpoint"] == "https://auth.robinhood.com/token"


def test_register_client_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body["redirect_uris"] == ["http://127.0.0.1:8765/callback"]
        assert body["token_endpoint_auth_method"] == "none"
        return httpx.Response(200, json={"client_id": "abc123", "client_secret": None})

    client = RobinhoodOAuthClient(
        mcp_url=MCP_URL, http_client=httpx.Client(transport=_mock_transport(handler))
    )
    client_id = client._register_client(
        {"registration_endpoint": "https://auth.robinhood.com/register"}
    )
    assert client_id == "abc123"


def test_register_client_ignores_absent_client_secret_field():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"client_id": "abc123"})

    client = RobinhoodOAuthClient(
        mcp_url=MCP_URL, http_client=httpx.Client(transport=_mock_transport(handler))
    )
    client_id = client._register_client(
        {"registration_endpoint": "https://auth.robinhood.com/register"}
    )
    assert client_id == "abc123"


def test_register_client_rejects_confidential_client_secret_response():
    # We register with token_endpoint_auth_method="none" (public client, PKCE
    # only) and never send a client_secret on token/refresh requests. If the
    # server hands one back anyway, we must not silently proceed — we'd
    # authenticate to a server that expects a secret without ever sending it.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"client_id": "abc123", "client_secret": "shh-its-a-secret"}
        )

    client = RobinhoodOAuthClient(
        mcp_url=MCP_URL, http_client=httpx.Client(transport=_mock_transport(handler))
    )
    with pytest.raises(OAuthError, match="confidential client"):
        client._register_client({"registration_endpoint": "https://auth.robinhood.com/register"})


def test_register_client_raises_without_registration_endpoint():
    client = RobinhoodOAuthClient(mcp_url=MCP_URL, http_client=httpx.Client())
    with pytest.raises(OAuthError):
        client._register_client({})


def test_get_access_token_returns_cached_token_without_network():
    secrets.set_secret("robinhood_access_token", "cached-token")
    secrets.set_secret("robinhood_token_expiry", str(time.time() + 3600))

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not hit the network when a valid cached token exists")

    client = RobinhoodOAuthClient(
        mcp_url=MCP_URL, http_client=httpx.Client(transport=_mock_transport(handler))
    )
    assert client.get_access_token() == "cached-token"


def test_refresh_updates_stored_tokens():
    secrets.set_secret("robinhood_refresh_token", "old-refresh")
    secrets.set_secret("robinhood_token_endpoint", "https://auth.robinhood.com/token")
    secrets.set_secret("robinhood_client_id", "abc123")

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://auth.robinhood.com/token"
        return httpx.Response(
            200,
            json={"access_token": "new-token", "refresh_token": "new-refresh", "expires_in": 3600},
        )

    client = RobinhoodOAuthClient(
        mcp_url=MCP_URL, http_client=httpx.Client(transport=_mock_transport(handler))
    )
    assert client.refresh() is True
    assert secrets.get_secret("robinhood_access_token") == "new-token"
    assert secrets.get_secret("robinhood_refresh_token") == "new-refresh"


def test_refresh_returns_false_without_stored_refresh_token():
    client = RobinhoodOAuthClient(mcp_url=MCP_URL, http_client=httpx.Client())
    assert client.refresh() is False


def test_get_access_token_raises_when_noninteractive_and_no_token():
    client = RobinhoodOAuthClient(mcp_url=MCP_URL, http_client=httpx.Client())
    with pytest.raises(OAuthError):
        client.get_access_token(interactive=False)


def test_disconnect_clears_all_robinhood_secrets():
    secrets.set_secret("robinhood_access_token", "t")
    secrets.set_secret("robinhood_refresh_token", "r")
    secrets.set_secret("robinhood_client_id", "c")

    client = RobinhoodOAuthClient(mcp_url=MCP_URL, http_client=httpx.Client())
    client.disconnect()

    assert secrets.get_secret("robinhood_access_token") is None
    assert secrets.get_secret("robinhood_refresh_token") is None
    assert secrets.get_secret("robinhood_client_id") is None
