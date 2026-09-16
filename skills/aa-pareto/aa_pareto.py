#!/usr/bin/env python3
"""Pareto search over Artificial Analysis model benchmarks, restricted to Copilot CLI models.

Prefers the generated Copilot model × reasoning-effort report, with the Artificial Analysis API
as a fallback, and reports the quality × speed × cost Pareto frontier plus role recommendations.

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
    python aa_pareto.py --models "gpt-6-astra,gpt-5.6-sol,gpt-5.6-luna"  # custom id set
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
DEFAULT_TRI_REVIEW_BUDGET_SECONDS = 300.0
TRI_REVIEW_FAMILIES = (
    ("Claude / Anthropic", "claude"),
    ("GPT / OpenAI", "gpt"),
    ("Gemini / Google", "gemini"),
    ("Grok / xAI", "grok"),
)

QUALITY_METRICS = {
    "coding": ("coding", "coding index"),
    "intelligence": ("intelligence", "intelligence index"),
    "briefcase": ("briefcase", "AA-Briefcase Elo"),
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
    "task-time": ("task_time", False, "AA task decode time"),
    "task-elapsed": ("task_elapsed", False, "AA task elapsed proxy"),
    "briefcase-turns": ("briefcase_turns", False, "AA-Briefcase turns per task"),
    "gdpval-turns": ("gdpval_turns", False, "GDPval-AA turns per task"),
}

COST_METRICS = {
    "token-price": ("token_price", "AA blended token price"),
    "ai-credits": (
        "copilot_ai_credits",
        "Copilot blended AI credits per 1M tokens",
    ),
    "task-cost": ("task_cost", "AA cost per task"),
    "task-ai-credits": (
        "copilot_task_ai_credits",
        "Estimated Copilot AI credits per AA task",
    ),
    "briefcase-cost": ("briefcase_cost", "AA-Briefcase total run cost"),
    "briefcase-ai-credits": (
        "copilot_briefcase_ai_credits",
        "Estimated Copilot AI credits per AA-Briefcase run",
    ),
}

COST_FALLBACKS = {
    "ai-credits": "token-price",
    "task-ai-credits": "task-cost",
    "briefcase-ai-credits": "briefcase-cost",
}

DEFAULT_SPEED_WEIGHT = 2.0
DEFAULT_COST_WEIGHT = 1.0

# Maintained recommendation policy based on AA benchmark definitions. Artificial
# Analysis supplies the measurements but does not prescribe these application mappings.
TASK_PROFILES = {
    "coding": ("coding", "throughput", "ai-credits", 0.70),
    "general-reasoning": ("intelligence", "task-time", "task-ai-credits", 0.70),
    "terminal-agent": ("terminal", "throughput", "ai-credits", 0.65),
    "knowledge-work": (
        "briefcase",
        "briefcase-turns",
        "briefcase-ai-credits",
        0.80,
    ),
    "professional-output": (
        "knowledge-work",
        "gdpval-turns",
        "ai-credits",
        0.80,
    ),
    "instruction-following": (
        "ifbench",
        "throughput",
        "ai-credits",
        0.85,
    ),
    "agentic-tools": ("agentic", "throughput", "ai-credits", 0.65),
    "office-automation": (
        "enterprise-ops",
        "throughput",
        "ai-credits",
        0.65,
    ),
    "factual-research": (
        "factuality",
        "throughput",
        "ai-credits",
        0.70,
    ),
    "multimodal": ("multimodal", "throughput", "ai-credits", 0.70),
}

QUALITY_COMPATIBILITY = {
    "coding": (
        {"throughput", "ttft", "task-elapsed"},
        {"token-price", "ai-credits"},
    ),
    "intelligence": ({"task-time"}, {"task-cost", "task-ai-credits"}),
    "briefcase": (
        {"briefcase-turns"},
        {"briefcase-cost", "briefcase-ai-credits"},
    ),
    "briefcase-analysis": (
        {"briefcase-turns"},
        {"briefcase-cost", "briefcase-ai-credits"},
    ),
    "briefcase-presentation": (
        {"briefcase-turns"},
        {"briefcase-cost", "briefcase-ai-credits"},
    ),
    "ifbench": ({"throughput", "ttft"}, {"token-price", "ai-credits"}),
    "agentic": (
        {"throughput", "ttft", "task-elapsed"},
        {"token-price", "ai-credits"},
    ),
    "terminal": (
        {"throughput", "ttft", "task-elapsed"},
        {"token-price", "ai-credits"},
    ),
    "knowledge-work": (
        {"gdpval-turns"},
        {"token-price", "ai-credits"},
    ),
    "factuality": ({"throughput", "ttft"}, {"token-price", "ai-credits"}),
    "multimodal": (
        {"throughput", "ttft", "task-elapsed"},
        {"token-price", "ai-credits"},
    ),
    "enterprise-ops": (
        {"throughput", "ttft"},
        {"token-price", "ai-credits"},
    ),
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
    "gpt-5.6-sol-fast": ["gpt-5.6 sol"],
    "gpt-5.6-terra": ["gpt-5.6 terra"],
    "gpt-5.6-luna": ["gpt-5.6 luna"],
    "gpt-6-astra": ["gpt-6 astra"],
    "gpt-5.5": ["gpt-5.5"],
    "gpt-5.4": ["gpt-5.4 (", "gpt-5.4 x", "gpt-5.4 h", "gpt-5.4 m"],
    "gpt-5.4-mini": ["gpt-5.4 mini"],
    "gpt-5.3-codex": ["gpt-5.3", "5.3-codex", "gpt-5.3 codex"],
    "gpt-5-mini": ["gpt-5 mini", "gpt-5-mini"],
    "gemini-3.8-flash": ["gemini 3.8 flash"],
    "gemini-3.7-flash": ["gemini 3.7 flash"],
    "gemini-3.6-flash": ["gemini 3.6 flash"],
    "gemini-3.5-flash": ["gemini 3.5 flash"],
    "grok-4.6": ["grok 4.6"],
    "grok-4.5": ["grok 4.5"],
    "mai-code-1.1-flash": ["mai-code-1.1-flash", "mai code 1.1 flash"],
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
            "copilot_ai_credits": (
                metrics.get("price.copilot_ai_credits_blended_3_to_1") or 0.0
            ),
            "task_time": metrics.get("task.decode_time_seconds") or 0.0,
            "task_elapsed": (
                metrics.get("task.elapsed_proxy_seconds")
                or (
                    (metrics.get("task.decode_time_seconds") or 0.0)
                    + (report_row.get("ttft") or 0.0)
                )
            ),
            "task_cost": metrics.get("task.cost_total") or 0.0,
            "copilot_task_ai_credits": (
                metrics.get("copilot.ai_credits_per_task") or 0.0
            ),
            "briefcase_turns": metrics.get("briefcase.turns_per_task") or 0.0,
            "briefcase_cost": metrics.get("briefcase.cost_total") or 0.0,
            "copilot_briefcase_ai_credits": (
                metrics.get("copilot.briefcase_ai_credits_total") or 0.0
            ),
            "briefcase": metrics.get("briefcase.elo") or 0.0,
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


def pareto_front(
    rows: list[dict],
    metric: str,
    speed_key: str,
    higher_is_faster: bool,
    cost_key: str,
) -> list[dict]:
    """Return rows not dominated on quality, speed, and cost."""
    def at_least_as_fast(a: dict, b: dict) -> bool:
        return a[speed_key] >= b[speed_key] if higher_is_faster else a[speed_key] <= b[speed_key]

    def strictly_faster(a: dict, b: dict) -> bool:
        return a[speed_key] > b[speed_key] if higher_is_faster else a[speed_key] < b[speed_key]

    candidates = [
        r
        for r in rows
        if (
            (r.get(metric) or 0) > 0
            and (r.get(speed_key) or 0) > 0
            and (r.get(cost_key) or 0) > 0
        )
    ]
    front = []
    for a in candidates:
        dominated = any(
            b is not a
            and b[metric] >= a[metric]
            and at_least_as_fast(b, a)
            and b[cost_key] <= a[cost_key]
            and (
                b[metric] > a[metric]
                or strictly_faster(b, a)
                or b[cost_key] < a[cost_key]
            )
            for b in candidates
        )
        if not dominated:
            front.append(a)
    return sorted(front, key=lambda r: -r[metric])


def strictly_dominates(
    candidate: dict,
    baseline: dict,
    metric: str,
    speed_key: str,
    higher_is_faster: bool,
    cost_key: str,
) -> bool:
    """Return whether candidate is strictly better on all three axes."""
    faster = (
        candidate[speed_key] > baseline[speed_key]
        if higher_is_faster
        else candidate[speed_key] < baseline[speed_key]
    )
    return (
        candidate[metric] > baseline[metric]
        and faster
        and candidate[cost_key] < baseline[cost_key]
    )


def parse_model_effort(value: str) -> tuple[str, str | None]:
    model, separator, effort = value.partition("@")
    return model.strip(), effort.strip() if separator and effort.strip() else None


def resolve_baseline(rows: list[dict], value: str) -> dict:
    model, effort = parse_model_effort(value)
    matches = [
        row
        for row in rows
        if row.get("copilot_id") == model
        and (effort is None or row.get("effort") == effort)
    ]
    if not matches:
        raise ValueError(f"baseline {value!r} was not found in the measured rows")
    if len(matches) > 1:
        efforts = ", ".join(str(row.get("effort")) for row in matches)
        raise ValueError(
            f"baseline {model!r} has multiple measured efforts ({efforts}); "
            "specify MODEL@EFFORT"
        )
    return matches[0]


def label(r: dict) -> str:
    model = r.get("copilot_id") or r["name"]
    effort = r.get("effort")
    return f"{model} ({effort})" if effort else model


def tri_review_elapsed(row: dict) -> float:
    """Return the AA elapsed-time proxy used for parallel review calibration."""
    ttft = row.get("ttft") or 0.0
    decode_time = row.get("task_time") or 0.0
    return ttft + decode_time if ttft > 0 and decode_time > 0 else 0.0


def tri_review_rows(
    rows: list[dict],
    budget_seconds: float,
) -> list[tuple[str, dict, dict, dict]]:
    """Select normal, same-family alternate, and maximum-depth reviewers per family.

    Normal review maximizes coding quality within a wall-clock budget because three reviewers run
    in parallel and the slowest reviewer determines completion time. The alternate prefers a
    different model ID within the same budget; when none exists, it uses another effort of the
    normal model. Maximum depth remains the family's maximum coding score.
    """
    out = []
    for fam_label, key in TRI_REVIEW_FAMILIES:
        members = [
            r
            for r in rows
            if key in (r.get("copilot_id") or "").lower()
            and (r.get("coding") or 0) > 0
            and tri_review_elapsed(r) > 0
        ]
        if not members:
            continue
        maximum = max(
            members,
            key=lambda r: (
                r["coding"],
                r["intelligence"],
                -tri_review_elapsed(r),
            ),
        )
        within_budget = [
            r for r in members if tri_review_elapsed(r) <= budget_seconds
        ]
        normal_pool = within_budget or members
        normal = max(
            normal_pool,
            key=lambda r: (
                r["coding"],
                r["intelligence"],
                -tri_review_elapsed(r),
            ),
        )
        distinct_model = [
            r
            for r in within_budget
            if r.get("copilot_id") != normal.get("copilot_id")
        ]
        alternate_pool = distinct_model or [
            r for r in within_budget if r is not normal
        ] or [r for r in members if r is not normal] or [normal]
        alternate = max(
            alternate_pool,
            key=lambda r: (
                r["coding"],
                r["intelligence"],
                -tri_review_elapsed(r),
            ),
        )
        out.append((fam_label, normal, alternate, maximum))
    return out


def picks(
    rows: list[dict],
    front: list[dict],
    metric: str,
    min_quality: float,
    speed_key: str,
    higher_is_faster: bool,
    cost_key: str,
    speed_weight: float = DEFAULT_SPEED_WEIGHT,
    cost_weight: float = DEFAULT_COST_WEIGHT,
) -> dict:
    if not rows:
        return {}
    candidates = [
        r
        for r in rows
        if (
            (r.get(metric) or 0) > 0
            and (r.get(speed_key) or 0) > 0
            and (r.get(cost_key) or 0) > 0
        )
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
    cmin = min(r[cost_key] for r in candidates)

    def cost_score(r: dict) -> float:
        return cmin / r[cost_key]

    knee = max(
        eligible_front or eligible,
        key=lambda r: (
            (r[metric] / qmax)
            * speed_score(r) ** speed_weight
            * cost_score(r) ** cost_weight
        ),
    )
    heavy = max(
        candidates,
        key=lambda r: (
            r[metric],
            speed_score(r),
            -r[cost_key],
        ),
    )
    fast = (
        max(eligible, key=lambda r: r[speed_key])
        if higher_is_faster
        else min(eligible, key=lambda r: r[speed_key])
    )
    economical = min(eligible, key=lambda r: (r[cost_key], -speed_score(r)))
    return {
        "heavy_reasoner": heavy,
        "quality_at_efficiency": knee,
        "fast_light": fast,
        "cost_saver": economical,
    }


def fmt(
    r: dict,
    metric: str,
    quality_label: str,
    speed_key: str,
    speed_label: str,
    cost_key: str,
    cost_label: str,
) -> str:
    price = ""
    if (r.get("copilot_task_ai_credits") or 0) > 0:
        price = f"  {r['copilot_task_ai_credits']:.2f} AI credits/AA task"
    elif (r.get("task_cost") or 0) > 0:
        price = f"  ${r['task_cost']:.2f}/AA task"
    elif (r.get("briefcase_cost") or 0) > 0:
        price = f"  ${r['briefcase_cost']:.2f}/Briefcase run"
    elif r["in_price"] is not None:
        price = f"  ${r['in_price']}/{r['out_price']}"
    quality = r.get(metric) or 0.0
    speed = r.get(speed_key) or 0.0
    cost = r.get(cost_key) or 0.0
    return (
        f"{label(r):<32}{quality:8.2f} {quality_label:<30}"
        f"{speed:9.2f} {speed_label:<28}"
        f"{cost:9.2f} {cost_label:<35}{price}   [{r['name']}]"
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
        "--cost-metric",
        choices=COST_METRICS,
        help="advanced override for the task profile's cost metric",
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
    ap.add_argument(
        "--speed-weight",
        type=float,
        default=DEFAULT_SPEED_WEIGHT,
        help=f"normalized speed exponent for the efficiency knee (default: {DEFAULT_SPEED_WEIGHT:g})",
    )
    ap.add_argument(
        "--cost-weight",
        type=float,
        default=DEFAULT_COST_WEIGHT,
        help=f"normalized cost exponent for the efficiency knee (default: {DEFAULT_COST_WEIGHT:g})",
    )
    ap.add_argument(
        "--strictly-better-than",
        metavar="MODEL@EFFORT",
        help=(
            "keep only candidates with higher quality, better speed, and lower cost "
            "than the specified baseline"
        ),
    )
    ap.add_argument("--all", action="store_true", help="do not restrict to Copilot CLI ids")
    ap.add_argument("--models", help="comma-separated Copilot ids to restrict to (subset of the map)")
    ap.add_argument(
        "--tri-review",
        action="store_true",
        help="emit latency-budgeted per-family tri-review candidates",
    )
    ap.add_argument(
        "--tri-review-budget",
        type=float,
        default=DEFAULT_TRI_REVIEW_BUDGET_SECONDS,
        help=(
            "AA elapsed-time budget in seconds for normal parallel reviewers "
            f"(default: {DEFAULT_TRI_REVIEW_BUDGET_SECONDS:g})"
        ),
    )
    ap.add_argument("--refresh", action="store_true", help="bypass the 24h cache and re-query the API")
    ap.add_argument(
        "--report-data",
        type=Path,
        help=f"generated model_data.json (default when present: {DEFAULT_REPORT_DATA})",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.speed_weight < 0:
        ap.error("--speed-weight must be nonnegative")
    if args.cost_weight < 0:
        ap.error("--cost-weight must be nonnegative")

    if args.list_tasks:
        print(
            "Task profiles are this skill's recommendation policy; "
            "Artificial Analysis supplies benchmark definitions and measurements.\n"
        )
        for task, (quality, speed, cost, ratio) in TASK_PROFILES.items():
            print(
                f"{task:<22} quality={QUALITY_METRICS[quality][1]:<40} "
                f"speed={SPEED_METRICS[speed][2]:<35} "
                f"cost={COST_METRICS[cost][1]:<45} floor={ratio:.0%}"
            )
        return

    profile_metric, profile_speed, profile_cost, quality_floor_ratio = TASK_PROFILES[
        args.task
    ]
    metric_name = args.metric or profile_metric
    speed_name = args.speed_metric or profile_speed
    cost_name = args.cost_metric or profile_cost
    allowed_speed, allowed_cost = QUALITY_COMPATIBILITY[metric_name]
    if speed_name not in allowed_speed:
        ap.error(
            f"{speed_name} is not relevant to {metric_name}; "
            f"choose one of: {', '.join(sorted(allowed_speed))}"
        )
    if cost_name not in allowed_cost:
        ap.error(
            f"{cost_name} is not relevant to {metric_name}; "
            f"choose one of: {', '.join(sorted(allowed_cost))}"
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

    requested_cost_name = cost_name
    cost_key, cost_label = COST_METRICS[cost_name]
    cost_fallback_reason = None
    quality_speed_rows = [
        r
        for r in rows
        if (r.get(metric) or 0) > 0 and (r.get(speed_key) or 0) > 0
    ]
    if quality_speed_rows and not all(
        (r.get(cost_key) or 0) > 0 for r in quality_speed_rows
    ):
        fallback_name = COST_FALLBACKS.get(cost_name)
        if fallback_name:
            fallback_key, fallback_label = COST_METRICS[fallback_name]
            if all((r.get(fallback_key) or 0) > 0 for r in quality_speed_rows):
                cost_fallback_reason = (
                    f"{cost_label} is unavailable for one or more candidates; "
                    f"using {fallback_label} for a comparable frontier"
                )
                cost_name = fallback_name
                cost_key = fallback_key
                cost_label = fallback_label

    if args.tri_review:
        if args.tri_review_budget <= 0:
            ap.error("--tri-review-budget must be greater than zero")
        tr = tri_review_rows(
            [r for r in rows if (r.get("coding") or 0) > 0],
            args.tri_review_budget,
        )
        if not tr:
            ap.error(
                "--tri-review requires generated report data with TTFT and AA task decode time"
            )
        if args.json:
            print(json.dumps([
                {
                    "family": family,
                    "normal": label(normal),
                    "normal_coding": normal["coding"],
                    "normal_elapsed_seconds": tri_review_elapsed(normal),
                    "alternate": label(alternate),
                    "alternate_coding": alternate["coding"],
                    "alternate_elapsed_seconds": tri_review_elapsed(alternate),
                    "maximum": label(maximum),
                    "maximum_coding": maximum["coding"],
                    "maximum_elapsed_seconds": tri_review_elapsed(maximum),
                }
                for family, normal, alternate, maximum in tr
            ], indent=2))
            return
        print(
            "\n=== tri-review refresh candidates "
            f"(normal elapsed budget: {args.tri_review_budget:g}s) ==="
        )
        for family, normal, alternate, maximum in tr:
            print(f"  {family}")
            print(
                f"     normal:    {label(normal):<26} "
                f"coding {normal['coding']:.1f}  intel {normal['intelligence']:.1f}  "
                f"~{tri_review_elapsed(normal):.0f}s"
            )
            print(
                f"     alternate: {label(alternate):<26} "
                f"coding {alternate['coding']:.1f}  intel {alternate['intelligence']:.1f}  "
                f"~{tri_review_elapsed(alternate):.0f}s"
            )
            print(
                f"     maximum:   {label(maximum):<26} "
                f"coding {maximum['coding']:.1f}  intel {maximum['intelligence']:.1f}  "
                f"~{tri_review_elapsed(maximum):.0f}s"
            )
        print(
            "\nNormal picks maximize family coding quality within the parallel-review budget. "
            "With four usable families, omit the active family and use the other three. "
            "The alternate is only for degraded three-family operation; maximum is reserved "
            "for an explicitly requested maximum-depth review."
        )
        return

    rows = [
        r
        for r in rows
        if (
            (r.get(metric) or 0) > 0
            and (r.get(speed_key) or 0) > 0
            and (r.get(cost_key) or 0) > 0
        )
    ]
    if not rows:
        ap.error(
            f"no rows contain {quality_label}, {speed_label}, and {cost_label}; "
            "refresh model_data.json or choose another task/metric"
        )
    baseline = None
    if args.strictly_better_than:
        try:
            baseline = resolve_baseline(rows, args.strictly_better_than)
        except ValueError as error:
            ap.error(str(error))
        rows = [
            row
            for row in rows
            if row is not baseline
            and strictly_dominates(
                row,
                baseline,
                metric,
                speed_key,
                higher_is_faster,
                cost_key,
            )
        ]
        if not rows:
            ap.error(
                f"no candidate is strictly better than {label(baseline)} on "
                f"{quality_label}, {speed_label}, and {cost_label}"
            )
    rows.sort(key=lambda r: -r[metric])
    min_quality = (
        args.min_quality
        if args.min_quality is not None
        else max(r[metric] for r in rows) * quality_floor_ratio
    )
    front = pareto_front(rows, metric, speed_key, higher_is_faster, cost_key)
    pk = picks(
        rows,
        front,
        metric,
        min_quality,
        speed_key,
        higher_is_faster,
        cost_key,
        args.speed_weight,
        args.cost_weight,
    )

    if args.json:
        print(json.dumps({
            "task": args.task,
            "task_policy_source": "aa-pareto maintained engineering policy",
            "metric": metric_name,
            "speed_metric": speed_name,
            "cost_metric_requested": requested_cost_name,
            "cost_metric": cost_name,
            "quality_label": quality_label,
            "speed_label": speed_label,
            "cost_label": cost_label,
            "speed_weight": args.speed_weight,
            "cost_weight": args.cost_weight,
            "cost_fallback_reason": cost_fallback_reason,
            "strictly_better_than": label(baseline) if baseline else None,
            "min_quality": min_quality,
            "generated_at": generated_at,
            "rows": rows,
            "pareto_front": [label(r) for r in front],
            "tradeoff_required": len(front) > 1,
            "picks": {k: label(v) for k, v in pk.items()},
            "attribution": ATTRIBUTION,
        }, indent=2))
        return

    print(f"\n=== Task profile: {args.task} ===")
    print(f"Quality: {quality_label}; speed: {speed_label}; cost: {cost_label}")
    if baseline:
        print(f"Strict-dominance baseline: {label(baseline)}")
    if cost_fallback_reason:
        print(f"Cost basis fallback: {cost_fallback_reason}")
    print(f"\n=== All candidates (sorted by {quality_label}) ===")
    for r in rows:
        print(
            "  "
            + fmt(
                r,
                metric,
                quality_label,
                speed_key,
                speed_label,
                cost_key,
                cost_label,
            )
        )
    direction = "maximize" if higher_is_faster else "minimize"
    print(
        f"\n=== Pareto frontier (maximize {quality_label}; "
        f"{direction} {speed_label}; minimize {cost_label}) ==="
    )
    for r in front:
        print(
            "  "
            + fmt(
                r,
                metric,
                quality_label,
                speed_key,
                speed_label,
                cost_key,
                cost_label,
            )
        )
    print("\n=== Recommended picks ===")
    print(f"  heavy reasoner   (max quality)          : {label(pk['heavy_reasoner'])}")
    print(
        "  quality-at-efficiency (speed-priority knee): "
        f"{label(pk['quality_at_efficiency'])}"
    )
    print(f"  fast / light     (best {speed_label} >= {min_quality:g} {quality_label}): {label(pk['fast_light'])}")
    print(
        f"  cost saver       (lowest {cost_label} >= {min_quality:g} "
        f"{quality_label}): {label(pk['cost_saver'])}"
    )
    if len(front) > 1:
        print(
            "\nTrade-off required: multiple candidates are Pareto-efficient. "
            "For consequential selections, ask whether to prioritize quality, speed, or cost. "
            f"The knee above weights speed {args.speed_weight:g}x and "
            f"cost {args.cost_weight:g}x."
        )
    else:
        print("\nOne candidate dominates the measured quality, speed, and cost axes.")
    print("\nNote: AA scores are measured at a specific reasoning effort (see the effort in [AA name]).")
    print("To realize a headline score, set the matching reasoning effort. Speed drops as effort rises.")
    print("\n" + ATTRIBUTION)


if __name__ == "__main__":
    main()
