#!/usr/bin/env python3
"""Pareto search over Artificial Analysis model benchmarks, restricted to Copilot CLI models.

Prefers the generated Copilot model × reasoning-effort report, with the Artificial Analysis API
as a fallback, and reports the Pareto-optimal frontier plus role-based recommendations.

Auth: set env AA_API_KEY (or ARTIFICIAL_ANALYSIS_API_KEY). Sent as the `x-api-key` header.
Endpoint: https://artificialanalysis.ai/api/v2/data/llms/models

Usage:
    python aa_pareto.py                          # coding task: table + Pareto set + picks
    python aa_pareto.py --list-tasks             # show task-oriented benchmark profiles
    python aa_pareto.py --task knowledge-work    # AA-Briefcase quality and native task time
    python aa_pareto.py --task instruction-following
    python aa_pareto.py --metric intelligence --speed-metric task-cost
    python aa_pareto.py --min-quality 55         # absolute floor for the "fast/light" pick
    python aa_pareto.py --all                    # do not restrict to Copilot CLI ids
    python aa_pareto.py --json                    # machine-readable output
    python aa_pareto.py --models "gpt-5.6-sol,gpt-5.6-terra,gpt-5.6-luna"  # custom id set
    python aa_pareto.py --refresh                 # bypass the 24h cache and re-query the API

Results are cached for 24h (the free tier allows only 100 requests/day). All data is provided by
Artificial Analysis; attribution is required per their API terms.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

AA_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"
CACHE_TTL_SECONDS = 24 * 60 * 60  # AA data refreshes ~daily and the free tier is 100 req/day.
ATTRIBUTION = ("Data by Artificial Analysis (https://artificialanalysis.ai) — "
               "attribution required per their API terms.")
DEFAULT_REPORT_DATA = Path(__file__).with_name("model_data.json")

QUALITY_METRICS = {
    "coding": ("coding", "coding index"),
    "intelligence": ("intelligence", "intelligence index"),
    "briefcase": ("briefcase", "AA-Briefcase Elo"),
    "briefcase-rubric": ("briefcase_rubric", "AA-Briefcase rubric Elo"),
    "briefcase-analysis": ("briefcase_analysis", "AA-Briefcase analytical quality Elo"),
    "briefcase-presentation": (
        "briefcase_presentation",
        "AA-Briefcase presentation Elo",
    ),
    "ifbench": ("ifbench", "IFBench"),
    "agentic": ("agentic", "AA Agentic Index"),
    "terminal": ("terminal", "Terminal-Bench v2.1"),
    "knowledge-work": ("gdpval", "GDPval-AA v2"),
    "factuality": ("omniscience", "AA-Omniscience"),
    "multimodal": ("mmmu", "MMMU Pro"),
    "enterprise-ops": ("enterprise_ops", "AA Enterprise Ops Gym success rate"),
}

SPEED_METRICS = {
    "throughput": ("tok_s", True, "output tok/s"),
    "ttft": ("ttft", False, "TTFT"),
    "token-price": ("token_price", False, "blended token price"),
    "task-time": ("task_time", False, "AA task decode time"),
    "task-cost": ("task_cost", False, "AA cost per task"),
    "briefcase-time": ("briefcase_time", False, "AA-Briefcase median task time"),
    "briefcase-cost": ("briefcase_cost", False, "AA-Briefcase cost per task"),
    "gdpval-turns": ("gdpval_turns", False, "GDPval-AA turns per task"),
    "enterprise-ops-time": (
        "enterprise_ops_time",
        False,
        "Enterprise Ops median active task time",
    ),
}

# Maintained recommendation policy based on AA benchmark definitions. Artificial
# Analysis supplies the measurements but does not prescribe these application mappings.
TASK_PROFILES = {
    "coding": ("coding", "throughput", 0.70),
    "general-reasoning": ("intelligence", "task-time", 0.70),
    "terminal-agent": ("terminal", "throughput", 0.65),
    "knowledge-work": ("briefcase", "briefcase-time", 0.80),
    "professional-output": ("knowledge-work", "gdpval-turns", 0.80),
    "instruction-following": ("ifbench", "throughput", 0.85),
    "agentic-tools": ("agentic", "throughput", 0.65),
    "office-automation": ("enterprise-ops", "enterprise-ops-time", 0.65),
    "factual-research": ("factuality", "throughput", 0.70),
    "multimodal": ("multimodal", "throughput", 0.70),
}

QUALITY_SPEED_COMPATIBILITY = {
    "coding": {"throughput", "ttft", "token-price"},
    "intelligence": {"task-time", "task-cost"},
    "briefcase": {"briefcase-time", "briefcase-cost"},
    "briefcase-rubric": {"briefcase-time", "briefcase-cost"},
    "briefcase-analysis": {"briefcase-time", "briefcase-cost"},
    "briefcase-presentation": {"briefcase-time", "briefcase-cost"},
    "ifbench": {"throughput", "ttft", "token-price"},
    "agentic": {"throughput", "ttft", "token-price"},
    "terminal": {"throughput", "ttft", "token-price"},
    "knowledge-work": {"gdpval-turns"},
    "factuality": {"throughput", "ttft", "token-price"},
    "multimodal": {"throughput", "ttft", "token-price"},
    "enterprise-ops": {"enterprise-ops-time"},
}

# Copilot-CLI-available model ids → substrings that match their Artificial Analysis `name`.
# Refresh this map when Copilot's model list changes (see SKILL.md → "Refresh the Copilot set").
# For each id we keep the single best-scoring AA variant (usually the highest reasoning effort).
COPILOT_MODELS: dict[str, list[str]] = {
    "claude-opus-5": ["opus 5"],
    "claude-opus-4.8": ["opus 4.8"],
    "claude-opus-4.7": ["opus 4.7"],
    "claude-opus-4.6": ["opus 4.6"],
    "claude-sonnet-5": ["claude sonnet 5", "sonnet 5 ("],
    "claude-sonnet-4.6": ["sonnet 4.6"],
    "claude-haiku-4.5": ["4.5 haiku", "haiku 4.5"],
    "gpt-5.6-sol": ["gpt-5.6 sol"],
    "gpt-5.6-terra": ["gpt-5.6 terra"],
    "gpt-5.6-luna": ["gpt-5.6 luna"],
    "gpt-5.5": ["gpt-5.5"],
    "gpt-5.4": ["gpt-5.4 (", "gpt-5.4 x", "gpt-5.4 h", "gpt-5.4 m"],
    "gpt-5.4-mini": ["gpt-5.4 mini"],
    "gpt-5.3-codex": ["gpt-5.3", "5.3-codex", "gpt-5.3 codex"],
    "gpt-5-mini": ["gpt-5 mini", "gpt-5-mini"],
    "gemini-3.1-pro-preview": ["gemini 3.1 pro"],
    "gemini-3.6-flash": ["gemini 3.6 flash"],
    "gemini-3.5-flash": ["gemini 3.5 flash"],
    "mai-code-1-flash-picker": ["mai-code-1-flash", "mai code 1 flash"],
}


def cache_path() -> Path:
    """Per-user cache file for the LLM endpoint (LOCALAPPDATA on Windows, ~/.cache elsewhere)."""
    base = (os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
            or os.path.join(os.path.expanduser("~"), ".cache"))
    d = Path(base) / "aa-pareto"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        d = Path(os.path.expanduser("~"))
    return d / "llms.json"


def _load_cache(cp: Path) -> list[dict] | None:
    try:
        with cp.open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def fetch(refresh: bool = False) -> list[dict]:
    """Return the AA LLM rows, served from a 24h cache unless --refresh or the cache is stale.

    Handles auth (401/403) and rate-limit (429) errors with clear messages, warns when the daily
    quota is nearly exhausted, and falls back to a stale cache on transient network failures.
    """
    cp = cache_path()
    if not refresh and cp.exists() and (time.time() - cp.stat().st_mtime) < CACHE_TTL_SECONDS:
        cached = _load_cache(cp)
        if cached is not None:
            return cached

    key = os.environ.get("AA_API_KEY") or os.environ.get("ARTIFICIAL_ANALYSIS_API_KEY")
    if not key:
        sys.exit("ERROR: set AA_API_KEY (or ARTIFICIAL_ANALYSIS_API_KEY) in the environment.")
    req = urllib.request.Request(AA_URL, headers={"x-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.load(resp)
            remaining = resp.headers.get("X-RateLimit-Remaining")
            reset = resp.headers.get("X-RateLimit-Reset")
            if remaining is not None and remaining.isdigit() and int(remaining) <= 5:
                msg = f"WARNING: {remaining} Artificial Analysis API request(s) left today"
                if reset:
                    msg += f" (resets {reset})"
                print(msg + "; results are cached for 24h.", file=sys.stderr)
    except HTTPError as e:
        if e.code in (401, 403):
            sys.exit(f"ERROR: Artificial Analysis rejected the API key (HTTP {e.code}). "
                     "Check AA_API_KEY / ARTIFICIAL_ANALYSIS_API_KEY.")
        if e.code == 429:
            reset = e.headers.get("X-RateLimit-Reset") if e.headers else None
            hint = f", resets {reset}" if reset else ""
            sys.exit(f"ERROR: Artificial Analysis rate limit reached (HTTP 429{hint}). "
                     "Free tier is 100 req/day; re-run later or rely on the 24h cache.")
        sys.exit(f"ERROR: Artificial Analysis API returned HTTP {e.code}: {e.reason}")
    except URLError as e:
        stale = _load_cache(cp) if cp.exists() else None
        if stale is not None:
            print(f"WARNING: live fetch failed ({e.reason}); using stale cache at {cp}.",
                  file=sys.stderr)
            return stale
        sys.exit(f"ERROR: could not reach Artificial Analysis: {e.reason}")

    data = payload.get("data") or payload
    try:
        with cp.open("w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass  # caching is best-effort
    return data


def row(m: dict) -> dict:
    ev = m.get("evaluations") or {}
    pr = m.get("pricing") or {}
    return {
        "name": m.get("name") or "",
        "coding": ev.get("artificial_analysis_coding_index") or 0.0,
        "intelligence": ev.get("artificial_analysis_intelligence_index") or 0.0,
        "tok_s": m.get("median_output_tokens_per_second") or 0.0,
        "ttft": m.get("median_time_to_first_token_seconds") or 0.0,
        "token_price": (
            pr.get("price_1m_blended_3_to_1")
            or (
                (
                    3 * (pr.get("price_1m_input_tokens") or 0)
                    + (pr.get("price_1m_output_tokens") or 0)
                )
                / 4
            )
        ),
        "in_price": pr.get("price_1m_input_tokens"),
        "out_price": pr.get("price_1m_output_tokens"),
    }


def load_report_rows(path: Path) -> tuple[list[dict], str | None]:
    """Load exact Copilot model × reasoning-effort rows from the generated report data."""
    try:
        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, ValueError) as e:
        sys.exit(f"ERROR: could not read report data at {path}: {e}")

    rows = []
    for combo in payload.get("combos", []):
        report_row = combo.get("row")
        if not combo.get("tracked") or not report_row:
            continue
        metrics = report_row.get("metrics") or {}
        pricing = report_row.get("pricing") or {}
        effort = combo.get("reasoning")
        rows.append({
            "name": report_row.get("name") or "",
            "coding": report_row.get("coding") or 0.0,
            "intelligence": report_row.get("intelligence") or 0.0,
            "tok_s": report_row.get("tok_s") or 0.0,
            "ttft": report_row.get("ttft") or 0.0,
            "token_price": metrics.get("price.price_1m_blended_3_to_1") or 0.0,
            "task_time": metrics.get("task.decode_time_seconds") or 0.0,
            "task_cost": metrics.get("task.cost_total") or 0.0,
            "briefcase_time": metrics.get("briefcase.task_time_p50_seconds") or 0.0,
            "briefcase_cost": metrics.get("briefcase.cost_per_task_total") or 0.0,
            "enterprise_ops_time": (
                metrics.get("rich.enterprise_ops_task_time_p50_seconds") or 0.0
            ),
            "briefcase": metrics.get("briefcase.elo") or 0.0,
            "briefcase_rubric": metrics.get("briefcase.rubric_elo") or 0.0,
            "briefcase_analysis": (
                metrics.get("briefcase.analytical_quality_elo") or 0.0
            ),
            "briefcase_presentation": (
                metrics.get("briefcase.presentation_elo") or 0.0
            ),
            "ifbench": metrics.get("eval.ifbench") or 0.0,
            "agentic": metrics.get("rich.agentic_index") or 0.0,
            "terminal": (
                metrics.get("rich.terminalbench_v2_1")
                or metrics.get("eval.terminalbench_v2_1")
                or 0.0
            ),
            "gdpval": metrics.get("rich.gdpval_v2") or 0.0,
            "gdpval_turns": metrics.get("rich.gdpval_turns_per_task") or 0.0,
            "omniscience": metrics.get("rich.omniscience") or 0.0,
            "mmmu": (
                metrics.get("rich.mmmu_pro")
                or metrics.get("eval.mmmu_pro")
                or 0.0
            ),
            "enterprise_ops": metrics.get("rich.enterprise_ops_success_rate") or 0.0,
            "in_price": (
                pricing.get("price_1m_input_tokens")
                or metrics.get("price.price_1m_input_tokens")
            ),
            "out_price": (
                pricing.get("price_1m_output_tokens")
                or metrics.get("price.price_1m_output_tokens")
            ),
            "copilot_id": combo.get("copilot_id") or "",
            "effort": effort if effort != "not supported" else "non-reasoning",
            "metrics": metrics,
        })
    return rows, payload.get("generated_at")


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


def pareto_front(rows: list[dict], metric: str, speed_key: str, higher_is_faster: bool) -> list[dict]:
    """Maximize quality and performance, accounting for metrics where lower is faster."""
    def at_least_as_fast(a: dict, b: dict) -> bool:
        return a[speed_key] >= b[speed_key] if higher_is_faster else a[speed_key] <= b[speed_key]

    def strictly_faster(a: dict, b: dict) -> bool:
        return a[speed_key] > b[speed_key] if higher_is_faster else a[speed_key] < b[speed_key]

    candidates = [
        r
        for r in rows
        if (r.get(metric) or 0) > 0 and (r.get(speed_key) or 0) > 0
    ]
    front = []
    for a in candidates:
        dominated = any(
            b is not a and b[metric] >= a[metric] and at_least_as_fast(b, a)
            and (b[metric] > a[metric] or strictly_faster(b, a))
            for b in candidates
        )
        if not dominated:
            front.append(a)
    return sorted(front, key=lambda r: -r[metric])


def label(r: dict) -> str:
    model = r.get("copilot_id") or r["name"]
    effort = r.get("effort")
    return f"{model} ({effort})" if effort else model


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


def picks(
    rows: list[dict],
    front: list[dict],
    metric: str,
    min_quality: float,
    speed_key: str,
    higher_is_faster: bool,
) -> dict:
    if not rows:
        return {}
    candidates = [
        r
        for r in rows
        if (r.get(metric) or 0) > 0 and (r.get(speed_key) or 0) > 0
    ]
    if not candidates:
        return {}
    # Normalize for a quality × speed knee. For duration metrics, reciprocal
    # normalization makes lower values score higher without treating zero/missing as fast.
    qmax = max(r[metric] for r in candidates) or 1.0
    if higher_is_faster:
        smax = max(r[speed_key] for r in candidates) or 1.0

        def speed_score(r: dict) -> float:
            return r[speed_key] / smax
    else:
        smin = min(r[speed_key] for r in candidates)

        def speed_score(r: dict) -> float:
            return smin / r[speed_key]

    eligible = [r for r in candidates if r[metric] >= min_quality] or candidates
    eligible_front = [r for r in front if r in eligible]
    knee = max(eligible_front or eligible, key=lambda r: (r[metric] / qmax) * speed_score(r))
    heavy = max(candidates, key=lambda r: (r[metric], r.get("intelligence") or 0))
    fast = (
        max(eligible, key=lambda r: r[speed_key])
        if higher_is_faster
        else min(eligible, key=lambda r: r[speed_key])
    )
    return {"heavy_reasoner": heavy, "quality_at_speed": knee, "fast_light": fast}


def fmt(
    r: dict,
    metric: str,
    quality_label: str,
    speed_key: str,
    speed_label: str,
) -> str:
    price = ""
    if (r.get("briefcase_cost") or 0) > 0:
        price = f"  ${r['briefcase_cost']:.2f}/Briefcase task"
    elif (r.get("task_cost") or 0) > 0:
        price = f"  ${r['task_cost']:.2f}/AA task"
    elif r["in_price"] is not None:
        price = f"  ${r['in_price']}/{r['out_price']}"
    quality = r.get(metric) or 0.0
    speed = r.get(speed_key) or 0.0
    return (
        f"{label(r):<32}{quality:8.2f} {quality_label:<30}"
        f"{speed:9.2f} {speed_label:<28}{price}   [{r['name']}]"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--task",
        choices=TASK_PROFILES,
        default="coding",
        help="task profile that selects default quality and efficiency axes",
    )
    ap.add_argument(
        "--metric",
        choices=QUALITY_METRICS,
        help="advanced override for the task profile's quality metric",
    )
    ap.add_argument(
        "--speed-metric",
        choices=SPEED_METRICS,
        help="advanced override for the task profile's efficiency metric",
    )
    ap.add_argument(
        "--list-tasks",
        action="store_true",
        help="list task profiles and their metric axes",
    )
    ap.add_argument(
        "--min-quality",
        type=float,
        help="absolute quality floor for the fast/light pick (default: profile ratio of max)",
    )
    ap.add_argument("--all", action="store_true", help="do not restrict to Copilot CLI ids")
    ap.add_argument("--models", help="comma-separated Copilot ids to restrict to (subset of the map)")
    ap.add_argument("--tri-review", action="store_true", help="emit per-family heavy/light refresh candidates")
    ap.add_argument("--refresh", action="store_true", help="bypass the 24h cache and re-query the API")
    ap.add_argument(
        "--report-data",
        type=Path,
        help=f"generated model_data.json (default when present: {DEFAULT_REPORT_DATA})",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.list_tasks:
        print(
            "Task profiles are this skill's recommendation policy; "
            "Artificial Analysis supplies benchmark definitions and measurements.\n"
        )
        for task, (quality, speed, ratio) in TASK_PROFILES.items():
            print(
                f"{task:<22} quality={QUALITY_METRICS[quality][1]:<40} "
                f"efficiency={SPEED_METRICS[speed][2]:<40} floor={ratio:.0%}"
            )
        return

    profile_metric, profile_speed, quality_floor_ratio = TASK_PROFILES[args.task]
    metric_name = args.metric or profile_metric
    speed_name = args.speed_metric or profile_speed
    if speed_name not in QUALITY_SPEED_COMPATIBILITY[metric_name]:
        allowed = ", ".join(sorted(QUALITY_SPEED_COMPATIBILITY[metric_name]))
        ap.error(
            f"{speed_name} is not relevant to {metric_name}; "
            f"choose one of: {allowed}"
        )
    metric, quality_label = QUALITY_METRICS[metric_name]
    speed_key, higher_is_faster, speed_label = SPEED_METRICS[speed_name]

    report_path = args.report_data
    if report_path is None and not args.all and not args.refresh and DEFAULT_REPORT_DATA.exists():
        report_path = DEFAULT_REPORT_DATA

    generated_at = None
    if report_path:
        if args.all:
            ap.error("--all cannot be combined with --report-data")
        rows, generated_at = load_report_rows(report_path)
    else:
        if metric not in {"coding", "intelligence"}:
            ap.error(
                f"{quality_label} is sourced from generated RSC data; "
                "use model_data.json instead of --refresh/--all"
            )
        models = fetch(refresh=args.refresh)
        if args.all:
            rows = [row(m) for m in models]
        else:
            rows = restrict_to_copilot(models, COPILOT_MODELS, metric)

    if args.models:
        wanted = {m.strip() for m in args.models.split(",") if m.strip()}
        rows = [r for r in rows if r.get("copilot_id") in wanted]

    if args.tri_review:
        tr = tri_review_rows([r for r in rows if (r.get("coding") or 0) > 0])
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
        print("and its 'queried' date accordingly.")
        return

    rows = [
        r
        for r in rows
        if (r.get(metric) or 0) > 0 and (r.get(speed_key) or 0) > 0
    ]
    if not rows:
        ap.error(
            f"no rows contain both {quality_label} and {speed_label}; "
            "refresh model_data.json or choose another task/metric"
        )
    rows.sort(key=lambda r: -r[metric])
    min_quality = (
        args.min_quality
        if args.min_quality is not None
        else max(r[metric] for r in rows) * quality_floor_ratio
    )
    front = pareto_front(rows, metric, speed_key, higher_is_faster)
    pk = picks(rows, front, metric, min_quality, speed_key, higher_is_faster)

    if args.json:
        print(json.dumps({
            "task": args.task,
            "task_policy_source": "aa-pareto maintained engineering policy",
            "metric": metric_name,
            "speed_metric": speed_name,
            "quality_label": quality_label,
            "speed_label": speed_label,
            "min_quality": min_quality,
            "generated_at": generated_at,
            "rows": rows,
            "pareto_front": [label(r) for r in front],
            "picks": {k: label(v) for k, v in pk.items()},
            "attribution": ATTRIBUTION,
        }, indent=2))
        return

    print(f"\n=== Task profile: {args.task} ===")
    print(f"Quality: {quality_label}; efficiency: {speed_label}")
    print(f"\n=== All candidates (sorted by {quality_label}) ===")
    for r in rows:
        print("  " + fmt(r, metric, quality_label, speed_key, speed_label))
    direction = "maximize" if higher_is_faster else "minimize"
    print(f"\n=== Pareto frontier (maximize {quality_label}; {direction} {speed_label}) ===")
    for r in front:
        print("  " + fmt(r, metric, quality_label, speed_key, speed_label))
    print("\n=== Recommended picks ===")
    print(f"  heavy reasoner   (max quality)          : {label(pk['heavy_reasoner'])}")
    print(f"  quality-at-speed ({speed_label} knee)   : {label(pk['quality_at_speed'])}")
    print(f"  fast / light     (best {speed_label} >= {min_quality:g} {quality_label}): {label(pk['fast_light'])}")
    print("\nNote: AA scores are measured at a specific reasoning effort (see the effort in [AA name]).")
    print("To realize a headline score, set the matching reasoning effort. Speed drops as effort rises.")
    print("\n" + ATTRIBUTION)


if __name__ == "__main__":
    main()
