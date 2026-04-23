#!/usr/bin/env python3
"""Stop-hook: tally token usage from the current session's transcript
and write a per-session line to <cwd>/claude-token-usage.txt."""

import json
import os
import sys
from datetime import datetime

OUT_NAME = "claude-token-usage.txt"
SEPARATOR = "-" * 72


def read_payload():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def tally(transcript_path):
    totals = {
        "input": 0,
        "output": 0,
        "cache_read": 0,
        "cache_creation": 0,
        "turns": 0,
    }
    peak_context = 0
    final_context = 0
    last_model = ""
    last_turn = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}

    if not transcript_path or not os.path.isfile(transcript_path):
        return totals, peak_context, final_context, last_model, last_turn

    with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "assistant":
                continue
            msg = entry.get("message") or {}
            u = msg.get("usage") or {}
            if not u:
                continue

            inp = int(u.get("input_tokens") or 0)
            outp = int(u.get("output_tokens") or 0)
            cr = int(u.get("cache_read_input_tokens") or 0)
            cc = int(u.get("cache_creation_input_tokens") or 0)

            totals["input"] += inp
            totals["output"] += outp
            totals["cache_read"] += cr
            totals["cache_creation"] += cc
            totals["turns"] += 1

            ctx = inp + cr + cc
            if ctx > peak_context:
                peak_context = ctx
            final_context = ctx

            last_turn = {"input": inp, "output": outp, "cache_read": cr, "cache_creation": cc}

            if msg.get("model"):
                last_model = msg["model"]

    return totals, peak_context, final_context, last_model, last_turn


def format_block(session_id, totals, peak, final, model, last):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def n(v):
        return f"{v:,}"

    header = (
        f"{SEPARATOR}\n"
        f"Session: {session_id}\n"
        f"Updated: {ts}   Model: {model or '-'}   Turns: {totals['turns']}\n"
        f"\n"
    )
    table = (
        f"                       input       output    cache_read   cache_creation\n"
        f"  Last turn       {n(last['input']):>10}  {n(last['output']):>11}  {n(last['cache_read']):>12}   {n(last['cache_creation']):>14}\n"
        f"  Session total   {n(totals['input']):>10}  {n(totals['output']):>11}  {n(totals['cache_read']):>12}   {n(totals['cache_creation']):>14}\n"
        f"\n"
    )
    footer = f"  Context window: peak={n(peak)}   final={n(final)}\n\n"
    return header + table + footer


def _block_session_id(body):
    for line in body.splitlines()[:3]:
        if line.startswith("Session: "):
            return line[len("Session: "):].strip()
    return ""


def upsert(out_path, session_id, new_block):
    existing = ""
    if os.path.isfile(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                existing = f.read()
        except OSError:
            existing = ""

    # Split into (preamble, [block bodies]) by the separator line.
    # Legacy single-line entries stay in preamble untouched.
    parts = existing.split(SEPARATOR + "\n")
    preamble = parts[0] if parts else ""
    bodies = parts[1:] if len(parts) > 1 else []

    rebuilt = []
    replaced = False
    for body in bodies:
        if _block_session_id(body) == session_id:
            rebuilt.append(new_block)
            replaced = True
        else:
            rebuilt.append(SEPARATOR + "\n" + body)
    if not replaced:
        rebuilt.append(new_block)

    content = preamble + "".join(rebuilt)

    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, out_path)


def main():
    payload = read_payload()
    session_id = payload.get("session_id") or "unknown"
    transcript_path = payload.get("transcript_path") or ""
    cwd = payload.get("cwd") or os.getcwd()

    totals, peak, final, model, last = tally(transcript_path)
    block = format_block(session_id, totals, peak, final, model, last)

    out_path = os.path.join(cwd, OUT_NAME)
    try:
        upsert(out_path, session_id, block)
    except OSError as e:
        # Never block the Stop event on I/O errors
        sys.stderr.write(f"token-usage tracker: {e}\n")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
