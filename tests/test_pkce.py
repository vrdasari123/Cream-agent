import base64
import hashlib

from cream_agent.auth.pkce import canonical_resource_uri, generate_pkce_pair, generate_state


def test_pkce_challenge_matches_verifier():
    pair = generate_pkce_pair()
    expected_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(pair.verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    assert pair.challenge == expected_challenge
    assert pair.method == "S256"


def test_pkce_pairs_are_unique():
    a = generate_pkce_pair()
    b = generate_pkce_pair()
    assert a.verifier != b.verifier
    assert a.challenge != b.challenge


def test_state_is_unique_and_url_safe():
    a = generate_state()
    b = generate_state()
    assert a != b
    assert "+" not in a and "/" not in a and "=" not in a


def test_canonical_resource_uri_strips_trailing_slash_and_lowercases():
    assert canonical_resource_uri("HTTPS://Agent.Robinhood.COM/mcp/trading/") == (
        "https://agent.robinhood.com/mcp/trading"
    )


def test_canonical_resource_uri_leaves_root_path_alone():
    assert canonical_resource_uri("https://Example.com") == "https://example.com"


def test_canonical_resource_uri_drops_fragment():
    assert canonical_resource_uri("https://example.com/mcp#frag") == "https://example.com/mcp"
