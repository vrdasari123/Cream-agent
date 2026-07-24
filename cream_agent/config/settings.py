"""Non-secret configuration for Cream Agent, stored at ``~/.creamagent/config.yaml``.

Secrets (API keys, OAuth tokens) never live here — see
:mod:`cream_agent.config.secrets`.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_ROBINHOOD_MCP_URL = "https://agent.robinhood.com/mcp/trading"
CONFIG_FILENAME = "config.yaml"


def config_dir() -> Path:
    """Directory holding Cream Agent's local state.

    Overridable via ``CREAM_AGENT_HOME`` (used by tests and anyone who wants
    an isolated config, e.g. multiple Robinhood accounts).
    """
    override = os.environ.get("CREAM_AGENT_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".creamagent"


@dataclass
class CreamConfig:
    # Which Claude model to use. None lets the Agent SDK pick its default.
    anthropic_model: str | None = None

    # Robinhood's Agentic Trading MCP endpoint.
    robinhood_mcp_url: str = DEFAULT_ROBINHOOD_MCP_URL

    # Local loopback port used for the OAuth redirect during the Robinhood
    # authorization flow.
    oauth_redirect_port: int = 8765

    # Safety defaults (see cream_agent.safety). M1 ships read-only, so this
    # flag is not yet enforceable for trades, but is recorded up front so
    # M2's trading layer has a documented, user-visible default to honor.
    require_trade_confirmation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CreamConfig":
        known = {f: v for f, v in data.items() if f in cls.__dataclass_fields__}
        return cls(**known)


def config_path() -> Path:
    return config_dir() / CONFIG_FILENAME


def load_config() -> CreamConfig:
    path = config_path()
    if not path.exists():
        return CreamConfig()
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return CreamConfig.from_dict(data)


def save_config(config: CreamConfig) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(config.to_dict(), f, sort_keys=False)
