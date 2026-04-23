# Claude Code Token Usage Tracker

A one-command install that adds a Stop hook to Claude Code. After each turn it
reads the session transcript, tallies tokens (input, output, cache read, cache
creation), and writes a human-readable block to `claude-token-usage.txt` in the
project folder you ran Claude in.

## What you get

Each session gets a block, updated in place on every turn:

```
------------------------------------------------------------------------
Session: 8f556e97-977e-4e77-b28f-bccd9e61160d
Updated: 2026-04-23 15:44:21   Model: claude-opus-4-7   Turns: 12

                       input       output    cache_read   cache_creation
  Last turn               12          482        82,615              298
  Session total          132       28,941     1,327,817          162,113

  Context window: peak=82,914   final=82,914
```

- **Last turn** — tokens from the most recent request only.
- **Session total** — cumulative across the whole session.
- **Context window** — peak and current size (input + cache_read + cache_creation).

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
3. Is idempotent — re-running replaces its own hook cleanly and will not create
   duplicates.

After install, in Claude Code open `/hooks` once (or restart) so the hook is
picked up by your current session. New sessions pick it up automatically.

## Where the file is written

The hook's working directory is the project folder Claude Code is running in,
so `claude-token-usage.txt` lands in that folder. Each project gets its own
file; sessions from the same project append/update blocks in that file.

## Uninstall

1. Delete `~/.claude/scripts/claude-token-usage.py`.
2. Open `~/.claude/settings.json` and remove the `Stop` entry whose command
   references `claude-token-usage.py`. (Leave the rest of the file alone.)

## Notes

- Token accounting matches what Anthropic bills on. Most of the `cache_read`
  number is the Claude Code system prompt + tool schemas, which are cached
  at ~10% the price of fresh input. A "hi" session showing 20k+ tokens is
  normal; it is mostly cheap cache reads, not new tokens.
- This tool does **not** and cannot show "tokens remaining" against your
  Claude.ai subscription — Anthropic does not expose that number locally.
  It only reports what *you* consumed.
