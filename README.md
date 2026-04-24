# Claude Code Token Usage Tracker

A one-command install that adds a Stop hook to Claude Code. After each turn it
reads the session transcript, tallies token usage, and writes a per-session
block to `claude-token-usage.txt` in the project folder you ran Claude in.

## What the output looks like

```
------------------------------------------------------------------------
Session: 8f556e97-977e-4e77-b28f-bccd9e61160d
Started: 2026-04-23 15:43:37   Updated: 2026-04-23 15:44:21
Duration: 43s   Model: claude-opus-4-7 (opus pricing)   Turns: 2

                       input       output    cache_read   cache_creation
  Last turn                6          107        26,979               24
  Session total           12          122        46,257            7,725

  Context window:      peak=27,009   final=27,009
  Cache efficiency:    85.7% of prompt served from cache
  API-equivalent cost: $0.3105 session   $0.0493 last turn
    breakdown: input=$0.0002  output=$0.0092  cache_read=$0.0694  cache_creation=$0.2318
    note: informational only - subscription users pay a flat monthly fee, not this
```

Each session = one block, updated in place on every turn. New sessions append.

### What each line means

- **Last turn / Session total** — raw token counts from Claude's `usage` field.
- **Context window** — per-turn context size (input + cache_read + cache_creation).
  `peak` = largest; `final` = current turn.
- **Cache efficiency** — `cache_read / (input + cache_read + cache_creation)`. High
  means prompt caching is working well; most of your prompt was served cheaply.
- **API-equivalent cost** — USD at public API rates, split 5-min vs 1-hour cache
  tiers. Pro / Max 5x / Max 20x subscribers don't pay this — they pay a flat
  monthly fee. Treat the number as "what this session would cost on the API"
  (a proxy for absolute session weight), **not** as a bill.
  Pricing tier is auto-detected from the model name (opus / sonnet / haiku).

## Prerequisites

- Claude Code installed.
- Python 3 on `PATH` (`python --version` must work).

## Install

Extract the folder anywhere. From inside it:

**macOS / Linux / Git Bash:**
```bash
bash install.sh
```

**Windows PowerShell:**
```powershell
.\install.ps1
```

The installer:
1. Copies `claude-token-usage.py` to `~/.claude/scripts/`.
2. Merges a Stop-hook entry into `~/.claude/settings.json` (preserving anything
   already there).
3. Is idempotent — re-running replaces its own hook cleanly.

After install, open `/hooks` in Claude Code once (or restart) so the hook is
picked up by your current session. New sessions pick it up automatically.

## Where the file lives

The hook's working directory is whatever folder Claude Code is running in, so
`claude-token-usage.txt` is written there. Each project gets its own file;
sessions from the same project accumulate blocks in that file.

## Uninstall

1. Delete `~/.claude/scripts/claude-token-usage.py`.
2. Open `~/.claude/settings.json` and remove the `Stop` entry whose command
   references `claude-token-usage.py`.

## Notes

- Cost estimates use public Anthropic API pricing at the time of writing.
  Rates are in the `PRICING` dict at the top of `claude-token-usage.py` —
  edit there if rates change.
- This tool does **not** and cannot show "tokens remaining" against your
  Claude.ai subscription — Anthropic does not expose that number locally.
  It only reports what you consumed.
