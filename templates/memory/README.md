# Private memory bootstrap

Copy the contents of this directory to `memory/` when initializing a workspace.
The root `memory/` directory is ignored by git because events, order records,
snapshots, and notes may contain account or personal information.

```text
memory/
├── events/       One validated JSONL stream per client session
├── journal/      Human-readable review and decision notes
├── knowledge/    Preferences, risk limits, and per-ticker theses
│   └── theses/
├── orders/       One state-machine JSON record per order ticket
└── snapshots/    Point-in-time account data (schema planned in issue #41)
```

Do not copy real runtime data back into `templates/`. If you deliberately
version selected private memory in a private fork, review it for account data,
credentials, identifiers, and personal information first.
