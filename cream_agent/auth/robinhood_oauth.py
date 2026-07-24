"""OAuth 2.1 + PKCE client for Robinhood's Agentic Trading MCP server.

The Claude Agent SDK does **not** run an interactive OAuth flow on behalf of
a library caller — per Anthropic's docs, when a remote MCP server demands
auth and no token is cached, the SDK just skips that server's tools and
reports ``needs-auth``. Robinhood's support docs don't publish a token/API
key flow either; Robinhood's MCP server is presumed to speak the standard
MCP authorization flow (OAuth 2.1 + PKCE, RFC 8414/7591/9728 discovery,
RFC 8707 resource indicators), since that's what the MCP spec requires of
HTTP-transport servers that opt into authorization. This client implements
that standard flow end to end so Cream Agent can obtain its own bearer
token and pass it via the ``headers`` field of the SDK's MCP server config.

This has not been exercised against Robinhood's real server yet (no
interactive browser session is available in this build environment) — if
Robinhood's discovery endpoints deviate from the spec, expect to adjust
``_discover_protected_resource_metadata`` / ``_discover_authorization_server_metadata``
once testing against a live account is possible.
"""

from __future__ import annotations

import re
import time
import webbrowser
from typing import Optional
from urllib.parse import urlencode, urlsplit

import httpx

from cream_agent.auth.callback_server import wait_for_callback
from cream_agent.auth.pkce import canonical_resource_uri, generate_pkce_pair, generate_state
from cream_agent.config.secrets import delete_secret, get_secret, set_secret

_RESOURCE_METADATA_RE = re.compile(r'resource_metadata="([^"]+)"')

# Secrets are namespaced so multiple OAuth-protected MCP integrations
# (Robinhood today, others later) can coexist without clobbering each other.
_PREFIX = "robinhood_"


class OAuthError(Exception):
    """Raised when the Robinhood authorization flow can't complete."""


class RobinhoodOAuthClient:
    def __init__(
        self,
        mcp_url: str,
        redirect_port: int = 8765,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self.mcp_url = mcp_url
        self.redirect_port = redirect_port
        self._http = http_client or httpx.Client(timeout=30.0)
        self._owns_http = http_client is None

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    # -- public API -----------------------------------------------------

    def is_connected(self) -> bool:
        return get_secret(_PREFIX + "access_token") is not None

    def get_access_token(self, interactive: bool = True) -> str:
        """Return a valid bearer token, refreshing or (re-)authorizing as needed."""
        token = get_secret(_PREFIX + "access_token")
        expiry = get_secret(_PREFIX + "token_expiry")
        if token and (expiry is None or float(expiry) - time.time() > 60):
            return token

        if self.refresh():
            token = get_secret(_PREFIX + "access_token")
            if token:
                return token

        if not interactive:
            raise OAuthError("No valid Robinhood token and interactive authorization is disabled")

        self.authorize()
        token = get_secret(_PREFIX + "access_token")
        if not token:
            raise OAuthError("Authorization completed but no access token was stored")
        return token

    def authorize(self) -> None:
        """Run the full interactive PKCE authorization-code flow."""
        resource = canonical_resource_uri(self.mcp_url)
        resource_metadata = self._discover_protected_resource_metadata()
        auth_servers = resource_metadata.get("authorization_servers") or []
        if not auth_servers:
            raise OAuthError(
                "Robinhood's protected resource metadata did not list an authorization server"
            )
        auth_meta = self._discover_authorization_server_metadata(auth_servers[0])

        client_id = get_secret(_PREFIX + "client_id")
        if not client_id:
            client_id = self._register_client(auth_meta)
            set_secret(_PREFIX + "client_id", client_id)

        pkce = generate_pkce_pair()
        state = generate_state()
        redirect_uri = f"http://127.0.0.1:{self.redirect_port}/callback"

        auth_params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": pkce.challenge,
            "code_challenge_method": pkce.method,
            "state": state,
            "resource": resource,
        }
        auth_url = f"{auth_meta['authorization_endpoint']}?{urlencode(auth_params)}"

        print(
            "[cream-agent] Opening your browser to authorize Cream Agent's "
            f"access to your Robinhood Agentic account:\n  {auth_url}"
        )
        webbrowser.open(auth_url)

        result = wait_for_callback(self.redirect_port)
        if result.error:
            raise OAuthError(
                f"Robinhood authorization failed: {result.error_description or result.error}"
            )
        if result.state != state:
            raise OAuthError("OAuth state mismatch on the Robinhood callback — aborting")
        if not result.code:
            raise OAuthError("No authorization code received from Robinhood")

        token_resp = self._http.post(
            auth_meta["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": result.code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "code_verifier": pkce.verifier,
                "resource": resource,
            },
        )
        token_resp.raise_for_status()
        self._store_tokens(token_resp.json(), auth_meta["token_endpoint"], resource)

    def refresh(self) -> bool:
        refresh_token = get_secret(_PREFIX + "refresh_token")
        token_endpoint = get_secret(_PREFIX + "token_endpoint")
        client_id = get_secret(_PREFIX + "client_id")
        if not (refresh_token and token_endpoint and client_id):
            return False

        resource = get_secret(_PREFIX + "resource") or canonical_resource_uri(self.mcp_url)
        resp = self._http.post(
            token_endpoint,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "resource": resource,
            },
        )
        if resp.status_code != 200:
            return False
        self._store_tokens(resp.json(), token_endpoint, resource)
        return True

    def disconnect(self) -> None:
        for suffix in (
            "access_token",
            "refresh_token",
            "token_expiry",
            "token_endpoint",
            "resource",
            "client_id",
            "client_secret",
        ):
            delete_secret(_PREFIX + suffix)

    # -- discovery (RFC 9728 / RFC 8414) ---------------------------------

    def _discover_protected_resource_metadata(self) -> dict:
        parsed = urlsplit(self.mcp_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        try:
            # MCP servers speak JSON-RPC over POST; probing with GET can get a
            # 405 instead of the 401 challenge (observed against Robinhood's
            # real server), so POST is what actually triggers WWW-Authenticate.
            resp = self._http.post(self.mcp_url)
            if resp.status_code == 401:
                metadata_url = _extract_resource_metadata_url(resp.headers.get("WWW-Authenticate", ""))
                if metadata_url:
                    meta_resp = self._http.get(metadata_url)
                    meta_resp.raise_for_status()
                    return meta_resp.json()
        except httpx.HTTPError:
            pass

        resp = self._http.get(f"{origin}/.well-known/oauth-protected-resource")
        resp.raise_for_status()
        return resp.json()

    def _discover_authorization_server_metadata(self, auth_server_base: str) -> dict:
        """Fetch RFC 8414 authorization server metadata.

        RFC 8414 says the well-known suffix is inserted *between* the origin
        and the issuer's path (``https://host/.well-known/oauth-authorization-server/path``),
        not appended after the full path. Verified against Robinhood's real
        server: ``/mcp/trading/.well-known/oauth-authorization-server`` 404s,
        while the path-insertion form returns the document. We still try a
        couple of fallback shapes in case a future server (or a different
        MCP integration reusing this client) doesn't follow the RFC exactly.
        """
        parsed = urlsplit(auth_server_base)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path.rstrip("/")

        candidates = [f"{origin}/.well-known/oauth-authorization-server{path}"]
        if path:
            candidates.append(f"{origin}/.well-known/oauth-authorization-server")
            candidates.append(f"{origin}{path}/.well-known/oauth-authorization-server")

        last_error: Optional[Exception] = None
        for url in candidates:
            try:
                resp = self._http.get(url)
                if resp.status_code == 200:
                    return resp.json()
            except httpx.HTTPError as e:
                last_error = e

        raise OAuthError(
            f"Could not find authorization server metadata for {auth_server_base}; "
            f"tried {candidates}"
            + (f" (last error: {last_error})" if last_error else "")
        )

    def _register_client(self, auth_meta: dict) -> str:
        """Register a public, PKCE-only client (RFC 7591) and return its
        ``client_id``.

        We ask for ``token_endpoint_auth_method: "none"`` because this client
        never sends a ``client_secret`` on token/refresh requests — it's a
        native app, so a bundled secret couldn't be kept confidential anyway,
        and PKCE is what actually secures the flow. If the authorization
        server registers us as a confidential client and hands back a
        ``client_secret`` regardless, we don't support authenticating with
        it (no client_secret_post/basic auth is implemented), so we reject
        that response explicitly rather than silently discarding the secret
        and sending unauthenticated token requests to a server that expects
        one.
        """
        registration_endpoint = auth_meta.get("registration_endpoint")
        if not registration_endpoint:
            raise OAuthError(
                "Robinhood's authorization server doesn't support dynamic client "
                "registration (RFC 7591). A pre-registered client_id would need to "
                "be configured manually — see the Robinhood MCP setup docs."
            )
        redirect_uri = f"http://127.0.0.1:{self.redirect_port}/callback"
        resp = self._http.post(
            registration_endpoint,
            json={
                "client_name": "Cream Agent",
                "redirect_uris": [redirect_uri],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("client_secret"):
            raise OAuthError(
                "Robinhood's authorization server registered Cream Agent as a "
                "confidential client and returned a client_secret, but this client "
                "only implements the public, secret-less PKCE flow "
                "(token_endpoint_auth_method='none') and has no way to authenticate "
                "with a client_secret. Refusing to proceed rather than silently "
                "sending unauthenticated token requests to a server that expects one."
            )
        return data["client_id"]

    # -- token storage ----------------------------------------------------

    def _store_tokens(self, token_data: dict, token_endpoint: str, resource: str) -> None:
        set_secret(_PREFIX + "access_token", token_data["access_token"])
        if "refresh_token" in token_data:
            set_secret(_PREFIX + "refresh_token", token_data["refresh_token"])
        expires_in = token_data.get("expires_in")
        if expires_in is not None:
            set_secret(_PREFIX + "token_expiry", str(time.time() + float(expires_in)))
        else:
            delete_secret(_PREFIX + "token_expiry")
        set_secret(_PREFIX + "token_endpoint", token_endpoint)
        set_secret(_PREFIX + "resource", resource)


def _extract_resource_metadata_url(www_authenticate: str) -> Optional[str]:
    match = _RESOURCE_METADATA_RE.search(www_authenticate)
    return match.group(1) if match else None
