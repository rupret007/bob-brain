---
name: Domino's pizza convoy
description: >-
  use this when Jeff wants Domino's pizza ordered and/or tracked — Bob does max
  in browser, Jeff Apple Pay only, tip 20%, live tracker beats to phone
---
# Domino's pizza convoy

Order Domino's through the box browser with Jeff on login/2FA/Apple Pay only. Track via official browser tracker; mirror short beats to phone. Never store cards, never auto-pay, never double-order.

## Hard rules
1. Jeff taps only: login, 2FA, Apple Pay confirm. Bob drives the cart.
2. Payment = Apple Pay. Bob never handles card numbers. No Link unless Jeff overrides.
3. Default tip = 20% unless Jeff says otherwise.
4. Anti double-order via `/workspace/dominos-live-order.json` — refuse second place while `active`.
5. Tracker source of truth = Domino's browser tracker / confirmation link / signed-in order status. No unofficial APIs by default.
6. Phone = short status; Grok Bot chat = full detail. Bob watches the same browser tracker.
7. No secrets in state files.

## Order path
1. Preflight lock file (idle vs active).
2. Open dominos.com in box browser; build cart from ask or `/workspace/dominos-usual-prefs.json`.
3. Checkout: tip 20%, select Apple Pay, summarize for Jeff.
4. request_box_help for Apple Pay / biometric.
5. After place: capture order id + tracker URL; set lock active; start finite 3–5 min tracker routine; self-delete on delivered/deadline.

## Tracker routine
Finite only while live. Each tick: read browser tracker stage; on change SendMessage Jeff (+ short phone mirror). Delete routine when delivered/picked up/cancelled or deadline (placed + 3h).

## Prefs
`/workspace/dominos-usual-prefs.json` — tip 20, apple_pay; Jeff fills usual pie later.

Full playbook also at `/workspace/dominos-pizza-convoy-SKILL.md`.
