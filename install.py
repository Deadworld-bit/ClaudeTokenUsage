#!/usr/bin/env python3
"""Installer for the Claude Code token-usage tracker.

- Copies claude-token-usage.py to ~/.claude/scripts/
- Merges a Stop-hook entry into ~/.claude/settings.json
- Idempotent: re-running replaces any previous install of this hook
  without touching other hooks or settings.
"""

import json
import os
import shutil
import sys
from pathlib import Path

SCRIPT_NAME = "claude-token-usage.py"
HOOK_MARKER = SCRIPT_NAME  # substring that identifies this tool in a hook command


def die(msg, code=1):
    sys.stderr.write(f"ERROR: {msg}\n")
    sys.exit(code)


def main():
    here = Path(__file__).resolve().parent
    src = here / SCRIPT_NAME
    if not src.is_file():
        die(f"tracker script not found next to installer: {src}")

    claude_dir = Path.home() / ".claude"
    scripts_dir = claude_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    dst = scripts_dir / SCRIPT_NAME
    shutil.copy2(src, dst)
    print(f"[OK] Tracker installed: {dst}")

    settings_path = claude_dir / "settings.json"
    settings = {}
    if settings_path.is_file():
        try:
            raw = settings_path.read_text(encoding="utf-8").strip()
            settings = json.loads(raw) if raw else {}
        except json.JSONDecodeError as e:
            die(f"{settings_path} is not valid JSON: {e}. Fix it and re-run.")

    hook_cmd = f'python "$HOME/.claude/scripts/{SCRIPT_NAME}"'
    new_entry = {"hooks": [{"type": "command", "command": hook_cmd}]}

    hooks = settings.setdefault("hooks", {})
    stop_hooks = hooks.setdefault("Stop", [])

    kept = []
    removed = 0
    for entry in stop_hooks:
        inner = entry.get("hooks") or []
        if any(HOOK_MARKER in (h.get("command") or "") for h in inner):
            removed += 1
        else:
            kept.append(entry)
    kept.append(new_entry)
    hooks["Stop"] = kept

    tmp = settings_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    tmp.replace(settings_path)

    verb = "Updated" if removed else "Added"
    print(f"[OK] {verb} Stop hook in {settings_path}" + (f" (replaced {removed} old entry)" if removed else ""))
    print()
    print("Next steps:")
    print("  1. In Claude Code, open /hooks once to reload (or restart Claude Code).")
    print("  2. After your next Claude turn, look for 'claude-token-usage.txt'")
    print("     in the project folder you ran Claude in.")
    print()
    print("To uninstall: delete the Stop entry from ~/.claude/settings.json and the")
    print(f"file {dst}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
