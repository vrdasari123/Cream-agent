# Cream Agent: Memory, Order Tracking, and the Observatory UI

Design plan for the next generation of Cream Agent, building on the MCP-native
pivot in PR #29. Status: proposed. This document is the source of truth for
the P1–P5 epics on the issue board.

## 1. Context

PR #29 repositions Cream Agent as an MCP-native trading workspace: the user
brings their own MCP-capable agent (Codex verified first; Claude, Cursor,
Windsurf, Kimi, ChatGPT planned), that client owns Robinhood Trading MCP
authentication, and this repo supplies the durable operating layer —
`AGENTS.md` safety policy, workflow docs, and journal/audit conventions.

This plan extends that layer in three directions:

1. **A structured memory store** — different memory types the agent reads and
   writes as files, so knowledge survives across sessions and across clients.
2. **Agentic order tracking** — every order's full lifecycle recorded as
   durable state, from draft ticket through confirmation to fill, with
   snapshots that make profit/loss computable over time.
3. **The Observatory** — a local, read-only web UI over the memory store:
   workflows, order history, P/L, a memory browser, and a live system diagram
   that animates an order's flow through the Cream system in real time
   (which memory files were read, which MCP tools were called, where the
   confirmation gate fired).

## 2. Core design principle: the agent writes, the UI observes

The single rule that keeps this compatible with "bring your own agent":

> **All runtime intelligence lives in the user's MCP client. The repo defines
> what the agent records; the UI only renders what was recorded.**

Consequences:

- The web UI has **zero brokerage access**. It never calls Robinhood Trading
  MCP, never sees a token, never submits anything. Everything it displays came
  from files the agent wrote into the workspace.
- The UI is not in the agent's execution path. Killing the UI changes nothing
  about a trading session. It is an observatory, not a runtime.
- Telemetry is **agent-authored**: `AGENTS.md` instructs the agent to emit
  structured events as it works. This is exactly the "agentic viewpoint" — the
  trace is the agent's own account of what it did, written as it does it.
- Because the store is plain files, it is portable across MCP clients for
  free. Switch from Codex to Claude and your memory, orders, and journal come
  with you.

Trust model (stated honestly): agent-authored telemetry is an audit trail, not
an enforcement layer. A misbehaving agent could fail to record an event. The
enforcement layer remains the `AGENTS.md` confirmation rules and the user's
final confirmation before any live order action. Helper CLIs (below) make
recording the path of least resistance so the trail stays complete in
practice.

## 3. The memory store

All durable state lives under `memory/` at the repo root. Memory is organized
by type, mirroring how agent memory is usually taxonomized:

```text
memory/
  events/       Episodic memory — append-only JSONL event streams, one file
                per session. The raw record of what happened.
  orders/       Working + record memory — one JSON file per order, tracking
                the full lifecycle from draft to terminal state.
  journal/      Narrative memory — dated markdown notes: trade reasoning,
                review write-ups, decisions. (Replaces PR #29's docs/journal/.)
  knowledge/    Semantic memory — durable facts the agent should consult:
                  preferences.md      user's standing preferences
                  risk-limits.md      position-size caps, concentration
                                      limits, never-trade lists
                  theses/<TICKER>.md  per-symbol investment theses
  snapshots/    Time-series memory — periodic portfolio/balance snapshots
                that make P/L and an equity curve computable.
```

Privacy default: `memory/` is **gitignored by default** — it contains real
account data. Users who want their journal or knowledge files versioned in
their private clone can un-ignore those subdirectories deliberately. The repo
ships the directory scaffolding plus templates, never real data.

### 3.1 Event log (episodic memory)

One JSONL file per session: `memory/events/<session-id>.jsonl`, where
`session-id` is `YYYY-MM-DD-<short-random>`. Each line:

```json
{"ts": "2026-07-25T14:03:22Z", "session": "2026-07-25-a3f2", "seq": 14,
 "type": "mcp_call", "actor": "agent",
 "data": {"server": "robinhood-trading", "tool": "get_positions",
          "summary": "fetch current positions for account review"}}
```

Event types (initial vocabulary):

| Type | Emitted when |
| --- | --- |
| `session_started` / `session_ended` | a working session begins/ends |
| `workflow_started` / `workflow_completed` | a docs/workflows/ doc is entered/finished |
| `memory_read` / `memory_write` | any file under `memory/` is consulted or updated |
| `mcp_call` / `mcp_result` | a Robinhood Trading MCP tool is invoked / returns |
| `decision` | the agent records a judgment worth auditing |
| `ticket_drafted` | an order ticket file is created (status: draft) |
| `confirmation_requested` / `confirmation_received` | the final-confirmation gate |
| `order_submitted` / `order_status` | live order action and subsequent status changes |
| `journal_written` | a journal note is saved |

Schema is versioned (`"v": 1` field reserved) and validated by tests.

### 3.2 Helper CLI

Hand-writing JSONL invites malformed lines. A small stdlib-only helper keeps
appends atomic and schema-checked:

```bash
cream-agent log --session 2026-07-25-a3f2 --type mcp_call \
  --data '{"server":"robinhood-trading","tool":"get_positions"}'

cream-agent snapshot < positions.json   # validates + writes a snapshot file
```

`AGENTS.md` will direct agents to prefer the helper and fall back to direct
file appends in the same format when the helper is unavailable. The helper
never talks to the network; the agent supplies data it obtained through its
own MCP connection.

### 3.3 Order records (lifecycle tracking)

One file per order: `memory/orders/<order-id>.json`, with
`order-id = YYYY-MM-DD-<symbol>-<side>-<nnn>`.

```json
{
  "order_id": "2026-07-25-vti-buy-001",
  "created": "2026-07-25T14:10:05Z",
  "ticket": {
    "symbol": "VTI", "side": "buy", "quantity": 5,
    "order_type": "limit", "limit_price": 275.00, "time_in_force": "day"
  },
  "status": "draft",
  "history": [
    {"ts": "2026-07-25T14:10:05Z", "status": "draft",
     "note": "prepared via order-ticket workflow"}
  ],
  "links": {
    "session": "2026-07-25-a3f2",
    "journal": "memory/journal/2026-07-25-vti-entry.md"
  }
}
```

State machine, enforced by convention and validated by tests:

```text
draft → confirmed → submitted → filled
                 ↘ canceled      ↘ partially_filled → filled | canceled
   (any state) → rejected | abandoned
```

The transitions map one-to-one onto the existing `order-ticket.md` workflow
and the `AGENTS.md` confirmation rules: a ticket cannot reach `submitted`
without a recorded `confirmation_received` event, and preparing a ticket
(`draft`) is still never permission to submit it.

### 3.4 Snapshots and P/L

`memory/snapshots/<ISO-timestamp>.json` — positions, balances, and marks the
agent captured from Robinhood Trading MCP reads:

```json
{"ts": "2026-07-25T14:00:00Z",
 "balances": {"cash": 1523.10, "buying_power": 3046.20},
 "positions": [
   {"symbol": "VTI", "qty": 12, "avg_cost": 260.10, "mark": 274.55}
 ]}
```

P/L is **derived, never authored**:

- **Realized** — from fills in `memory/orders/` history.
- **Unrealized** — latest snapshot marks vs. avg cost (as reported by the
  MCP's position data; field mapping to be pinned down against the real
  server in P2).
- **Equity curve** — snapshot series over time; robust even when per-lot cost
  basis is unavailable.

Workflow docs get a small addition: account review and portfolio review end
by writing a snapshot, so the time series accumulates as a side effect of
normal use.

## 4. The Observatory (local web UI)

A read-only dashboard over `memory/` and `docs/workflows/`.

**Stack:** FastAPI + uvicorn + `watchfiles`, installed as an optional extra
(`pip install -e ".[ui]"`), launched with `cream-agent-ui`. Frontend is a
no-build-step single page (vanilla JS + SSE + SVG) so the repo stays light
and fully offline-capable.

**Security posture:**

- Binds `127.0.0.1` only — enforced in code, covered by tests.
- Read-only by construction: no route mutates the filesystem; no route
  proxies to any MCP server or external network.
- Holds no secrets. If the process is compromised, the blast radius is
  "read local files the user already owns."

**Views:**

1. **Dashboard** — latest snapshot (balances, positions), open order tickets,
   recent events, last journal entries.
2. **Workflows** — renders `docs/workflows/` and shows run history per
   workflow (from `workflow_started/completed` events): when it ran, in which
   session, what it produced.
3. **Orders** — lifecycle table across `memory/orders/` (filter by status),
   with a detail view showing the full ticket, state history timeline, and
   linked journal note + session.
4. **P/L & history** — equity curve from snapshots, realized/unrealized
   breakdown, per-symbol P/L.
5. **Memory browser** — browse knowledge, journal, and event files; see what
   the agent knows and when it last consulted it.
6. **Flow** — the live system diagram (next section).

## 5. The live order-flow diagram

The centerpiece view: a system diagram of the Cream architecture that
animates in real time as the agent works.

**Static topology** (rendered as SVG, defined once in a small JSON topology
file):

```text
┌──────┐   ┌────────────────┐   ┌───────────────┐   ┌──────────────────┐
│ User │──▶│ MCP client     │──▶│ AGENTS.md     │──▶│ Workflow doc     │
└──────┘   │ (Codex/Claude) │   │ safety policy │   │ (e.g. order-     │
           └───────┬────────┘   └───────────────┘   │  ticket.md)      │
                   │                                └──────────────────┘
                   ├──────────────▶ memory/knowledge · journal · events
                   │                        (reads & writes)
                   ├──────────────▶ robinhood-trading MCP (tool calls)
                   │
                   ▼
           ┌────────────────┐    ┌──────────────┐    ┌─────────────────┐
           │ Confirmation   │───▶│ Order record │───▶│ Journal + event │
           │ gate           │    │ (lifecycle)  │    │ log             │
           └────────────────┘    └──────────────┘    └─────────────────┘
```

**Live mode:** the server tails `memory/events/` with `watchfiles` and pushes
events over SSE. As each event arrives, the corresponding node and edge light
up — a `memory_read` pulses the knowledge node and names the file, an
`mcp_call` pulses the Robinhood node and names the tool, a
`confirmation_requested` highlights the gate in a distinct "waiting" state. A
side ticker lists the raw events as they stream. Watching an order go from
"prepare a ticket for 5 VTI" to `filled` shows, live: which theses and risk
limits were consulted, every MCP tool touched, the confirmation exchange, and
the record/journal writes.

**Replay mode:** pick any past session, scrub a timeline, and step through
its events on the same diagram — a post-trade review tool, and the natural
way to audit "what exactly did the agent do here?"

## 6. Phases

| Phase | Scope | Depends on |
| --- | --- | --- |
| **P1 — Memory foundation** | `memory/` layout, event schema + vocabulary, `cream-agent log` helper, AGENTS.md event/memory conventions, knowledge templates, schema tests | PR #29 |
| **P2 — Order tracking & P/L records** | order lifecycle files + state machine, snapshot convention + helper, P/L derivation spec pinned against real MCP field names | P1 |
| **P3 — Observatory core** | FastAPI scaffold (localhost, read-only, `[ui]` extra), dashboard/orders/workflows/memory/P-L views, hardening tests | P1, P2 |
| **P4 — Live flow diagram** | SSE event stream, topology + live SVG rendering, session replay | P3 |
| **P5 — Clients & cleanup** | PR #29 amendments landed, second client verified (Claude Code), quarantined legacy runtime deleted | P1 |

## 7. Required changes to PR #29

PR #29 is the right pivot and should land largely as-is; the deltas below keep
it from contradicting this plan the day after it merges:

1. **Journal path.** `AGENTS.md` and the README point at `docs/journal/`; this
   plan puts all agent-written data under `memory/` (docs are the doc plane,
   memory is the data plane). Change references to `memory/journal/` — cheap
   now, a migration later.
2. **Gitignore.** Add `memory/` (with a `!memory/**/.gitkeep` or template
   exception) so real account data never lands in a public clone by accident.
3. **README positioning.** One paragraph in "Product direction" noting the
   planned memory store and the optional local Observatory, with the explicit
   framing that the dashboard *observes* the workspace and never trades or
   authenticates — so "not another chat app / not a hosted agent service"
   stays true.
4. **AGENTS.md Artifacts section.** Note that structured event emission
   conventions are coming (P1) so agents built against PR #29's wording don't
   entrench a conflicting ad-hoc format.
5. *(Optional, non-blocking)* `doctor.py` gains a check for the `[ui]` extra
   once P3 lands; nothing to do in PR #29 itself.

None of these are architectural; all are small edits to the PR's docs plus one
`.gitignore` line.
