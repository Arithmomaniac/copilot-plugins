#!/usr/bin/env python3
"""Pareto search over Artificial Analysis model benchmarks, restricted to Copilot CLI models.

Queries the Artificial Analysis API (quality / speed / price) and reports the Pareto-optimal
frontier plus role-based recommendations (heavy reasoner, quality-at-speed, fast/light).

Auth: set env AA_API_KEY (or ARTIFICIAL_ANALYSIS_API_KEY). Sent as the `x-api-key` header.
Endpoint: https://artificialanalysis.ai/api/v2/data/llms/models

Usage:
    python aa_pareto.py                          # table + Pareto set + picks (coding metric)
    python aa_pareto.py --metric intelligence    # rank by intelligence index instead of coding
    python aa_pareto.py --min-quality 55         # floor for the "fast/light" pick
    python aa_pareto.py --all                    # do not restrict to Copilot CLI ids
    python aa_pareto.py --json                    # machine-readable output
    python aa_pareto.py --models "gpt-5.5,gemini-3.5-flash,claude-opus-4.8"  # custom id set
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

AA_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"

# Copilot-CLI-available model ids → substrings that match their Artificial Analysis `name`.
# Refresh this map when Copilot's model list changes (see SKILL.md → "Refresh the Copilot set").
# For each id we keep the single best-scoring AA variant (usually the highest reasoning effort).
COPILOT_MODELS: dict[str, list[str]] = {
    "claude-opus-4.8": ["opus 4.8"],
    "claude-opus-4.7": ["opus 4.7"],
    "claude-opus-4.6": ["opus 4.6"],
    "claude-sonnet-5": ["claude sonnet 5", "sonnet 5 ("],
    "claude-sonnet-4.6": ["sonnet 4.6"],
    "claude-sonnet-4.5": ["sonnet 4.5"],
    "claude-haiku-4.5": ["4.5 haiku", "haiku 4.5"],
    "gpt-5.5": ["gpt-5.5"],
    "gpt-5.4": ["gpt-5.4 (", "gpt-5.4 x", "gpt-5.4 h", "gpt-5.4 m"],
    "gpt-5.4-mini": ["gpt-5.4 mini"],
    "gpt-5.3-codex": ["gpt-5.3", "5.3-codex", "gpt-5.3 codex"],
    "gpt-5-mini": ["gpt-5 mini", "gpt-5-mini"],
    "gemini-3.1-pro-preview": ["gemini 3.1 pro"],
    "gemini-3.5-flash": ["gemini 3.5 flash"],
    "mai-code-1-flash-picker": ["mai-code-1-flash", "mai code 1 flash"],
}


def fetch() -> list[dict]:
    key = os.environ.get("AA_API_KEY") or os.environ.get("ARTIFICIAL_ANALYSIS_API_KEY")
    if not key:
        sys.exit("ERROR: set AA_API_KEY (or ARTIFICIAL_ANALYSIS_API_KEY) in the environment.")
    req = urllib.request.Request(AA_URL, headers={"x-api-key": key})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    return data.get("data") or data


def row(m: dict) -> dict:
    ev = m.get("evaluations") or {}
    pr = m.get("pricing") or {}
    return {
        "name": m.get("name") or "",
        "coding": ev.get("artificial_analysis_coding_index") or 0.0,
        "intelligence": ev.get("artificial_analysis_intelligence_index") or 0.0,
        "tok_s": m.get("median_output_tokens_per_second") or 0.0,
        "ttft": m.get("median_time_to_first_token_seconds") or 0.0,
        "in_price": pr.get("price_1m_input_tokens"),
        "out_price": pr.get("price_1m_output_tokens"),
    }


def restrict_to_copilot(models: list[dict], id_map: dict[str, list[str]], metric: str) -> list[dict]:
    """Return one row per Copilot id: the best-scoring (by metric) AA variant matching it."""
    out = []
    for cid, needles in id_map.items():
        best = None
        for m in models:
            nm = (m.get("name") or "").lower()
            if any(n in nm for n in needles):
                r = row(m)
                if best is None or r[metric] > best[metric]:
                    best = r
        if best:
            best = dict(best)
            best["copilot_id"] = cid
            out.append(best)
    return out


def pareto_front(rows: list[dict], metric: str) -> list[dict]:
    """Maximize (metric, tok_s). A row is dominated if another has >= both and > one."""
    front = []
    for a in rows:
        dominated = any(
            b is not a and b[metric] >= a[metric] and b["tok_s"] >= a["tok_s"]
            and (b[metric] > a[metric] or b["tok_s"] > a["tok_s"])
            for b in rows
        )
        if not dominated:
            front.append(a)
    return sorted(front, key=lambda r: -r[metric])


def label(r: dict) -> str:
    return r.get("copilot_id") or r["name"]


def tri_review_rows(rows: list[dict]) -> list[tuple]:
    """Per family (Claude/GPT/Gemini): heavy = max coding; light = fastest with a quality floor.
    Refresh material for the tri-review skill's hardcoded table (apply judgment for pro-vs-flash tiers)."""
    fams = [("Claude / Anthropic", "claude"), ("GPT / OpenAI", "gpt"), ("Gemini / Google", "gemini")]
    out = []
    for fam_label, key in fams:
        members = [r for r in rows if key in (r.get("copilot_id") or "").lower()]
        if not members:
            continue
        heavy = max(members, key=lambda r: (r["coding"], r["intelligence"]))
        pool = [r for r in members if r["coding"] >= 20.0 and r is not heavy] \
            or [r for r in members if r is not heavy] or members
        light = max(pool, key=lambda r: r["tok_s"])
        out.append((fam_label, heavy, light))
    return out


def picks(rows: list[dict], front: list[dict], metric: str, min_quality: float) -> dict:
    if not rows:
        return {}
    # normalize for a quality x speed knee
    qmax = max(r[metric] for r in rows) or 1.0
    smax = max(r["tok_s"] for r in rows) or 1.0
    knee = max(front or rows, key=lambda r: (r[metric] / qmax) * (r["tok_s"] / smax))
    heavy = max(rows, key=lambda r: (r[metric], r["intelligence"]))
    eligible = [r for r in rows if r[metric] >= min_quality] or rows
    fast = max(eligible, key=lambda r: r["tok_s"])
    return {"heavy_reasoner": heavy, "quality_at_speed": knee, "fast_light": fast}


def fmt(r: dict, metric: str) -> str:
    price = ""
    if r["in_price"] is not None:
        price = f"  ${r['in_price']}/{r['out_price']}"
    return (f"{label(r):<26}{r['coding']:6.1f} cod  {r['intelligence']:6.1f} int  "
            f"{r['tok_s']:6.0f} tok/s  {r['ttft']:5.1f}s ttft{price}   [{r['name']}]")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metric", choices=["coding", "intelligence"], default="coding")
    ap.add_argument("--min-quality", type=float, default=55.0, help="quality floor for the fast/light pick")
    ap.add_argument("--all", action="store_true", help="do not restrict to Copilot CLI ids")
    ap.add_argument("--models", help="comma-separated Copilot ids to restrict to (subset of the map)")
    ap.add_argument("--tri-review", action="store_true", help="emit per-family heavy/light refresh candidates")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    models = fetch()
    if args.all:
        rows = [row(m) for m in models]
    else:
        id_map = COPILOT_MODELS
        if args.models:
            wanted = {m.strip() for m in args.models.split(",") if m.strip()}
            id_map = {k: v for k, v in COPILOT_MODELS.items() if k in wanted}
        rows = restrict_to_copilot(models, id_map, args.metric)

    rows.sort(key=lambda r: -r[args.metric])
    front = pareto_front(rows, args.metric)
    pk = picks(rows, front, args.metric, args.min_quality)

    if args.tri_review:
        tr = tri_review_rows(rows)
        if args.json:
            print(json.dumps([
                {"family": f, "heavy": label(h), "heavy_coding": h["coding"], "heavy_tok_s": h["tok_s"],
                 "light": label(l), "light_coding": l["coding"], "light_tok_s": l["tok_s"]}
                for f, h, l in tr], indent=2))
            return
        print("\n=== tri-review refresh candidates (heavy = max coding; light = fastest w/ quality floor) ===")
        for f, h, l in tr:
            flag = "  ⚠ light==heavy (family has no distinct fast tier)" if label(l) == label(h) else ""
            print(f"  {f}")
            print(f"     heavy: {label(h):<26} coding {h['coding']:.1f}  intel {h['intelligence']:.1f}  {h['tok_s']:.0f} tok/s")
            print(f"     light: {label(l):<26} coding {l['coding']:.1f}  intel {l['intelligence']:.1f}  {l['tok_s']:.0f} tok/s{flag}")
        print("\nApply judgment for 'pro vs flash' heavy tiers: a fast model can out-score the pro model on")
        print("coding yet you may still want the pro tier as the heavy reviewer. Update the tri-review table")
        print(f"and its 'queried' date accordingly.")
        return

    if args.json:
        print(json.dumps({
            "metric": args.metric,
            "rows": rows,
            "pareto_front": [label(r) for r in front],
            "picks": {k: label(v) for k, v in pk.items()},
        }, indent=2))
        return

    print(f"\n=== All candidates (sorted by {args.metric}) ===")
    for r in rows:
        print("  " + fmt(r, args.metric))
    print(f"\n=== Pareto frontier (maximize {args.metric} & tok/s) ===")
    for r in front:
        print("  " + fmt(r, args.metric))
    print("\n=== Recommended picks ===")
    print(f"  heavy reasoner   (max quality)          : {label(pk['heavy_reasoner'])}")
    print(f"  quality-at-speed (Pareto knee)          : {label(pk['quality_at_speed'])}")
    print(f"  fast / light     (fastest >= {args.min_quality:g} {args.metric}): {label(pk['fast_light'])}")
    print("\nNote: AA scores are measured at a specific reasoning effort (see the effort in [AA name]).")
    print("To realize a headline score, set the matching reasoning effort. Speed drops as effort rises.")


if __name__ == "__main__":
    main()
