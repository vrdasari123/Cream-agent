# Workflow: Portfolio And Risk Review

Use this when the user wants exposure analysis, concentration checks, or a
discussion of portfolio risk without placing trades.

## Goal

Summarize the portfolio's current shape and identify obvious risks such as:

- concentration by single name
- sector concentration
- cash drag or liquidity concentration
- outsized recent winners or losers
- mismatch between stated goals and current holdings

## Rules

- Read-only by default.
- Do not turn a risk review into an order recommendation automatically.
- If proposing possible next steps, label them as options, not instructions.
- Make it explicit when additional context is needed for a sound risk judgment.
- Consult `memory/knowledge/preferences.md`,
  `memory/knowledge/risk-limits.md`, and theses for held tickers when present.
- Log knowledge reads and every MCP call/result using the event conventions in
  `AGENTS.md`.

## Suggested sequence

1. Emit session/workflow start events and log relevant knowledge reads.
2. Confirm the review is analytical and read-only.
3. Inspect positions and current weights.
4. Group exposures by sector, theme, or asset type when possible.
5. Compare exposures with recorded risk limits; treat absent limits as unknown.
6. Highlight concentrations and uncertainty.
7. End with options or questions, not live actions. Write a requested journal
   note and emit workflow/session completion events.

## Output template

```md
# Portfolio Risk Review

Date: YYYY-MM-DD

## Portfolio Shape
- Largest positions:
- Sector or theme concentrations:
- Cash posture:

## Risks
- 

## Missing context
- 

## Possible next steps
- 
```
