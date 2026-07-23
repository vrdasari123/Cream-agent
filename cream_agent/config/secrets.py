"""Secret storage for Cream Agent.

Prefers the OS keyring (macOS Keychain, Windows Credential Locker, the Secret
Service on Linux). Many headless Linux environments have no keyring daemon
running, so if the OS keyring is unavailable we fall back to a local file at
``~/.creamagent/secrets.json`` with owner-only permissions (0600). That file
is plaintext, not encrypted — it's a fallback for local, single-user
machines, not a substitute for a real keyring. The fallback is announced once
per process so it's never silent.
"""

from __future__ import annotations

import json
import stat
import sys
import threading
from pathlib import Path
from typing import Optional

SERVICE_NAME = "cream-agent"

_fallback_warned = False
_lock = threading.Lock()


def _fallback_path() -> Path:
    from cream_agent.config.settings import config_dir

    return config_dir() / "secrets.json"


def _warn_fallback_once() -> None:
    global _fallback_warned
    with _lock:
        if not _fallback_warned:
            _fallback_warned = True
            print(
                "[cream-agent] No OS keyring backend available — storing secrets "
                f"in {_fallback_path()} instead (owner-only file permissions, "
                "not encrypted). Set up a keyring backend for stronger protection.",
                file=sys.stderr,
            )


def _fallback_read() -> dict:
    path = _fallback_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _fallback_write(data: dict) -> None:
    path = _fallback_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def get_secret(name: str) -> Optional[str]:
    try:
        import keyring

        value = keyring.get_password(SERVICE_NAME, name)
        if value is not None:
            return value
        # Fall through to the file fallback in case a prior run stored it
        # there (e.g. keyring became unavailable between runs).
    except Exception:
        pass
    return _fallback_read().get(name)


def set_secret(name: str, value: str) -> None:
    try:
        import keyring

        keyring.set_password(SERVICE_NAME, name, value)
        return
    except Exception:
        _warn_fallback_once()
    data = _fallback_read()
    data[name] = value
    _fallback_write(data)


def delete_secret(name: str) -> None:
    try:
        import keyring

        keyring.delete_password(SERVICE_NAME, name)
    except Exception:
        pass
    data = _fallback_read()
    if name in data:
        del data[name]
        _fallback_write(data)
