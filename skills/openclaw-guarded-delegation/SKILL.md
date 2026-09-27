---
name: OpenClaw guarded delegation
description: >-
  use this when Bob needs OpenClaw or Cursor Cloud Agent handoff rules — native
  Grok Bot Cloud Agents first, optional Integration CLI fallback, never merge
  Andrea lockstep into Bob
---
# OpenClaw guarded delegation

## When
Use when Bob needs OpenClaw or Cursor Cloud Agent handoff rules, consolidating Cursor-OpenClaw-Integration into Grok Bot / Bob-the-Bot, or deciding native Cloud Agents vs CLI fallback.

Jeff north star: absorb skills and reusable tool code into Grok Bot / Bob-the-Bot; minimize separate tool apps; keep real products and Andrea bridge + gateway secrets separate.

## Architecture
- Bob/Grok = conductor; native Cloud Agents first
- Andrea = Messages wire only; keep openclaw-* bridge in Andrea
- OpenClaw Runtime = local LaunchAgent; never auto-restart; no secrets in Bob
- Integration = legacy; absorb CLI/handoff; leave andrea_sync

## Order
1. Native Cloud Agents
2. Optional CLI fallback dry-run first
3. Never second Andrea in Bob

## Hard fences
Dry-run default; no gateway restart; no cred writes; no auto-send; Jeff owns merge/Latest/spend/feel; one WebJam lane.

## Dashboard
Work-now shows assignments (not Running); include Gemini+MiniMax; WashOps label; Barker = rupret007/barker.
