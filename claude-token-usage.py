#!/usr/bin/env python3
"""Stop-hook: tally token usage from the current session's transcript
and write a per-session block to <cwd>/claude-token-usage.txt.

Tracks:
  - per-turn and cumulative tokens (input, output, cache_read, cache_creation)
  - 5-minute vs 1-hour cache_creation split (priced differently)
  - context window size (peak, final)
  - cache efficiency (% of prompt served from cache)
  - estimated cost in USD at current public API rates
  - session duration (first → last assistant turn timestamp)
"""

import json
import os
import sys
from datetime import datetime, timezone

OUT_NAME = "claude-token-usage.txt"
SEPARATOR = "-" * 72

# Per-1M-token USD rates. Used for cost estimation only.
# Claude.ai subscription users don't pay these — the flat monthly fee applies.
# Treat the USD figure as "what this session would cost at API rates".
PRICING = {
    "opus":   {"in": 15.00, "out": 75.00, "cache_5m": 18.75, "cache_1h": 30.00, "read": 1.50},
    "sonnet": {"in":  3.00, "out": 15.00, "cache_5m":  3.75, "cache_1h":  6.00, "read": 0.30},
    "haiku":  {"in":  1.00, "out":  5.00, "cache_5m":  1.25, "cache_1h":  2.00, "read": 0.10},
}


def read_payload():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def fmt_duration(delta_seconds):
    if delta_seconds is None or delta_seconds < 0:
        return "-"
    s = int(delta_seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m{s % 60}s"
    if s < 86400:
        return f"{s // 3600}h{(s % 3600) // 60}m"
    return f"{s // 86400}d{(s % 86400) // 3600}h"


def price_tier(model):
    m = (model or "").lower()
    if "opus" in m:
        return "opus", PRICING["opus"]
    if "sonnet" in m:
        return "sonnet", PRICING["sonnet"]
    if "haiku" in m:
        return "haiku", PRICING["haiku"]
    return "opus", PRICING["opus"]  # safe default: assume most expensive


def compute_cost(bucket, model):
    _, p = price_tier(model)
    parts = {
        "input":             bucket["input"]             * p["in"]       / 1_000_000,
        "output":            bucket["output"]            * p["out"]      / 1_000_000,
        "cache_read":        bucket["cache_read"]        * p["read"]     / 1_000_000,
        "cache_creation_5m": bucket["cache_creation_5m"] * p["cache_5m"] / 1_000_000,
        "cache_creation_1h": bucket["cache_creation_1h"] * p["cache_1h"] / 1_000_000,
    }
    parts["total"] = sum(parts.values())
    return parts


def new_bucket():
    return {
        "input": 0, "output": 0,
        "cache_read": 0, "cache_creation": 0,
        "cache_creation_5m": 0, "cache_creation_1h": 0,
    }


def tally(transcript_path):
    totals = new_bucket()
    totals["turns"] = 0
    last = new_bucket()
    peak_context = 0
    final_context = 0
    last_model = ""
    first_ts = None
    last_ts = None

    if not transcript_path or not os.path.isfile(transcript_path):
        return totals, peak_context, final_context, last_model, last, first_ts, last_ts

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

            cc_split = u.get("cache_creation") or {}
            cc_5m = int(cc_split.get("ephemeral_5m_input_tokens") or 0) if isinstance(cc_split, dict) else 0
            cc_1h = int(cc_split.get("ephemeral_1h_input_tokens") or 0) if isinstance(cc_split, dict) else 0
            # If no breakdown was reported but cc>0, attribute to 5m (the default tier).
            if cc and (cc_5m + cc_1h) == 0:
                cc_5m = cc

            totals["input"] += inp
            totals["output"] += outp
            totals["cache_read"] += cr
            totals["cache_creation"] += cc
            totals["cache_creation_5m"] += cc_5m
            totals["cache_creation_1h"] += cc_1h
            totals["turns"] += 1

            ctx = inp + cr + cc
            if ctx > peak_context:
                peak_context = ctx
            final_context = ctx

            last = {
                "input": inp, "output": outp,
                "cache_read": cr, "cache_creation": cc,
                "cache_creation_5m": cc_5m, "cache_creation_1h": cc_1h,
            }

            if msg.get("model"):
                last_model = msg["model"]

            ts = parse_iso(entry.get("timestamp"))
            if ts:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts

    return totals, peak_context, final_context, last_model, last, first_ts, last_ts


def cache_efficiency(bucket):
    denom = bucket["input"] + bucket["cache_read"] + bucket["cache_creation"]
    if denom == 0:
        return 0.0
    return 100.0 * bucket["cache_read"] / denom


def format_block(session_id, totals, peak, final, model, last, first_ts, last_ts):
    now = datetime.now()

    def n(v):
        return f"{v:,}"

    def money(v):
        return f"${v:,.4f}" if v < 10 else f"${v:,.2f}"

    started_local = first_ts.astimezone().strftime("%Y-%m-%d %H:%M:%S") if first_ts else "-"
    updated_local = now.strftime("%Y-%m-%d %H:%M:%S")
    if first_ts and last_ts:
        duration = fmt_duration((last_ts - first_ts).total_seconds())
    else:
        duration = "-"

    tier_name, _ = price_tier(model)
    cost_total = compute_cost(totals, model)
    cost_last = compute_cost(last, model)
    eff = cache_efficiency(totals)

    header = (
        f"{SEPARATOR}\n"
        f"Session: {session_id}\n"
        f"Started: {started_local}   Updated: {updated_local}\n"
        f"Duration: {duration}   Model: {model or '-'} ({tier_name} pricing)   Turns: {totals['turns']}\n"
        f"\n"
    )
    table = (
        f"                       input       output    cache_read   cache_creation\n"
        f"  Last turn       {n(last['input']):>10}  {n(last['output']):>11}  {n(last['cache_read']):>12}   {n(last['cache_creation']):>14}\n"
        f"  Session total   {n(totals['input']):>10}  {n(totals['output']):>11}  {n(totals['cache_read']):>12}   {n(totals['cache_creation']):>14}\n"
        f"\n"
    )
    metrics = (
        f"  Context window:      peak={n(peak)}   final={n(final)}\n"
        f"  Cache efficiency:    {eff:.1f}% of prompt served from cache\n"
        f"  API-equivalent cost: {money(cost_total['total'])} session   {money(cost_last['total'])} last turn\n"
        f"    breakdown: "
        f"input={money(cost_total['input'])}  "
        f"output={money(cost_total['output'])}  "
        f"cache_read={money(cost_total['cache_read'])}  "
        f"cache_creation={money(cost_total['cache_creation_5m'] + cost_total['cache_creation_1h'])}\n"
        f"    note: informational only - subscription users pay a flat monthly fee, not this\n"
        f"\n"
    )
    return header + table + metrics


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

    totals, peak, final, model, last, first_ts, last_ts = tally(transcript_path)
    block = format_block(session_id, totals, peak, final, model, last, first_ts, last_ts)

    out_path = os.path.join(cwd, OUT_NAME)
    try:
        upsert(out_path, session_id, block)
    except OSError as e:
        sys.stderr.write(f"token-usage tracker: {e}\n")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
