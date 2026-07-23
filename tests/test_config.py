import os

import pytest

from cream_agent.config.settings import CreamConfig, config_dir, load_config, save_config


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("CREAM_AGENT_HOME", str(tmp_path))
    return tmp_path


def test_config_dir_respects_env_override(isolated_home):
    assert config_dir() == isolated_home


def test_load_config_returns_defaults_when_missing(isolated_home):
    config = load_config()
    assert config.robinhood_mcp_url == "https://agent.robinhood.com/mcp/trading"
    assert config.require_trade_confirmation is True
    assert config.anthropic_model is None


def test_save_and_load_round_trip(isolated_home):
    config = CreamConfig(anthropic_model="claude-x", oauth_redirect_port=9999)
    save_config(config)

    loaded = load_config()
    assert loaded.anthropic_model == "claude-x"
    assert loaded.oauth_redirect_port == 9999
    assert (isolated_home / "config.yaml").exists()


def test_from_dict_ignores_unknown_fields():
    config = CreamConfig.from_dict({"anthropic_model": "foo", "bogus_field": "bar"})
    assert config.anthropic_model == "foo"
    assert not hasattr(config, "bogus_field")
