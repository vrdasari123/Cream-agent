"""A durable, append-only record of every tool-call permission decision.

Independent of whatever the model tells the user happened — the point of an
audit log for a trading agent is that it doesn't depend on the model being
truthful or the terminal scrollback still being around.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from cream_agent.config.settings import config_dir

AUDIT_LOG_FILENAME = "audit.log"


class AuditLogger:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or (config_dir() / AUDIT_LOG_FILENAME)

    def log(
        self,
        tool_name: str,
        input_data: dict[str, Any],
        decision: str,
        reason: Optional[str] = None,
    ) -> None:
        entry = {
            "timestamp": time.time(),
            "tool_name": tool_name,
            "input": input_data,
            "decision": decision,
            "reason": reason,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        entries = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries
