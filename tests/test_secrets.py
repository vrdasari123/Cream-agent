import json

import pytest

from cream_agent.config import secrets


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CREAM_AGENT_HOME", str(tmp_path))
    secrets._fallback_warned = False
    return tmp_path


def test_round_trip_via_whatever_backend_is_available():
    secrets.set_secret("thing", "value123")
    assert secrets.get_secret("thing") == "value123"
    secrets.delete_secret("thing")
    assert secrets.get_secret("thing") is None


def test_missing_secret_returns_none():
    assert secrets.get_secret("does-not-exist") is None


def test_fallback_file_used_when_keyring_unavailable(monkeypatch, isolated_home):
    def _boom(*args, **kwargs):
        raise RuntimeError("no keyring backend")

    monkeypatch.setattr("keyring.set_password", _boom)
    monkeypatch.setattr("keyring.get_password", _boom)
    monkeypatch.setattr("keyring.delete_password", _boom)

    secrets.set_secret("api_key", "sekrit")

    fallback_path = isolated_home / "secrets.json"
    assert fallback_path.exists()
    data = json.loads(fallback_path.read_text())
    assert data["api_key"] == "sekrit"

    assert secrets.get_secret("api_key") == "sekrit"

    secrets.delete_secret("api_key")
    assert json.loads(fallback_path.read_text()) == {}


def test_fallback_file_has_owner_only_permissions(monkeypatch, isolated_home):
    import stat

    def _boom(*args, **kwargs):
        raise RuntimeError("no keyring backend")

    monkeypatch.setattr("keyring.set_password", _boom)
    monkeypatch.setattr("keyring.get_password", _boom)

    secrets.set_secret("api_key", "sekrit")
    mode = (isolated_home / "secrets.json").stat().st_mode
    assert stat.S_IMODE(mode) == stat.S_IRUSR | stat.S_IWUSR
