# Workflow: Prepare Order Ticket

Use this when the user wants to stage a trade idea into a precise order ticket
without submitting it.

## Goal

Convert an intent such as "buy VTI" into a complete, reviewable ticket plus
risk notes and a confirmation-ready summary.

## Rules

- Preparing a ticket is not permission to submit it.
- Never submit, modify, or cancel an order from this workflow alone.
- Do not infer missing ticket fields.
- If terms are incomplete, ask for the missing terms first.
- Consult preferences, risk limits, and the matching ticker thesis under
  `memory/knowledge/` when present. Surface any conflict before confirmation.
- A draft record, a confirmed record, and a broker-submitted order are distinct
  states. Recording state never performs an MCP call.

## Required fields

- symbol
- side
- quantity or notional
- order type
- time in force
- limit price for limit orders
- stop price for stop or stop-limit orders

## Suggested sequence

1. Emit session/workflow start events and log relevant knowledge reads.
2. Confirm the user wants a draft ticket only.
3. Collect missing order terms and represent numeric values as decimal strings.
4. Create the draft record:

   ```bash
   cream-agent order create --session <session> \
     --ticket '{"symbol":"VTI","side":"buy","quantity":"5","order_type":"limit","limit_price":"275.00","time_in_force":"day"}'
   ```

5. Restate the exact ticket, record ID, ticket fingerprint, and risk checks.
6. End with a plain statement that no order has been submitted. Emit workflow
   and session completion events unless the user separately requests a live
   action.

## Separate live-action continuation

Only use this section after an explicit request to submit. It does not weaken
the repository-wide trade safety rules.

1. Re-read the draft and current risk limits. If ticket terms changed, create a
   new draft; do not mutate a previously confirmed ticket.
2. Emit `confirmation_requested` with `order_id`, `ticket_fingerprint`, and the
   exact terms. Restate those terms and ask for final confirmation in the same
   interaction.
3. Only after an explicit user confirmation, emit `confirmation_received` with
   `actor=user` and data:

   ```json
   {
     "order_id": "<order-id>",
     "ticket_fingerprint": "<sha256>",
     "confirmed": true
   }
   ```

4. Transition the local record to `confirmed`:

   ```bash
   cream-agent order transition <order-id> --session <session> --to confirmed
   ```

5. Emit `mcp_call`, perform the exact live MCP call, then emit `mcp_result`.
6. Only on successful broker acceptance, transition to `submitted`:

   ```bash
   cream-agent order transition <order-id> --session <session> --to submitted
   ```

7. Record later broker outcomes as `partially_filled`, `filled`, `canceled`, or
   `rejected`. Use `abandoned` only before submission.

## Output template

```md
# Draft Order Ticket

Date: YYYY-MM-DD

## Ticket
- Symbol:
- Side:
- Quantity / Notional:
- Order type:
- Limit price:
- Stop price:
- Time in force:

## Risk checks
- 

## Status
- No order has been submitted.
- A separate final confirmation is required before any live order action.
```
