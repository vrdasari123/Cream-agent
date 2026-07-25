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

## Required fields

- symbol
- side
- quantity or notional
- order type
- time in force
- limit price for limit orders
- stop price for stop or stop-limit orders

## Suggested sequence

1. Confirm the user wants a draft ticket only.
2. Collect missing order terms.
3. Restate the completed ticket.
4. Add key risk checks or operational questions.
5. End with a plain statement that no order has been submitted.

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
