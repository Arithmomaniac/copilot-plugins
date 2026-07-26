#!/usr/bin/env python3
"""Fetch Artificial Analysis data and build a standalone Copilot model report.

The default command refreshes ``model_data.json`` and renders
``model_report.html``. The script intentionally uses only the Python standard
library.

Examples:
    python build_report.py
    python build_report.py --fetch-only
    python build_report.py --render-only
    python build_report.py --discover-models
    python build_report.py --no-rsc
"""

from __future__ import annotations

import argparse
import json
import math
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AA_MODELS_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"
AA_RSC_URL = (
    "https://artificialanalysis.ai/evaluations/"
    "artificial-analysis-intelligence-index"
)
AA_BRIEFCASE_URL = "https://artificialanalysis.ai/evaluations/aa-briefcase"
ATTRIBUTION = "Data by Artificial Analysis (https://artificialanalysis.ai)."
SCHEMA_VERSION = 2
EFFORT_ORDER = ("minimal", "low", "medium", "high", "xhigh", "max")


@dataclass(frozen=True)
class ModelSpec:
    copilot_id: str
    efforts: tuple[str, ...]
    aa_pattern: str
    mode: str


MODEL_SPECS = (
    ModelSpec("claude-sonnet-5", ("low", "medium", "high", "xhigh", "max"), r"^Claude Sonnet 5\b", "adaptive"),
    ModelSpec("claude-sonnet-4.6", ("low", "medium", "high", "max"), r"^Claude Sonnet 4\.6\b", "adaptive"),
    ModelSpec("claude-haiku-4.5", (), r"^Claude 4\.5 Haiku\b", "nonreasoning"),
    ModelSpec("claude-opus-5", ("low", "medium", "high", "xhigh", "max"), r"^Claude Opus 5\b", "adaptive"),
    ModelSpec("claude-opus-4.8", ("low", "medium", "high", "xhigh", "max"), r"^Claude Opus 4\.8\b", "adaptive"),
    ModelSpec("claude-opus-4.7", ("low", "medium", "high", "xhigh", "max"), r"^Claude Opus 4\.7\b", "adaptive"),
    ModelSpec("claude-opus-4.6", ("low", "medium", "high", "max"), r"^Claude Opus 4\.6\b", "adaptive"),
    ModelSpec("gpt-5.6-sol", ("low", "medium", "high", "xhigh", "max"), r"^GPT-5\.6 Sol \(", "parenthesized"),
    ModelSpec("gpt-5.6-terra", ("low", "medium", "high", "xhigh", "max"), r"^GPT-5\.6 Terra \(", "parenthesized"),
    ModelSpec("gpt-5.6-luna", ("low", "medium", "high", "xhigh", "max"), r"^GPT-5\.6 Luna \(", "parenthesized"),
    ModelSpec("gpt-5.5", ("low", "medium", "high", "xhigh"), r"^GPT-5\.5 \(", "parenthesized"),
    ModelSpec("gpt-5.4", ("low", "medium", "high", "xhigh"), r"^GPT-5\.4 \(", "parenthesized"),
    ModelSpec("gpt-5.3-codex", ("low", "medium", "high", "xhigh"), r"^GPT-5\.3 Codex \(", "parenthesized"),
    ModelSpec("gpt-5.4-mini", ("low", "medium", "high", "xhigh"), r"^GPT-5\.4 mini \(", "parenthesized"),
    ModelSpec("gpt-5-mini", ("low", "medium", "high"), r"^GPT-5 mini \(", "parenthesized"),
    ModelSpec("gemini-3.1-pro-preview", ("low", "medium", "high"), r"^Gemini 3\.1 Pro Preview$", "unknown"),
    ModelSpec("gemini-3.6-flash", ("minimal", "low", "medium", "high"), r"^Gemini 3\.6 Flash \(", "parenthesized"),
    ModelSpec("gemini-3.5-flash", ("minimal", "low", "medium", "high"), r"^Gemini 3\.5 Flash \(", "parenthesized"),
    ModelSpec("kimi-k2.7-code", (), r"^Kimi K2\.7 Code$", "unknown"),
    ModelSpec("mai-code-1-flash-picker", ("low", "medium", "high"), r"^MAI[- ]Code 1 Flash", "parenthesized"),
)

RSC_PUSH = re.compile(
    r'self\.__next_f\.push\(\[\s*1,\s*"((?:[^"\\]|\\.)*)"\s*\]\)',
    re.DOTALL,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def request_json(url: str, *, headers: dict[str, str] | None = None) -> Any:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def request_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read().decode("utf-8", "replace")


def fetch_aa_models() -> list[dict[str, Any]]:
    key = os.environ.get("AA_API_KEY") or os.environ.get("ARTIFICIAL_ANALYSIS_API_KEY")
    if not key:
        raise RuntimeError("Set AA_API_KEY or ARTIFICIAL_ANALYSIS_API_KEY.")
    payload = request_json(AA_MODELS_URL, headers={"x-api-key": key})
    models = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(models, list):
        raise RuntimeError("Artificial Analysis returned an unexpected model payload.")
    return models


def decode_rsc_stream(html: str) -> str:
    parts: list[str] = []
    for raw in RSC_PUSH.findall(html):
        try:
            parts.append(json.loads(f'"{raw}"'))
        except json.JSONDecodeError:
            parts.append(raw.replace(r"\"", '"').replace(r"\\", "\\"))
    if not parts:
        raise RuntimeError("No Next.js RSC chunks were found.")
    return "\n".join(parts)


def extract_balanced_array(stream: str, key: str) -> list[dict[str, Any]]:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*\[', stream)
    if not match:
        raise RuntimeError(f"RSC array {key!r} was not found.")
    start = match.end() - 1
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(stream)):
        char = stream[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                value = json.loads(stream[start : index + 1])
                if not isinstance(value, list):
                    raise RuntimeError(f"RSC value {key!r} was not an array.")
                return value
    raise RuntimeError(f"RSC array {key!r} was not balanced.")


def fetch_rich_rows(url: str = AA_RSC_URL) -> list[dict[str, Any]]:
    stream = decode_rsc_stream(request_text(url))
    return extract_balanced_array(stream, "defaultData")


def _read_frame(stream) -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        name, _, value = line.decode("ascii", "replace").partition(":")
        headers[name.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    return json.loads(stream.read(length).decode("utf-8"))


def _copilot_command() -> list[str]:
    executable = shutil.which("copilot")
    if not executable:
        raise RuntimeError("copilot executable was not found.")
    arguments = [executable, "--server", "--stdio", "--disable-builtin-mcps"]
    if os.name != "nt" or Path(executable).suffix.lower() not in {".bat", ".cmd"}:
        return arguments
    command_line = subprocess.list2cmdline(arguments)
    return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", command_line]


def _terminate_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()


def discover_copilot_models(timeout_seconds: float = 20.0) -> list[dict[str, Any]]:
    """Best-effort live discovery through the Copilot CLI SDK server."""
    process = subprocess.Popen(
        _copilot_command(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if process.stdin is None or process.stdout is None:
        _terminate_process_tree(process)
        raise RuntimeError("Could not open Copilot SDK server pipes.")

    responses: queue.Queue[dict[str, Any] | BaseException | None] = queue.Queue()

    def reader() -> None:
        try:
            while True:
                frame = _read_frame(process.stdout)
                responses.put(frame)
                if frame is None:
                    return
        except BaseException as error:
            responses.put(error)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    request = {"jsonrpc": "2.0", "id": 1, "method": "models.list", "params": {}}
    body = json.dumps(request, separators=(",", ":")).encode("utf-8")
    try:
        process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
        process.stdin.flush()
    except BaseException:
        _terminate_process_tree(process)
        raise
    deadline = time.monotonic() + timeout_seconds
    try:
        while time.monotonic() < deadline:
            try:
                message = responses.get(timeout=max(0.05, deadline - time.monotonic()))
            except queue.Empty:
                break
            if isinstance(message, BaseException):
                raise RuntimeError(f"Copilot SDK server failed: {message}") from message
            if message is None:
                break
            if message.get("id") != 1:
                continue
            if "error" in message:
                raise RuntimeError(f"Copilot models.list failed: {message['error']}")
            models = (message.get("result") or {}).get("models")
            if not isinstance(models, list):
                raise RuntimeError("Copilot models.list returned no model array.")
            return [model for model in models if model.get("id") != "auto"]
        raise TimeoutError("Copilot models.list timed out.")
    finally:
        _terminate_process_tree(process)


def effective_specs(discovered: list[dict[str, Any]] | None) -> tuple[list[ModelSpec], str, int]:
    if not discovered:
        return list(MODEL_SPECS), "embedded", 0
    by_id = {spec.copilot_id: spec for spec in MODEL_SPECS}
    result: list[ModelSpec] = []
    omitted_count = 0
    for model in discovered:
        model_id = str(model.get("id") or "").strip()
        if not model_id:
            continue
        existing = by_id.get(model_id)
        if not existing:
            omitted_count += 1
            continue
        efforts = tuple(
            effort
            for effort in EFFORT_ORDER
            if effort in (model.get("supportedReasoningEfforts") or [])
        )
        result.append(replace(existing, efforts=efforts))
    return result, "copilot-models.list (public allowlist only)", omitted_count


def positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def valid_runtime(model: dict[str, Any]) -> bool:
    return positive_number(model.get("median_output_tokens_per_second")) and positive_number(
        model.get("median_time_to_first_token_seconds")
    )


def effort_matches(name: str, effort: str, mode: str) -> bool:
    if mode == "adaptive":
        return bool(
            re.search(
                rf"\bAdaptive Reasoning, {re.escape(effort)} Effort\)",
                name,
                re.IGNORECASE,
            )
        )
    return bool(re.search(rf"\({re.escape(effort)}\)$", name, re.IGNORECASE))


def metric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def base_row(model: dict[str, Any], evaluation_keys: list[str]) -> dict[str, Any]:
    evaluations = model.get("evaluations") or {}
    pricing = model.get("pricing") or {}
    creator = model.get("model_creator") or {}
    metrics = {f"eval.{key}": metric_value(evaluations.get(key)) for key in evaluation_keys}
    metrics.update(
        {
            "metric.median_output_tokens_per_second": metric_value(
                model.get("median_output_tokens_per_second")
            ),
            "metric.median_time_to_first_token_seconds": metric_value(
                model.get("median_time_to_first_token_seconds")
            ),
            "metric.median_time_to_first_answer_token": metric_value(
                model.get("median_time_to_first_answer_token")
            ),
            "price.price_1m_input_tokens": metric_value(pricing.get("price_1m_input_tokens")),
            "price.price_1m_output_tokens": metric_value(pricing.get("price_1m_output_tokens")),
            "price.price_1m_blended_3_to_1": metric_value(
                pricing.get("price_1m_blended_3_to_1")
            ),
        }
    )
    return {
        "aa_id": model.get("id"),
        "slug": model.get("slug"),
        "name": model.get("name") or "",
        "creator": creator.get("name"),
        "release_date": model.get("release_date"),
        "metrics": metrics,
        "coding": metric_value(evaluations.get("artificial_analysis_coding_index")),
        "intelligence": metric_value(
            evaluations.get("artificial_analysis_intelligence_index")
        ),
        "tok_s": metric_value(model.get("median_output_tokens_per_second")),
        "ttft": metric_value(model.get("median_time_to_first_token_seconds")),
    }


def put_metric(metrics: dict[str, Any], key: str, value: Any) -> None:
    number = metric_value(value)
    if number is not None:
        metrics[key] = number


def enrich_rich(row: dict[str, Any], rich: dict[str, Any]) -> None:
    metrics = row["metrics"]
    tokens = rich.get("intelligenceIndexOutputTokensPerTask")
    if isinstance(tokens, dict):
        put_metric(metrics, "task.output_tokens_total", tokens.get("output"))
        put_metric(metrics, "task.output_tokens_reasoning", tokens.get("reasoning"))
        put_metric(metrics, "task.output_tokens_answer", tokens.get("answer"))
    put_metric(metrics, "task.decode_time_seconds", rich.get("intelligenceIndexTimePerTask"))
    gdpval = rich.get("gdpval_v2_breakdown")
    if isinstance(gdpval, dict):
        put_metric(metrics, "rich.gdpval_turns_per_task", gdpval.get("avg_turns"))

    task_cost = rich.get("intelligenceIndexCostPerTask")
    cost = task_cost.get("cost") if isinstance(task_cost, dict) else None
    if isinstance(cost, dict):
        for component in (
            "total",
            "input",
            "nonCacheInput",
            "cacheRead",
            "cacheWrite",
            "output",
            "reasoning",
            "answer",
        ):
            put_metric(metrics, f"task.cost_{component}", cost.get(component))

    for source, target in {
        "agentic_index": "rich.agentic_index",
        "gdpval_v2": "rich.gdpval_v2",
        "gdpval_normalized": "rich.gdpval_normalized",
        "terminalbench_v2_1": "rich.terminalbench_v2_1",
        "tau_banking": "rich.tau_banking",
        "critpt": "rich.critpt",
        "omniscience": "rich.omniscience",
        "mmmu_pro": "rich.mmmu_pro",
        "apex_agents": "rich.apex_agents",
        "it_bench_sre": "rich.it_bench_sre",
    }.items():
        put_metric(metrics, target, rich.get(source))

    automation = rich.get("automation_bench_breakdown")
    if isinstance(automation, dict):
        summary = automation.get("summary")
        if isinstance(summary, dict):
            put_metric(metrics, "rich.automation_completion", summary.get("completion"))
            put_metric(metrics, "rich.automation_strict_score", summary.get("strict_score"))
            put_metric(
                metrics,
                "rich.automation_violations_per_task",
                summary.get("violations_per_task"),
            )

    enterprise = rich.get("enterprise_ops_gym_breakdown")
    if isinstance(enterprise, dict):
        summary = enterprise.get("summary")
        if isinstance(summary, dict):
            put_metric(metrics, "rich.enterprise_ops_success_rate", summary.get("success_rate"))
            put_metric(
                metrics,
                "rich.enterprise_ops_task_time_p50_seconds",
                (summary.get("active_task_ms_p50") or 0) / 1000,
            )
            put_metric(
                metrics,
                "rich.enterprise_ops_tool_calls_p50",
                summary.get("tool_calls_p50"),
            )

    harvey = rich.get("harvey_lab_breakdown")
    if isinstance(harvey, dict):
        put_metric(metrics, "rich.harvey_criteria_pass", harvey.get("criteria_pass"))
        put_metric(metrics, "rich.harvey_all_pass", harvey.get("all_pass"))
        turns = harvey.get("turns")
        if isinstance(turns, dict):
            put_metric(metrics, "rich.harvey_turns_per_task", turns.get("avg_per_task"))
    row["aa_rsc_enriched"] = True


def enrich_briefcase(row: dict[str, Any], rich: dict[str, Any]) -> None:
    briefcase = rich.get("briefcase")
    if not isinstance(briefcase, dict):
        return
    metrics = row["metrics"]
    put_metric(metrics, "briefcase.elo", briefcase.get("elo"))
    put_metric(metrics, "briefcase.rubric_elo", (briefcase.get("rubric") or {}).get("elo"))
    put_metric(
        metrics,
        "briefcase.analytical_quality_elo",
        (briefcase.get("analyticalQuality") or {}).get("elo"),
    )
    put_metric(
        metrics,
        "briefcase.presentation_elo",
        (briefcase.get("presentation") or {}).get("elo"),
    )
    put_metric(metrics, "briefcase.rubric_pass_rate", briefcase.get("rubricPassRate"))
    turns = briefcase.get("turns")
    if isinstance(turns, dict):
        put_metric(metrics, "briefcase.turns_per_task", turns.get("avgPerTask"))

    breakdown = rich.get("briefcase_breakdown")
    task_count = None
    if isinstance(breakdown, dict):
        task_count = metric_value(breakdown.get("num_tasks"))
        put_metric(metrics, "briefcase.perfect_task_rate", breakdown.get("perfect_task_rate"))
        durations = breakdown.get("duration_ms_per_task_percentiles")
        if isinstance(durations, dict):
            for percentile in ("p25", "p50", "p75", "p95"):
                value = metric_value(durations.get(percentile))
                if value is not None:
                    metrics[f"briefcase.task_time_{percentile}_seconds"] = value / 1000

    if positive_number(task_count):
        put_metric(
            metrics,
            "briefcase.tool_calls_per_task",
            (briefcase.get("totalToolCalls") or 0) / task_count,
        )
        put_metric(
            metrics,
            "briefcase.tool_time_per_task_seconds",
            (briefcase.get("totalToolMs") or 0) / task_count / 1000,
        )
        cost = rich.get("briefcaseCost")
        if isinstance(cost, dict):
            for component in (
                "total",
                "input",
                "nonCacheInput",
                "cacheRead",
                "cacheWrite",
                "output",
                "reasoning",
                "answer",
            ):
                value = metric_value(cost.get(component))
                if value is not None:
                    metrics[f"briefcase.cost_per_task_{component}"] = value / task_count
    row["aa_briefcase_enriched"] = True


def build_combo(
    spec: ModelSpec,
    reasoning: str,
    candidates: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    evaluation_keys: list[str],
    missing_status: str,
    rich_by_slug: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    valid_matches = [model for model in matches if valid_runtime(model)]
    model = valid_matches[0] if valid_matches else None
    if model:
        status = "Tracked"
    elif matches:
        status = "AA row excluded because runtime measurements are nonpositive or invalid"
    else:
        status = missing_status
    row = base_row(model, evaluation_keys) if model else None
    if row and row.get("slug") in rich_by_slug:
        enrich_rich(row, rich_by_slug[row["slug"]])
    return {
        "copilot_id": spec.copilot_id,
        "reasoning": reasoning,
        "tracked": row is not None,
        "status": status,
        "candidate_names": [candidate.get("name") for candidate in candidates],
        "row": row,
    }


def build_combos(
    models: list[dict[str, Any]],
    rich_rows: list[dict[str, Any]],
    briefcase_rows: list[dict[str, Any]],
    specs: list[ModelSpec],
) -> tuple[list[dict[str, Any]], list[str]]:
    evaluation_keys = sorted(
        {key for model in models for key in (model.get("evaluations") or {})}
    )
    rich_by_slug = {
        str(row["slug"]): row
        for row in rich_rows
        if isinstance(row, dict) and row.get("slug")
    }
    briefcase_by_slug = {
        str(row["slug"]): row
        for row in briefcase_rows
        if isinstance(row, dict) and row.get("slug")
    }
    combos: list[dict[str, Any]] = []
    for spec in specs:
        pattern = re.compile(spec.aa_pattern, re.IGNORECASE)
        candidates = [
            model for model in models if pattern.search(str(model.get("name") or ""))
        ]
        if spec.mode == "fast":
            for effort in spec.efforts:
                combos.append(
                    build_combo(
                        spec,
                        effort,
                        candidates,
                        [],
                        evaluation_keys,
                        "AA tracks the standard model but not Copilot's distinct fast serving mode",
                        rich_by_slug,
                    )
                )
            continue
        if spec.mode == "unknown":
            for effort in spec.efforts:
                combos.append(
                    build_combo(
                        spec,
                        effort,
                        candidates,
                        [],
                        evaluation_keys,
                        "AA tracks the model but does not identify this reasoning effort",
                        rich_by_slug,
                    )
                )
            combos.append(
                build_combo(
                    spec,
                    "not supported",
                    candidates,
                    candidates,
                    evaluation_keys,
                    "No AA row found",
                    rich_by_slug,
                )
            )
            if combos[-1]["tracked"]:
                combos[-1]["status"] = "Tracked with unknown/unspecified AA reasoning effort"
            continue
        if not spec.efforts:
            matches = [
                model
                for model in candidates
                if "(Non-reasoning)" in str(model.get("name") or "")
            ]
            combos.append(
                build_combo(
                    spec,
                    "not supported",
                    candidates,
                    matches,
                    evaluation_keys,
                    "No AA non-reasoning row found",
                    rich_by_slug,
                )
            )
            if combos[-1]["tracked"]:
                combos[-1]["status"] = "Tracked as non-reasoning"
            continue
        for effort in spec.efforts:
            matches = [
                model
                for model in candidates
                if effort_matches(str(model.get("name") or ""), effort, spec.mode)
            ]
            combos.append(
                build_combo(
                    spec,
                    effort,
                    candidates,
                    matches,
                    evaluation_keys,
                    "Model row exists, but not this reasoning level"
                    if candidates
                    else "No AA row found",
                    rich_by_slug,
                )
            )
    for combo in combos:
        row = combo.get("row")
        if row and row.get("slug") in briefcase_by_slug:
            enrich_briefcase(row, briefcase_by_slug[row["slug"]])
    return combos, evaluation_keys


def metric_def(
    key: str,
    label: str,
    *,
    higher_better: bool,
    group: str,
    unit: str,
    source: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "higherBetter": higher_better,
        "group": group,
        "unit": unit,
        "source": source,
    }


def metric_definitions(
    evaluation_keys: list[str], combos: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [combo["row"] for combo in combos if combo.get("row")]

    def populated(key: str) -> bool:
        return any(row["metrics"].get(key) is not None for row in rows)

    quality = []
    for key, label in (
        ("artificial_analysis_coding_index", "AA Coding Index"),
        ("artificial_analysis_intelligence_index", "AA Intelligence Index"),
        ("ifbench", "IFBench"),
    ):
        metric_key = f"eval.{key}"
        if populated(metric_key):
            quality.append(
                metric_def(
                    metric_key,
                    label,
                    higher_better=True,
                    group="Core daily-use benchmarks",
                    unit="score",
                    source="AA API",
                )
            )
    for key, label in (
        ("rich.agentic_index", "AA Agentic Index"),
        ("rich.gdpval_v2", "GDPval-AA v2"),
        ("rich.enterprise_ops_success_rate", "AA Enterprise Ops Gym success rate"),
        ("rich.terminalbench_v2_1", "Terminal-Bench v2.1"),
        ("rich.omniscience", "AA-Omniscience"),
        ("rich.mmmu_pro", "MMMU Pro"),
    ):
        if populated(key):
            quality.append(
                metric_def(
                    key,
                    label,
                    higher_better=True,
                    group="AA rich quality",
                    unit="score",
                    source="AA public RSC",
                )
            )
    for key, label, unit in (
        ("briefcase.elo", "AA-Briefcase overall Elo", "Elo"),
        ("briefcase.rubric_elo", "AA-Briefcase rubric Elo", "Elo"),
        (
            "briefcase.analytical_quality_elo",
            "AA-Briefcase analytical quality Elo",
            "Elo",
        ),
        ("briefcase.presentation_elo", "AA-Briefcase presentation Elo", "Elo"),
    ):
        if populated(key):
            quality.append(
                metric_def(
                    key,
                    label,
                    higher_better=True,
                    group="AA-Briefcase",
                    unit=unit,
                    source="AA-Briefcase public RSC",
                )
            )

    operational = [
        metric_def(
            "metric.median_output_tokens_per_second",
            "Output tokens/sec",
            higher_better=True,
            group="Performance",
            unit="tokens/sec",
            source="AA API",
        ),
        metric_def(
            "metric.median_time_to_first_token_seconds",
            "Time to first token (sec)",
            higher_better=False,
            group="Performance",
            unit="seconds",
            source="AA API",
        ),
        metric_def(
            "price.price_1m_blended_3_to_1",
            "Blended price / 1M tokens (3:1)",
            higher_better=False,
            group="Pricing",
            unit="USD",
            source="AA API",
        ),
    ]
    for key, label, unit in (
        ("task.decode_time_seconds", "Intelligence Index decode time per task", "seconds"),
        ("task.cost_total", "Intelligence Index cost per task", "USD"),
        ("rich.gdpval_turns_per_task", "GDPval-AA turns per task", "turns"),
        (
            "rich.enterprise_ops_task_time_p50_seconds",
            "Enterprise Ops active task time p50 (sec)",
            "seconds",
        ),
        ("briefcase.task_time_p50_seconds", "AA-Briefcase task time p50 (sec)", "seconds"),
        ("briefcase.task_time_p95_seconds", "AA-Briefcase task time p95 (sec)", "seconds"),
        ("briefcase.cost_per_task_total", "AA-Briefcase cost per task: total", "USD"),
    ):
        if populated(key):
            source = (
                "AA-Briefcase public RSC"
                if key.startswith("briefcase.")
                else "AA public RSC"
            )
            operational.append(
                metric_def(
                    key,
                    label,
                    higher_better=False,
                    group="AA task efficiency",
                    unit=unit,
                    source=source,
                )
            )
    return quality, [definition for definition in operational if populated(definition["key"])]


def metric_pairs(
    quality_metrics: list[dict[str, Any]],
    operational_metrics: list[dict[str, Any]],
) -> dict[str, list[str]]:
    available_quality = {metric["key"] for metric in quality_metrics}
    available_operational = {metric["key"] for metric in operational_metrics}
    generic = [
        "metric.median_output_tokens_per_second",
        "metric.median_time_to_first_token_seconds",
        "price.price_1m_blended_3_to_1",
    ]
    intelligence = ["task.decode_time_seconds", "task.cost_total"]
    briefcase = [
        "briefcase.task_time_p50_seconds",
        "briefcase.task_time_p95_seconds",
        "briefcase.cost_per_task_total",
    ]
    pairs = {
        "eval.artificial_analysis_coding_index": generic,
        "eval.artificial_analysis_intelligence_index": intelligence,
        "eval.ifbench": generic,
        "rich.agentic_index": generic,
        "rich.terminalbench_v2_1": generic,
        "rich.gdpval_v2": ["rich.gdpval_turns_per_task"],
        "rich.omniscience": generic,
        "rich.mmmu_pro": generic,
        "rich.enterprise_ops_success_rate": [
            "rich.enterprise_ops_task_time_p50_seconds"
        ],
        "briefcase.elo": briefcase,
        "briefcase.rubric_elo": briefcase,
        "briefcase.analytical_quality_elo": briefcase,
        "briefcase.presentation_elo": briefcase,
    }
    return {
        quality: [metric for metric in metrics if metric in available_operational]
        for quality, metrics in pairs.items()
        if quality in available_quality
    }


def build_data(
    *,
    discover_models: bool,
    include_rsc: bool,
) -> dict[str, Any]:
    discovery_error = None
    discovered = None
    if discover_models:
        try:
            discovered = discover_copilot_models()
        except Exception as error:
            discovery_error = str(error)
    specs, registry_source, omitted_unrecognized_model_count = effective_specs(discovered)
    aa_models = fetch_aa_models()
    rich_rows: list[dict[str, Any]] = []
    briefcase_rows: list[dict[str, Any]] = []
    rsc_error = None
    briefcase_error = None
    if include_rsc:
        try:
            rich_rows = fetch_rich_rows()
        except Exception as error:
            rsc_error = str(error)
        try:
            briefcase_rows = fetch_rich_rows(AA_BRIEFCASE_URL)
        except Exception as error:
            briefcase_error = str(error)
    combos, evaluation_keys = build_combos(
        aa_models,
        rich_rows,
        briefcase_rows,
        specs,
    )
    quality_metrics, operational_metrics = metric_definitions(evaluation_keys, combos)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "attribution": ATTRIBUTION,
        "sources": {
            "aa_api": {"url": AA_MODELS_URL, "rows": len(aa_models)},
            "aa_rsc": {
                "url": AA_RSC_URL,
                "rows": len(rich_rows),
                "error": rsc_error,
            },
            "aa_briefcase_rsc": {
                "url": AA_BRIEFCASE_URL,
                "rows": len(briefcase_rows),
                "error": briefcase_error,
            },
            "copilot_registry": {
                "source": registry_source,
                "discovery_requested": discover_models,
                "error": discovery_error,
                "omitted_unrecognized_model_count": omitted_unrecognized_model_count,
            },
        },
        "model_matrix": [
            {"copilot_id": spec.copilot_id, "reasoning_levels": list(spec.efforts)}
            for spec in specs
        ],
        "quality_metrics": quality_metrics,
        "operational_metrics": operational_metrics,
        "metric_pairs": metric_pairs(quality_metrics, operational_metrics),
        "combos": combos,
        "notes": [
            "AA API rows are matched by exact model family and exact effort labels.",
            "Claude reasoning levels match only Adaptive Reasoning rows.",
            "Unqualified AA rows are shown under none / unknown effort.",
            "Distinct Copilot serving modes such as Opus Fast are not assigned standard-model runtime measurements.",
            "Rows with missing or nonpositive runtime measurements are not plotted.",
            "AA time per task is weighted decode time and excludes TTFT and request overhead.",
            "AA-Briefcase task duration, turns, tool calls, and cost use the benchmark's own observed task runs.",
            "AA-Briefcase cost per task is provider list-price cost observed by AA, not Copilot premium-request billing.",
            "Live discovery only updates models in the reviewed public allowlist; unrecognized IDs are omitted without being stored.",
        ],
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Copilot model Pareto explorer for Artificial Analysis</title>
<script>
  (() => {
    const param = new URLSearchParams(window.location.search).get("scoutTheme");
    const theme =
      param || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", theme);
  })();
</script>
<style>
:root {
  color-scheme: light;
  --cp-bg: #f7f4ef;
  --cp-bg-elevated: #fcfbf8;
  --cp-surface: #ffffff;
  --cp-surface-soft: #f5f5f5;
  --cp-border: #dedede;
  --cp-border-strong: #919191;
  --cp-text: #242424;
  --cp-text-muted: #5c5c5c;
  --cp-text-soft: #6f6f6f;
  --cp-accent: #b11f4b;
  --cp-accent-hover: #9a1a41;
  --cp-accent-soft: rgba(177, 31, 75, 0.08);
  --cp-accent-fg: #ffffff;
  --cp-success: #16a34a;
  --cp-danger: #dc2626;
  --cp-warning: #f59e0b;
  --cp-link: #0078d4;
  --cp-shadow: 0 18px 48px rgba(0, 0, 0, 0.12);
  --cp-overlay: rgba(255, 255, 255, 0.8);
  --cp-panel: rgba(255, 255, 255, 0.86);
  --cp-panel-strong: rgba(255, 255, 255, 0.96);
  --cp-sheen: rgba(255, 255, 255, 0.55);
  --cp-highlight: rgba(177, 31, 75, 0.12);
}
html[data-theme="dark"] {
  color-scheme: dark;
  --cp-bg: #3d3b3a;
  --cp-bg-elevated: #343231;
  --cp-surface: #292929;
  --cp-surface-soft: #2e2e2e;
  --cp-border: #474747;
  --cp-border-strong: #5f5f5f;
  --cp-text: #dedede;
  --cp-text-muted: #919191;
  --cp-text-soft: #b0b0b0;
  --cp-accent: #fd8ea1;
  --cp-accent-hover: #fb7b91;
  --cp-accent-soft: rgba(253, 142, 161, 0.14);
  --cp-accent-fg: #1a1a1a;
  --cp-success: #4ade80;
  --cp-danger: #f87171;
  --cp-warning: #fbbf24;
  --cp-link: #4da6ff;
  --cp-shadow: 0 18px 48px rgba(0, 0, 0, 0.32);
  --cp-overlay: rgba(41, 41, 41, 0.88);
  --cp-panel: rgba(41, 41, 41, 0.72);
  --cp-panel-strong: rgba(41, 41, 41, 0.96);
  --cp-sheen: rgba(255, 255, 255, 0.04);
  --cp-highlight: rgba(253, 142, 161, 0.12);
}
*{box-sizing:border-box}body{margin:0;background:var(--cp-bg);color:var(--cp-text);font-family:"Segoe UI",Aptos,Calibri,-apple-system,BlinkMacSystemFont,sans-serif}main{max-width:1400px;margin:auto;padding:32px}h1{margin:0 0 8px;font-size:28px}h2{margin:0 0 16px;font-size:20px}p{color:var(--cp-text-muted);line-height:1.5}.card{background:var(--cp-surface);border:1px solid var(--cp-border);border-radius:16px;box-shadow:0 0 2px var(--cp-border),0 1px 2px var(--cp-border);padding:20px;margin:20px 0}.toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:16px}label{color:var(--cp-text-muted);font-size:13px}select,input{background:var(--cp-surface-soft);color:var(--cp-text);border:1px solid var(--cp-border);border-radius:.625rem;padding:8px 10px;font:inherit;max-width:390px}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-top:16px}.stat{background:var(--cp-surface-soft);border:1px solid var(--cp-border);border-radius:.625rem;padding:12px}.stat strong{display:block;font-size:24px}.stat span{color:var(--cp-text-muted);font-size:13px}.chart-wrap,.table-wrap{overflow:auto}svg{width:100%;min-width:860px;height:590px;background:var(--cp-surface-soft);border:1px solid var(--cp-border);border-radius:.625rem}.axis,.tick{fill:var(--cp-text-muted);font-size:12px}.grid,.axis-line{stroke:var(--cp-border)}.point{fill:var(--cp-link);stroke:var(--cp-surface);stroke-width:2;opacity:.88}.point.frontier{fill:var(--cp-accent);stroke:var(--cp-accent-fg);stroke-width:3;opacity:1}.frontier-line{fill:none;stroke:var(--cp-accent);stroke-width:2;stroke-dasharray:5 5}.legend,.matrix-legend{display:flex;flex-wrap:wrap;gap:14px;color:var(--cp-text-muted);font-size:13px;margin-top:10px}.legend i,.matrix-dot{display:inline-block;width:14px;height:14px;border-radius:999px;margin-right:5px;vertical-align:-2px;background:var(--cp-link);border:2px solid var(--cp-border)}.legend .frontier-key i{background:var(--cp-accent)}table{width:100%;border-collapse:collapse;min-width:850px}th,td{border-bottom:1px solid var(--cp-border);padding:9px;text-align:center}th{position:sticky;top:0;background:var(--cp-surface-soft);z-index:1}th:first-child,td:first-child{text-align:left;position:sticky;left:0;background:var(--cp-surface);z-index:2}th:first-child{background:var(--cp-surface-soft);z-index:3}.matrix-dot{width:18px;height:18px;margin:0;cursor:help}.matrix-dot.yes{background:var(--cp-success);border-color:var(--cp-success)}.matrix-dot.partial{background:var(--cp-warning);border-color:var(--cp-warning)}.matrix-dot.no{background:var(--cp-danger);border-color:var(--cp-danger)}.matrix-dot.blank{background:var(--cp-surface);cursor:default}code{font-family:Consolas,"Courier New",Courier,monospace;background:var(--cp-surface-soft);border:1px solid var(--cp-border);border-radius:.625rem;padding:1px 5px}.tooltip{position:fixed;display:none;pointer-events:none;background:var(--cp-panel-strong);color:var(--cp-text);border:1px solid var(--cp-border-strong);border-radius:.625rem;padding:10px 12px;box-shadow:var(--cp-shadow);max-width:440px;font-size:13px;z-index:10}.muted{color:var(--cp-text-muted)}
</style>
</head>
<body><main>
<h1>Copilot model Pareto explorer for Artificial Analysis</h1>
<p id="subtitle"></p>
<section class="stats" id="stats"></section>
<section class="card">
<h2>Pareto chart</h2>
<div class="toolbar">
<label>X speed/cost metric <select id="xMetric"></select></label>
<label>Y quality metric <select id="yMetric"></select></label>
<label>Family <select id="family"><option value="all">All</option></select></label>
</div>
<div class="chart-wrap"><svg id="chart" role="img" aria-label="Pareto scatter chart"></svg></div>
<div class="legend"><span><i></i>Tracked row</span><span class="frontier-key"><i></i>Pareto frontier</span><span>Circle Claude · square GPT · diamond Gemini · triangle other</span><span>Upper-left is best</span></div>
</section>
<section class="card">
<h2>Coverage matrix</h2>
<div class="toolbar"><label>Search <input id="search" placeholder="model or AA row"></label></div>
<div class="table-wrap"><table id="matrix"></table></div>
<div class="matrix-legend"><span><i class="matrix-dot yes"></i>Tracked</span><span><i class="matrix-dot partial"></i>Model exists, level missing</span><span><i class="matrix-dot no"></i>No AA row</span><span><i class="matrix-dot blank"></i>Not exposed</span></div>
</section>
<section class="card"><h2>Provenance and notes</h2><div id="provenance"></div></section>
</main><div class="tooltip" id="tooltip"></div>
<script id="report-data" type="application/json">__REPORT_DATA__</script>
<script>
const DATA=JSON.parse(document.getElementById('report-data').textContent);
const xMetric=document.getElementById('xMetric'),yMetric=document.getElementById('yMetric'),family=document.getElementById('family'),search=document.getElementById('search'),tooltip=document.getElementById('tooltip');
const metricMap=new Map([...DATA.operational_metrics,...DATA.quality_metrics].map(m=>[m.key,m]));
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function css(n){return getComputedStyle(document.documentElement).getPropertyValue(n).trim()}
function fmt(v,d){if(v==null||!Number.isFinite(Number(v)))return'—';const n=Number(v),digits=d??(Math.abs(n)>0&&Math.abs(n)<2?3:1),s=n.toFixed(digits);return s.includes('.')?s.replace(/0+$/,'').replace(/\.$/,''):s}
function meta(k){return metricMap.get(k)||{label:k,higherBetter:true}}
function valid(k,v){if(v==null||v==='')return false;const n=Number(v);if(!Number.isFinite(n)||n<0)return false;if(k.startsWith('eval.artificial_analysis_')||k.includes('time_to_')||k==='metric.median_output_tokens_per_second')return n>0;return true}
function rows(){const f=family.value,x=xMetric.value,y=yMetric.value;return DATA.combos.filter(c=>c.tracked&&c.row&&Number(c.row.metrics['metric.median_output_tokens_per_second'])>0&&valid(x,c.row.metrics[x])&&valid(y,c.row.metrics[y])&&(f==='all'||c.copilot_id.includes(f)))}
function dominates(a,b,x,y){const ax=+a.row.metrics[x],bx=+b.row.metrics[x],ay=+a.row.metrics[y],by=+b.row.metrics[y],xm=meta(x).higherBetter!==false,ym=meta(y).higherBetter!==false;const xok=xm?ax>=bx:ax<=bx,yok=ym?ay>=by:ay<=by,xs=xm?ax>bx:ax<bx,ys=ym?ay>by:ay<by;return xok&&yok&&(xs||ys)}
function pareto(rs,x,y){return rs.filter(a=>!rs.some(b=>a!==b&&dominates(b,a,x,y)))}
function scale(v,min,max,a,b){return max===min?(a+b)/2:a+(v-min)*(b-a)/(max-min)}
function quantile(values,p){const s=[...values].sort((a,b)=>a-b),i=(s.length-1)*p,l=Math.floor(i),u=Math.ceil(i);return l===u?s[l]:s[l]+(s[u]-s[l])*(i-l)}
function outliers(points,key,higher){if(points.length<4)return new Set;const vals=points.map(p=>p[key]),q1=quantile(vals,.25),q3=quantile(vals,.75),iqr=q3-q1;if(!(iqr>0))return new Set;const fence=higher?q1-1.5*iqr:q3+1.5*iqr;return new Set(points.filter(p=>!p.front&&(higher?p[key]<fence:p[key]>fence)))}
function niceStep(span,n=5){const rough=span/Math.max(1,n),power=10**Math.floor(Math.log10(rough)),z=rough/power,f=z>=7.5?10:z>=3.5?5:z>=1.5?2:1;return f*power}
function niceAxis(vals){const rawMin=Math.min(...vals),rawMax=Math.max(...vals),span=rawMax-rawMin,fallback=Math.max(Math.abs(rawMax)*.1,.01),step=niceStep(span>0?span*1.1:fallback),pmin=span>0?rawMin-span*.05:rawMin-fallback*.5,pmax=span>0?rawMax+span*.05:rawMax+fallback*.5,min=Math.max(0,Math.floor(pmin/step)*step),max=Math.max(min+step,Math.ceil(pmax/step)*step),count=Math.round((max-min)/step);return{min,max,step,ticks:Array.from({length:count+1},(_,i)=>Number((min+i*step).toPrecision(14)))}}
function tick(v,step){const d=Math.max(0,-Math.floor(Math.log10(Math.abs(step)))),s=Number(v).toFixed(d);return s.includes('.')?s.replace(/0+$/,'').replace(/\.$/,''):s}
function shape(kind,x,y,r,front){const ns='http://www.w3.org/2000/svg';let n;if(kind==='claude'){n=document.createElementNS(ns,'circle');n.setAttribute('cx',x);n.setAttribute('cy',y);n.setAttribute('r',r)}else if(kind==='gpt'){n=document.createElementNS(ns,'rect');n.setAttribute('x',x-r);n.setAttribute('y',y-r);n.setAttribute('width',r*2);n.setAttribute('height',r*2);n.setAttribute('rx',2)}else if(kind==='gemini'){n=document.createElementNS(ns,'polygon');n.setAttribute('points',`${x},${y-r} ${x+r},${y} ${x},${y+r} ${x-r},${y}`)}else{n=document.createElementNS(ns,'polygon');n.setAttribute('points',`${x},${y-r} ${x+r},${y+r} ${x-r},${y+r}`)}n.setAttribute('class','point'+(front?' frontier':''));return n}
function kind(id){return id.includes('claude')?'claude':id.includes('gpt')?'gpt':id.includes('gemini')?'gemini':'other'}
function overlap(a,b){return!(a.x+a.w<b.x||b.x+b.w<a.x||a.y+a.h<b.y||b.y+b.h<a.y)}
function labelPos(text,x,y,used,right,top,bottom){const w=Math.max(56,text.length*6.2),tries=[[10,-10],[10,15],[-w-8,-10],[-w-8,15],[10,-26],[10,31]];for(const[dX,dY]of tries){const px=Math.max(82,Math.min(x+dX,right-w)),py=Math.max(top+14,Math.min(y+dY,bottom-4)),box={x:px,y:py-12,w,h:15};if(!used.some(u=>overlap(u,box))){used.push(box);return{x:px,y:py}}}return{x:Math.min(x+10,right-w),y:Math.min(y+15,bottom-4)}}
function showTip(text,e){tooltip.style.display='block';tooltip.style.left=e.clientX+12+'px';tooltip.style.top=e.clientY+12+'px';tooltip.innerHTML=text.split('\n').map(esc).join('<br>')}
function spread(items,key,min,max){items.sort((a,b)=>a[key]-b[key]);items.forEach((p,i)=>p[key]=items.length===1?(min+max)/2:min+(max-min)*i/(items.length-1))}
function renderChart(){
 const svg=document.getElementById('chart'),xKey=xMetric.value,yKey=yMetric.value,rs=rows(),front=pareto(rs,xKey,yKey),frontKeys=new Set(front.map(c=>c.copilot_id+'|'+c.reasoning)),W=1120,H=590,L=78,R=32,T=32,B=86,PR=W-R,PB=H-B;
 svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.innerHTML='';if(!rs.length){svg.innerHTML=`<text x="${W/2}" y="${H/2}" text-anchor="middle" fill="${css('--cp-text-muted')}">No valid rows for this selection.</text>`;return}
 const pts=rs.map(c=>({c,xv:+c.row.metrics[xKey],yv:+c.row.metrics[yKey],front:frontKeys.has(c.copilot_id+'|'+c.reasoning)})),xo=outliers(pts,'xv',meta(xKey).higherBetter!==false),yo=outliers(pts,'yv',meta(yKey).higherBetter!==false),hasX=xo.size>0,hasY=yo.size>0,OL=PR-82,OT=PB-62,MR=hasX?OL-10:PR,MB=hasY?OT-10:PB,xA=niceAxis(pts.filter(p=>!xo.has(p)).map(p=>p.xv)),yA=niceAxis(pts.filter(p=>!yo.has(p)).map(p=>p.yv)),xS=v=>meta(xKey).higherBetter!==false?scale(v,xA.min,xA.max,MR,L):scale(v,xA.min,xA.max,L,MR),yS=v=>meta(yKey).higherBetter!==false?scale(v,yA.min,yA.max,MB,T):scale(v,yA.min,yA.max,T,MB);
 pts.forEach(p=>{p.x=xo.has(p)?OL+42:xS(p.xv);p.y=yo.has(p)?OT+32:yS(p.yv)});spread(pts.filter(p=>xo.has(p)&&!yo.has(p)),'y',T+24,MB-12);spread(pts.filter(p=>yo.has(p)&&!xo.has(p)),'x',L+12,MR-12);pts.filter(p=>xo.has(p)&&yo.has(p)).forEach((p,i)=>{p.x=OL+22+(i%3)*18;p.y=Math.min(PB-12,OT+26+Math.floor(i/3)*16)});
 if(hasX)svg.insertAdjacentHTML('beforeend',`<rect x="${OL}" y="${T}" width="${PR-OL}" height="${PB-T}" fill="${css('--cp-highlight')}" stroke="${css('--cp-border')}"/><text class="axis" x="${OL+6}" y="${T+16}">X outliers</text>`);
 if(hasY)svg.insertAdjacentHTML('beforeend',`<rect x="${L}" y="${OT}" width="${PR-L}" height="${PB-OT}" fill="${css('--cp-highlight')}" stroke="${css('--cp-border')}"/><text class="axis" x="${L+8}" y="${OT+16}">Y outliers</text>`);
 xA.ticks.forEach(v=>{const x=xS(v);svg.insertAdjacentHTML('beforeend',`<line class="grid" x1="${x}" x2="${x}" y1="${T}" y2="${MB}"/><text class="tick x-tick" x="${x}" y="${PB+24}" text-anchor="middle">${tick(v,xA.step)}</text>`)});
 yA.ticks.forEach(v=>{const y=yS(v);svg.insertAdjacentHTML('beforeend',`<line class="grid" x1="${L}" x2="${MR}" y1="${y}" y2="${y}"/><text class="tick y-tick" x="${L-10}" y="${y+4}" text-anchor="end">${tick(v,yA.step)}</text>`)});
 svg.insertAdjacentHTML('beforeend',`<line class="axis-line" x1="${L}" x2="${PR}" y1="${PB}" y2="${PB}"/><line class="axis-line" x1="${L}" x2="${L}" y1="${T}" y2="${PB}"/><text class="axis" x="${(L+MR)/2}" y="${H-30}" text-anchor="middle">${esc(meta(xKey).label)} (${meta(xKey).higherBetter!==false?'higher':'lower'} is better; better is left)</text><text class="axis" transform="translate(18 ${(T+MB)/2}) rotate(-90)" text-anchor="middle">${esc(meta(yKey).label)} (${meta(yKey).higherBetter!==false?'higher':'lower'} is better; better is up)</text><text class="axis" x="${L+8}" y="${T+18}">best quadrant</text>`);
 const fp=front.map(c=>pts.find(p=>p.c===c)).filter(Boolean).sort((a,b)=>a.x-b.x);if(fp.length>1)svg.insertAdjacentHTML('beforeend',`<polyline class="frontier-line" points="${fp.map(p=>p.x+','+p.y).join(' ')}"/>`);
 const used=[{x:L+4,y:T+2,w:96,h:20},...pts.map(p=>({x:p.x-8,y:p.y-8,w:16,h:16}))];
 pts.forEach(p=>{const c=p.c,row=c.row,title=`${c.copilot_id} / ${c.reasoning}\n${row.name}\n${meta(xKey).label}: ${fmt(p.xv)}${xo.has(p)?' (X outlier)':''}\n${meta(yKey).label}: ${fmt(p.yv)}${yo.has(p)?' (Y outlier)':''}` ,n=shape(kind(c.copilot_id),p.x,p.y,p.front?7:5,p.front);n.addEventListener('mousemove',e=>showTip(title,e));n.addEventListener('mouseleave',()=>tooltip.style.display='none');svg.appendChild(n);if(!p.front)return;const text=c.copilot_id+' '+(c.reasoning==='not supported'?'unknown':c.reasoning),pos=labelPos(text,p.x,p.y,used,MR,T,MB),line=document.createElementNS('http://www.w3.org/2000/svg','line');line.setAttribute('x1',p.x);line.setAttribute('y1',p.y);line.setAttribute('x2',pos.x);line.setAttribute('y2',pos.y-5);line.setAttribute('stroke',css('--cp-border-strong'));svg.appendChild(line);const label=document.createElementNS('http://www.w3.org/2000/svg','text');label.setAttribute('x',pos.x);label.setAttribute('y',pos.y);label.setAttribute('fill',css('--cp-text'));label.setAttribute('font-size','11');label.textContent=text;svg.appendChild(label)})
}
function dot(c){return!c?'blank':c.tracked?'yes':c.candidate_names.length?'partial':'no'}
function renderMatrix(){const levels=['not supported',...new Set(DATA.model_matrix.flatMap(m=>m.reasoning_levels))],labels={'not supported':'none / unknown'},q=search.value.toLowerCase(),models=DATA.model_matrix.filter(m=>!q||m.copilot_id.toLowerCase().includes(q)||DATA.combos.filter(c=>c.copilot_id===m.copilot_id).some(c=>(c.row?.name||'').toLowerCase().includes(q))),map=new Map(DATA.combos.map(c=>[c.copilot_id+'|'+c.reasoning,c]));document.getElementById('matrix').innerHTML=`<thead><tr><th>Model</th>${levels.map(l=>`<th>${labels[l]||l}</th>`).join('')}</tr></thead><tbody>${models.map(m=>`<tr><td><code>${m.copilot_id}</code></td>${levels.map(l=>{const c=map.get(m.copilot_id+'|'+l),tip=c?`${c.status}${c.row?'\n'+c.row.name:''}`:'';return`<td><span class="matrix-dot ${dot(c)}" data-tip="${esc(tip)}"></span></td>`}).join('')}</tr>`).join('')}</tbody>`;document.querySelectorAll('#matrix [data-tip]').forEach(n=>{if(!n.dataset.tip)return;n.addEventListener('mousemove',e=>showTip(n.dataset.tip,e));n.addEventListener('mouseleave',()=>tooltip.style.display='none')})}
function populateXMetrics(){const current=xMetric.value,allowed=new Set(DATA.metric_pairs[yMetric.value]||[]),metrics=DATA.operational_metrics.filter(m=>allowed.has(m.key));xMetric.innerHTML=metrics.map(m=>`<option value="${m.key}">${esc(m.label)}</option>`).join('');xMetric.value=metrics.some(m=>m.key===current)?current:(metrics[0]?.key||'')}
function setup(){yMetric.innerHTML=DATA.quality_metrics.map(m=>`<option value="${m.key}">${esc(m.label)}</option>`).join('');yMetric.value=DATA.quality_metrics.some(m=>m.key==='eval.artificial_analysis_coding_index')?'eval.artificial_analysis_coding_index':DATA.quality_metrics[0].key;populateXMetrics();const families=[...new Set(DATA.model_matrix.map(m=>m.copilot_id.split('-')[0]))];family.insertAdjacentHTML('beforeend',families.map(f=>`<option value="${f}">${f[0].toUpperCase()+f.slice(1)}</option>`).join(''));const tracked=DATA.combos.filter(c=>c.tracked).length,partial=DATA.combos.filter(c=>!c.tracked&&c.candidate_names.length).length,briefcase=DATA.combos.filter(c=>c.row?.metrics?.['briefcase.elo']>0).length;document.getElementById('stats').innerHTML=`<div class="stat"><strong>${DATA.combos.length}</strong><span>model/reasoning combinations</span></div><div class="stat"><strong>${tracked}</strong><span>tracked rows</span></div><div class="stat"><strong>${briefcase}</strong><span>AA-Briefcase rows</span></div><div class="stat"><strong>${partial}</strong><span>model exists, effort missing</span></div><div class="stat"><strong>${DATA.quality_metrics.length}</strong><span>curated quality metrics</span></div><div class="stat"><strong>${DATA.operational_metrics.length}</strong><span>relevant efficiency metrics</span></div>`;document.getElementById('subtitle').textContent=`Generated ${DATA.generated_at}. ${DATA.attribution}`;const brief=DATA.sources.aa_briefcase_rsc;document.getElementById('provenance').innerHTML=`<p><strong>Copilot registry:</strong> ${esc(DATA.sources.copilot_registry.source)}${DATA.sources.copilot_registry.error?' — fallback: '+esc(DATA.sources.copilot_registry.error):''}</p><p><strong>AA API:</strong> ${DATA.sources.aa_api.rows} rows. <strong>AA Intelligence RSC:</strong> ${DATA.sources.aa_rsc.rows} rich rows. <strong>AA-Briefcase RSC:</strong> ${brief?.rows??0} rows${brief?.error?' — '+esc(brief.error):''}.</p><ul>${DATA.notes.map(n=>`<li>${esc(n)}</li>`).join('')}</ul>`;renderMatrix();renderChart()}
xMetric.addEventListener('change',renderChart);yMetric.addEventListener('change',()=>{populateXMetrics();renderChart()});family.addEventListener('change',renderChart);search.addEventListener('input',renderMatrix);setup();
</script>
</body></html>"""


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def render_html(path: Path, data: dict[str, Any]) -> None:
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace(
        "<", r"\u003c"
    )
    path.write_text(HTML_TEMPLATE.replace("__REPORT_DATA__", encoded), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fetch-only", action="store_true", help="Refresh JSON without rendering HTML.")
    mode.add_argument("--render-only", action="store_true", help="Render HTML from existing JSON.")
    parser.add_argument(
        "--discover-models",
        action="store_true",
        help="Try Copilot models.list and fall back to the embedded matrix.",
    )
    parser.add_argument("--no-rsc", action="store_true", help="Skip the public rich RSC payload.")
    parser.add_argument("--data", type=Path, help="JSON path (default: model_data.json beside this script).")
    parser.add_argument("--output", type=Path, help="HTML path (default: model_report.html beside this script).")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base = Path(__file__).resolve().parent
    data_path = (args.data or base / "model_data.json").resolve()
    output_path = (args.output or base / "model_report.html").resolve()
    if args.render_only:
        data = json.loads(data_path.read_text(encoding="utf-8"))
        render_html(output_path, data)
        print(f"Rendered {output_path}")
        return
    data = build_data(discover_models=args.discover_models, include_rsc=not args.no_rsc)
    write_json(data_path, data)
    print(f"Wrote {data_path}")
    if not args.fetch_only:
        render_html(output_path, data)
        print(f"Rendered {output_path}")


if __name__ == "__main__":
    main()
