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
import html
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
AA_RSC_URL = "https://artificialanalysis.ai/leaderboards/models"
AA_MODEL_PAGE_BASE = "https://artificialanalysis.ai/models/"
AA_BRIEFCASE_URL = "https://artificialanalysis.ai/evaluations/aa-briefcase"
COPILOT_PRICING_URL = "https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing"
ATTRIBUTION = "Data by Artificial Analysis (https://artificialanalysis.ai)."
SCHEMA_VERSION = 4
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
    ModelSpec("gpt-5.6-sol-fast", ("low", "medium", "high", "xhigh", "max"), r"^GPT-5\.6 Sol \(", "fast"),
    ModelSpec("gpt-5.6-terra", ("low", "medium", "high", "xhigh", "max"), r"^GPT-5\.6 Terra \(", "parenthesized"),
    ModelSpec("gpt-5.6-luna", ("low", "medium", "high", "xhigh", "max"), r"^GPT-5\.6 Luna \(", "parenthesized"),
    ModelSpec("gpt-6-astra", ("low", "medium", "high", "xhigh", "max"), r"^GPT-6 Astra \(", "parenthesized"),
    ModelSpec("gpt-5.5", ("low", "medium", "high", "xhigh"), r"^GPT-5\.5 \(", "parenthesized"),
    ModelSpec("gpt-5.4", ("low", "medium", "high", "xhigh"), r"^GPT-5\.4 \(", "parenthesized"),
    ModelSpec("gpt-5.3-codex", ("low", "medium", "high", "xhigh"), r"^GPT-5\.3 Codex \(", "parenthesized"),
    ModelSpec("gpt-5.4-mini", ("low", "medium", "high", "xhigh"), r"^GPT-5\.4 mini \(", "parenthesized"),
    ModelSpec("gpt-5-mini", ("low", "medium", "high"), r"^GPT-5 mini \(", "parenthesized"),
    ModelSpec("gemini-3.8-flash", ("low", "medium", "high"), r"^Gemini 3\.8 Flash \(", "parenthesized"),
    ModelSpec("gemini-3.7-flash", ("minimal", "low", "medium", "high"), r"^Gemini 3\.7 Flash \(", "parenthesized"),
    ModelSpec("gemini-3.6-flash", ("minimal", "low", "medium", "high"), r"^Gemini 3\.6 Flash \(", "parenthesized"),
    ModelSpec("gemini-3.5-flash", ("minimal", "low", "medium", "high"), r"^Gemini 3\.5 Flash \(", "parenthesized"),
    ModelSpec("grok-4.6", ("low", "medium", "high"), r"^Grok 4\.6 \(", "parenthesized"),
    ModelSpec("grok-4.5", ("low", "medium", "high"), r"^Grok 4\.5 \(", "parenthesized"),
    ModelSpec("kimi-k2.7-code", (), r"^Kimi K2\.7 Code$", "unknown"),
    ModelSpec("mai-code-1.1-flash", ("low", "medium", "high"), r"^MAI[- ]Code 1\.1 Flash", "parenthesized"),
    ModelSpec("mai-code-1-flash-picker", ("low", "medium", "high"), r"^MAI[- ]Code 1 Flash", "parenthesized"),
)

COPILOT_DOC_MODEL_NAMES = {
    "claude-haiku-4.5": "Claude Haiku 4.5",
    "claude-opus-4.7": "Claude Opus 4.7",
    "claude-opus-4.8": "Claude Opus 4.8",
    "claude-opus-5": "Claude Opus 5",
    "claude-sonnet-4.6": "Claude Sonnet 4.6",
    "claude-sonnet-5": "Claude Sonnet 5",
    "gemini-3.5-flash": "Gemini 3.5 Flash",
    "gemini-3.6-flash": "Gemini 3.6 Flash",
    "gemini-3.7-flash": "Gemini 3.7 Flash",
    "gemini-3.8-flash": "Gemini 3.8 Flash",
    "gpt-5-mini": "GPT-5 mini",
    "gpt-5.3-codex": "GPT-5.3-Codex",
    "gpt-5.4": "GPT-5.4",
    "gpt-5.4-mini": "GPT-5.4 mini",
    "gpt-5.5": "GPT-5.5",
    "gpt-5.6-luna": "GPT-5.6 Luna",
    "gpt-5.6-sol": "GPT-5.6 Sol",
    "gpt-5.6-terra": "GPT-5.6 Terra",
    "gpt-6-astra": "GPT-6 Astra",
    "mai-code-1-flash-picker": "MAI-Code-1-Flash",
    "mai-code-1.1-flash": "MAI-Code-1.1-Flash",
}

# These public models are exposed by the interactive runtime but omitted by
# models.list. Keep this set only while fresh live inference probes succeed.
LIVE_PROBE_VERIFIED_MODEL_IDS = frozenset(
    {
        "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.8-flash",
    }
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


def extract_balanced_array(stream: str, key: str, *, marker: str | None = None) -> list[dict[str, Any]]:
    best: list[dict[str, Any]] | None = None
    for match in re.finditer(rf'"{re.escape(key)}"\s*:\s*\[', stream):
        value = _read_balanced_array(stream, match.end() - 1)
        if not isinstance(value, list):
            continue
        rows = [row for row in value if isinstance(row, dict)]
        if marker and not any(marker in row for row in rows):
            continue
        if best is None or len(rows) > len(best):
            best = rows
    if best is None:
        raise RuntimeError(f"RSC array {key!r} was not found.")
    return best


def _read_balanced_array(stream: str, start: int) -> Any:
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
                try:
                    return json.loads(stream[start : index + 1])
                except json.JSONDecodeError:
                    return None
    return None


# Fields Artificial Analysis publishes only on a model detail page, not on the
# leaderboard payload. They are merged into the leaderboard rows by slug.
MODEL_PAGE_ONLY_FIELDS = (
    "briefcaseBreakdown",
    "briefcaseTotalCost",
    "enterpriseOpsGym",
    "apexAgents",
    "harveyLabCriteriaPass",
    "automationBenchPartialScore",
)


def fetch_rich_rows(url: str = AA_RSC_URL) -> list[dict[str, Any]]:
    """Full per-variant benchmark rows, merged from the leaderboard payload and
    a model detail page (which carries the Briefcase/Enterprise-Ops fields the
    leaderboard omits)."""
    stream = decode_rsc_stream(request_text(url))
    rows = extract_balanced_array(stream, "models", marker="terminalbenchV21")
    detail_slug = next(
        (
            str(row["slug"])
            for row in rows
            if row.get("slug") and not row.get("deprecated")
        ),
        None,
    )
    if detail_slug:
        detail_stream = decode_rsc_stream(
            request_text(f"{AA_MODEL_PAGE_BASE}{detail_slug}")
        )
        detail_rows = extract_balanced_array(
            detail_stream, "models", marker="terminalbenchV21"
        )
        detail_by_slug = {
            str(row["slug"]): row for row in detail_rows if row.get("slug")
        }
        for row in rows:
            detail = detail_by_slug.get(str(row.get("slug")))
            if not detail:
                continue
            for field in MODEL_PAGE_ONLY_FIELDS:
                if row.get(field) is None and detail.get(field) is not None:
                    row[field] = detail[field]
    return rows


def fetch_briefcase_rows(url: str = AA_BRIEFCASE_URL) -> list[dict[str, Any]]:
    """AA-Briefcase rows carrying the deep run telemetry (turns, tool calls).
    Artificial Analysis publishes these only for the models preselected on the
    Briefcase chart."""
    stream = decode_rsc_stream(request_text(url))
    return extract_balanced_array(stream, "initialModels")


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
    discovered_ids = {spec.copilot_id for spec in result}
    result.extend(
        by_id[model_id]
        for model_id in LIVE_PROBE_VERIFIED_MODEL_IDS
        if model_id not in discovered_ids
    )
    return (
        result,
        "copilot-models.list plus live-probed picker-only public models",
        omitted_count,
    )


def positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def runtime_measurement(
    model: dict[str, Any],
    rich: dict[str, Any] | None,
    api_key: str,
    rich_key: str,
) -> tuple[float | None, str | None]:
    api_value = metric_value(model.get(api_key))
    if positive_number(api_value):
        return api_value, "AA API"
    rich_value = metric_value((rich or {}).get(rich_key))
    if positive_number(rich_value):
        return rich_value, "AA public RSC"
    return api_value if api_value is not None else rich_value, None


def runtime_measurements(
    model: dict[str, Any],
    rich: dict[str, Any] | None,
) -> dict[str, tuple[float | None, str | None]]:
    return {
        "tok_s": runtime_measurement(
            model,
            rich,
            "median_output_tokens_per_second",
            "medianOutputTokensPerSecond",
        ),
        "ttft": runtime_measurement(
            model,
            rich,
            "median_time_to_first_token_seconds",
            "medianTimeToFirstTokenSeconds",
        ),
        "answer_ttft": runtime_measurement(
            model,
            rich,
            "median_time_to_first_answer_token",
            "medianTimeToFirstAnswerTokenSeconds",
        ),
    }


def valid_runtime(
    model: dict[str, Any],
    rich: dict[str, Any] | None = None,
) -> bool:
    runtime = runtime_measurements(model, rich)
    return positive_number(runtime["tok_s"][0]) and positive_number(runtime["ttft"][0])


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


def base_row(
    model: dict[str, Any],
    evaluation_keys: list[str],
    rich: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evaluations = model.get("evaluations") or {}
    pricing = model.get("pricing") or {}
    creator = model.get("model_creator") or {}
    runtime = runtime_measurements(model, rich)
    tok_s, tok_s_source = runtime["tok_s"]
    ttft, ttft_source = runtime["ttft"]
    answer_ttft, answer_ttft_source = runtime["answer_ttft"]
    metrics = {f"eval.{key}": metric_value(evaluations.get(key)) for key in evaluation_keys}
    metrics.update(
        {
            "metric.median_output_tokens_per_second": tok_s,
            "metric.median_time_to_first_token_seconds": ttft,
            "metric.median_time_to_first_answer_token": answer_ttft,
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
        "tok_s": tok_s,
        "ttft": ttft,
        "runtime_sources": {
            "output_tokens_per_second": tok_s_source,
            "time_to_first_token": ttft_source,
            "time_to_first_answer_token": answer_ttft_source,
        },
    }


def put_metric(metrics: dict[str, Any], key: str, value: Any) -> None:
    number = metric_value(value)
    if number is not None:
        metrics[key] = number


def fetch_official_copilot_ai_credit_prices() -> dict[str, tuple[float, float]]:
    """Read current default-tier prices from GitHub's official pricing table.

    The table publishes USD per 1M tokens. One USD equals 100 AI credits, so
    convert the first and last monetary cells in each model row to credits.
    """
    page = request_text(COPILOT_PRICING_URL)
    rows: dict[str, tuple[float, float]] = {}
    normalized_names = sorted(
        (
            (re.sub(r"\s+", " ", name).strip().lower(), model_id)
            for model_id, name in COPILOT_DOC_MODEL_NAMES.items()
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for match in re.finditer(r"<tr>(.*?)</tr>", page, re.DOTALL | re.IGNORECASE):
        row_html = match.group(1)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL | re.IGNORECASE)
        if not cells:
            continue
        model_name = html.unescape(re.sub(r"<[^>]+>", "", cells[0]))
        model_name = re.sub(r"\s+", " ", model_name).strip().lower()
        model_id = next(
            (
                model_id
                for expected_name, model_id in normalized_names
                if model_name.startswith(expected_name)
            ),
            None,
        )
        if not model_id or model_id in rows:
            continue
        dollar_values = [
            float(value.replace(",", ""))
            for value in re.findall(r"\$([0-9][0-9,]*(?:\.[0-9]+)?)", row_html)
        ]
        if len(dollar_values) >= 2:
            rows[model_id] = (dollar_values[0] * 100, dollar_values[-1] * 100)
    return rows


def copilot_ai_credit_prices(
    discovered: list[dict[str, Any]] | None,
    official_prices: dict[str, tuple[float, float]] | None = None,
) -> tuple[dict[str, tuple[float, float]], dict[str, str]]:
    """Return Copilot AI-credit prices per 1M input and output tokens."""
    prices: dict[str, tuple[float, float]] = {}
    sources: dict[str, str] = {}
    for model_id, price in (official_prices or {}).items():
        prices[model_id] = price
        sources[model_id] = "GitHub Copilot official pricing table"
    for model in discovered or []:
        model_id = model.get("id")
        token_prices = (model.get("billing") or {}).get("tokenPrices") or {}
        input_price = metric_value(token_prices.get("inputPrice"))
        output_price = metric_value(token_prices.get("outputPrice"))
        if model_id and positive_number(input_price) and positive_number(output_price):
            prices[str(model_id)] = (input_price, output_price)
            sources[str(model_id)] = "Copilot models.list billing.tokenPrices"
    return prices, sources


def enrich_copilot_cost(
    row: dict[str, Any],
    copilot_price: tuple[float, float],
    price_source: str = "Copilot models.list billing.tokenPrices",
) -> None:
    """Estimate task AI credits from AA's observed public-rate cost.

    Intelligence Index input/output components are scaled separately. Briefcase
    exposes only total cost, so it uses the blended-rate ratio. Neither estimate
    is an observed Copilot charge, and cache/billing differences can prevent
    exact proportionality.
    """
    metrics = row["metrics"]
    copilot_input, copilot_output = copilot_price
    aa_input = metric_value(metrics.get("price.price_1m_input_tokens"))
    aa_output = metric_value(metrics.get("price.price_1m_output_tokens"))
    metrics["price.copilot_ai_credits_1m_input_tokens"] = copilot_input
    metrics["price.copilot_ai_credits_1m_output_tokens"] = copilot_output
    metrics["price.copilot_ai_credits_blended_3_to_1"] = (
        3 * copilot_input + copilot_output
    ) / 4
    row["copilot_pricing_source"] = price_source
    if not positive_number(aa_input) or not positive_number(aa_output):
        return
    briefcase_cost = metric_value(metrics.get("briefcase.cost_total"))
    aa_blended = metric_value(metrics.get("price.price_1m_blended_3_to_1"))
    if briefcase_cost is not None and positive_number(aa_blended):
        metrics["copilot.briefcase_ai_credits_total"] = (
            briefcase_cost
            * metrics["price.copilot_ai_credits_blended_3_to_1"]
            / aa_blended
        )
    input_cost = metric_value(metrics.get("task.cost_input"))
    output_cost = metric_value(metrics.get("task.cost_output"))
    if input_cost is None or output_cost is None:
        return
    metrics["copilot.ai_credits_per_task"] = (
        input_cost * (copilot_input / aa_input)
        + output_cost * (copilot_output / aa_output)
    )


def enrich_rich(row: dict[str, Any], rich: dict[str, Any]) -> None:
    metrics = row["metrics"]
    tokens = rich.get("intelligenceIndexOutputTokensPerTask")
    if isinstance(tokens, dict):
        put_metric(metrics, "task.output_tokens_total", tokens.get("output"))
        put_metric(metrics, "task.output_tokens_reasoning", tokens.get("reasoning"))
        put_metric(metrics, "task.output_tokens_answer", tokens.get("answer"))
    put_metric(metrics, "task.decode_time_seconds", rich.get("intelligenceIndexTimePerTask"))
    task_time = metric_value(metrics.get("task.decode_time_seconds"))
    ttft = metric_value(row.get("ttft"))
    if positive_number(task_time) and positive_number(ttft):
        metrics["task.elapsed_proxy_seconds"] = task_time + ttft
    gdpval = rich.get("gdpvalBreakdown")
    if isinstance(gdpval, dict):
        put_metric(metrics, "rich.gdpval_v2", gdpval.get("elo"))
        put_metric(metrics, "rich.gdpval_turns_per_task", gdpval.get("avgTurns"))

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
        "agenticIndex": "rich.agentic_index",
        "gdpvalNormalized": "rich.gdpval_normalized",
        "terminalbenchV21": "rich.terminalbench_v2_1",
        "tauBanking": "rich.tau_banking",
        "critpt": "rich.critpt",
        "omniscience": "rich.omniscience",
        "mmmuPro": "rich.mmmu_pro",
        "apexAgents": "rich.apex_agents",
        "itbenchSre": "rich.it_bench_sre",
        "automationBenchPartialScore": "rich.automation_strict_score",
        "enterpriseOpsGym": "rich.enterprise_ops_success_rate",
        "harveyLabCriteriaPass": "rich.harvey_criteria_pass",
        "mlcrOverall": "rich.mlcr_overall",
    }.items():
        put_metric(metrics, target, rich.get(source))

    omniscience = rich.get("omniscienceBreakdown")
    if isinstance(omniscience, dict):
        put_metric(metrics, "rich.omniscience_accuracy", omniscience.get("accuracy"))
        put_metric(
            metrics,
            "rich.omniscience_hallucination_rate",
            omniscience.get("hallucinationRate"),
        )
    row["aa_rsc_enriched"] = True


def enrich_briefcase(row: dict[str, Any], rich: dict[str, Any]) -> None:
    """Briefcase Elo/telemetry. `rich` is either a leaderboard row carrying the
    merged `briefcaseBreakdown`, or a Briefcase-page row whose breakdown adds
    turn and tool-call telemetry."""
    briefcase = rich.get("briefcaseBreakdown")
    if not isinstance(briefcase, dict):
        return
    metrics = row["metrics"]
    # The model detail page nests the headline Elo under `overall`; the
    # Briefcase evaluation page puts it at the top level of the breakdown.
    overall = briefcase.get("overall")
    overall = overall if isinstance(overall, dict) else briefcase
    put_metric(metrics, "briefcase.elo", overall.get("elo"))
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
        total_turns = metric_value(turns.get("total"))
        tool_ms = metric_value(briefcase.get("totalToolMs"))
        tool_calls = metric_value(briefcase.get("totalToolCalls"))
        if positive_number(total_turns):
            if tool_calls is not None:
                metrics["briefcase.tool_calls_per_turn"] = tool_calls / total_turns
            if tool_ms is not None:
                metrics["briefcase.tool_time_per_turn_seconds"] = (
                    tool_ms / total_turns / 1000
                )
    put_metric(metrics, "briefcase.cost_total", rich.get("briefcaseTotalCost"))
    row["aa_briefcase_enriched"] = True


def build_combo(
    spec: ModelSpec,
    reasoning: str,
    candidates: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    evaluation_keys: list[str],
    missing_status: str,
    missing_coverage: str,
    rich_by_slug: dict[str, dict[str, Any]],
    copilot_prices: dict[str, tuple[float, float]],
    copilot_price_sources: dict[str, str],
) -> dict[str, Any]:
    def rich_row(model: dict[str, Any]) -> dict[str, Any] | None:
        return rich_by_slug.get(str(model.get("slug") or ""))

    valid_matches = [model for model in matches if valid_runtime(model, rich_row(model))]
    model = valid_matches[0] if valid_matches else None
    if model:
        rich = rich_row(model)
        runtime = runtime_measurements(model, rich)
        rsc_fields = [
            label
            for label, key in (
                ("output throughput", "tok_s"),
                ("time to first token", "ttft"),
            )
            if runtime[key][1] == "AA public RSC"
        ]
        status = (
            f"Tracked; {', '.join(rsc_fields)} recovered from AA public RSC "
            "because the AA API value was nonpositive"
            if rsc_fields
            else "Tracked"
        )
        coverage = "tracked"
    elif matches:
        measurements = []
        for candidate in matches:
            runtime = runtime_measurements(candidate, rich_row(candidate))
            measurements.append(
                f"{candidate.get('name')}: "
                f"output tokens/sec={runtime['tok_s'][0]!r}, "
                f"TTFT={runtime['ttft'][0]!r}"
            )
        status = "AA row has invalid runtime measurements: " + "; ".join(measurements)
        coverage = "invalid_runtime"
    else:
        status = missing_status
        coverage = missing_coverage
    rich = rich_row(model) if model else None
    row = base_row(model, evaluation_keys, rich) if model else None
    if row and row.get("slug") in rich_by_slug:
        rich = rich_by_slug[row["slug"]]
        enrich_rich(row, rich)
        enrich_briefcase(row, rich)
    if row and spec.copilot_id in copilot_prices:
        enrich_copilot_cost(
            row,
            copilot_prices[spec.copilot_id],
            copilot_price_sources[spec.copilot_id],
        )
    return {
        "copilot_id": spec.copilot_id,
        "reasoning": reasoning,
        "tracked": row is not None,
        "coverage": coverage,
        "status": status,
        "candidate_names": [candidate.get("name") for candidate in candidates],
        "row": row,
    }


def build_combos(
    models: list[dict[str, Any]],
    rich_rows: list[dict[str, Any]],
    briefcase_rows: list[dict[str, Any]],
    specs: list[ModelSpec],
    copilot_prices: dict[str, tuple[float, float]],
    copilot_price_sources: dict[str, str],
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
                        "distinct_mode",
                        rich_by_slug,
                        copilot_prices,
                        copilot_price_sources,
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
                        "effort_unknown",
                        rich_by_slug,
                        copilot_prices,
                        copilot_price_sources,
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
                    "no_row",
                    rich_by_slug,
                    copilot_prices,
                    copilot_price_sources,
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
                    "no_row",
                    rich_by_slug,
                    copilot_prices,
                    copilot_price_sources,
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
                    "effort_missing" if candidates else "no_row",
                    rich_by_slug,
                    copilot_prices,
                    copilot_price_sources,
                )
            )
    for combo in combos:
        row = combo.get("row")
        if row and row.get("slug") in briefcase_by_slug:
            enrich_briefcase(row, briefcase_by_slug[row["slug"]])
        if row and combo["copilot_id"] in copilot_prices:
            enrich_copilot_cost(
                row,
                copilot_prices[combo["copilot_id"]],
                copilot_price_sources[combo["copilot_id"]],
            )
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
        metric_def(
            "price.copilot_ai_credits_blended_3_to_1",
            "Blended AI credits / 1M tokens (Copilot rates, 3:1)",
            higher_better=False,
            group="Pricing",
            unit="AI credits",
            source="Copilot models.list or GitHub Copilot official pricing table",
        ),
    ]
    for key, label, unit in (
        ("task.decode_time_seconds", "Intelligence Index decode time per task", "seconds"),
        (
            "task.elapsed_proxy_seconds",
            "Intelligence Index elapsed proxy per task",
            "seconds",
        ),
        ("task.cost_total", "Intelligence Index cost per task", "USD"),
        (
            "copilot.ai_credits_per_task",
            "Intelligence Index AI credits per task (estimated)",
            "AI credits",
        ),
        ("rich.gdpval_turns_per_task", "GDPval-AA turns per task", "turns"),
        ("briefcase.turns_per_task", "AA-Briefcase turns per task", "turns"),
        ("briefcase.cost_total", "AA-Briefcase total run cost", "USD"),
        (
            "copilot.briefcase_ai_credits_total",
            "AA-Briefcase AI credits per run (estimated)",
            "AI credits",
        ),
    ):
        if populated(key):
            if key.startswith("briefcase."):
                source = "AA-Briefcase public RSC"
            elif key.startswith("copilot."):
                source = "AA public RSC task cost rescaled to Copilot token rates"
            else:
                source = "AA public RSC"
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
    generic_speed = [
        "metric.median_output_tokens_per_second",
        "metric.median_time_to_first_token_seconds",
    ]
    generic_cost = [
        "price.copilot_ai_credits_blended_3_to_1",
        "price.price_1m_blended_3_to_1",
    ]
    intelligence = [
        "task.decode_time_seconds",
        "task.elapsed_proxy_seconds",
        "copilot.ai_credits_per_task",
        "task.cost_total",
    ]
    briefcase = [
        "briefcase.turns_per_task",
        "copilot.briefcase_ai_credits_total",
        "briefcase.cost_total",
    ]
    pairs = {
        "eval.artificial_analysis_coding_index": (
            generic_speed + ["task.elapsed_proxy_seconds"] + generic_cost
        ),
        "eval.artificial_analysis_intelligence_index": intelligence,
        "eval.ifbench": generic_speed + generic_cost,
        "rich.agentic_index": (
            generic_speed + ["task.elapsed_proxy_seconds"] + generic_cost
        ),
        "rich.terminalbench_v2_1": (
            generic_speed + ["task.elapsed_proxy_seconds"] + generic_cost
        ),
        "rich.gdpval_v2": ["rich.gdpval_turns_per_task"] + generic_cost,
        "rich.omniscience": generic_speed + generic_cost,
        "rich.mmmu_pro": (
            generic_speed + ["task.elapsed_proxy_seconds"] + generic_cost
        ),
        "rich.enterprise_ops_success_rate": generic_speed + generic_cost,
        "briefcase.elo": briefcase,
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
    # Discovery is also the only source of Copilot's billed token prices, so
    # attempt it even when the caller did not ask to refresh the model registry.
    try:
        discovered = discover_copilot_models()
    except Exception as error:
        discovery_error = str(error)
    specs, registry_source, omitted_unrecognized_model_count = effective_specs(
        discovered if discover_models else None
    )
    official_pricing_error = None
    official_prices: dict[str, tuple[float, float]] = {}
    try:
        official_prices = fetch_official_copilot_ai_credit_prices()
    except Exception as error:
        official_pricing_error = str(error)
    copilot_prices, copilot_price_sources = copilot_ai_credit_prices(
        discovered,
        official_prices,
    )
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
            briefcase_rows = fetch_briefcase_rows()
        except Exception as error:
            briefcase_error = str(error)
    combos, evaluation_keys = build_combos(
        aa_models,
        rich_rows,
        briefcase_rows,
        specs,
        copilot_prices,
        copilot_price_sources,
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
                "billed_price_models": len(copilot_prices),
                "official_pricing_url": COPILOT_PRICING_URL,
                "official_pricing_error": official_pricing_error,
                "live_price_models": sum(
                    source.startswith("Copilot models.list")
                    for source in copilot_price_sources.values()
                ),
                "official_fallback_price_models": sum(
                    source.startswith("GitHub Copilot official")
                    for source in copilot_price_sources.values()
                ),
            },
        },
        "model_matrix": [
            {"copilot_id": spec.copilot_id, "reasoning_levels": list(spec.efforts)}
            for spec in specs
        ],
        "quality_metrics": quality_metrics,
        "operational_metrics": operational_metrics,
        "metric_pairs": metric_pairs(quality_metrics, operational_metrics),
        "speed_metric_keys": [
            metric["key"]
            for metric in operational_metrics
            if "cost" not in metric["key"]
            and "ai_credits" not in metric["key"]
            and not metric["key"].startswith("price.")
        ],
        "cost_metric_keys": [
            metric["key"]
            for metric in operational_metrics
            if "cost" in metric["key"]
            or "ai_credits" in metric["key"]
            or metric["key"].startswith("price.")
        ],
        "combos": combos,
        "notes": [
            "AA API rows are matched by exact model family and exact effort labels.",
            "Claude reasoning levels match only Adaptive Reasoning rows.",
            "Unqualified AA rows are shown under none / unknown effort.",
            "Distinct Copilot serving modes such as Opus Fast are not assigned standard-model runtime measurements.",
            "Positive AA API runtime measurements are preferred; nonpositive API placeholders fall back to the same slug's AA public RSC measurements.",
            "Rows whose runtime measurements remain missing or nonpositive after the RSC fallback are not plotted.",
            "AA time per task is weighted decode time and excludes TTFT and request overhead.",
            "The task elapsed proxy adds median TTFT to AA Intelligence Index decode time; it is not measured separately for each quality benchmark.",
            "AA-Briefcase task duration, turns, tool calls, and cost use the benchmark's own observed task runs.",
            "AA-Briefcase cost per task is provider list-price cost observed by AA, not Copilot premium-request billing.",
            "Copilot Briefcase AI credits are estimated using the model's blended 3:1 price ratio because AA does not publish the Briefcase token mix.",
            "Estimated task AI credits are counterfactual; observed CAPI total_nano_aiu remains authoritative for completed calls.",
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
*{box-sizing:border-box}body{margin:0;background:var(--cp-bg);color:var(--cp-text);font-family:"Segoe UI",Aptos,Calibri,-apple-system,BlinkMacSystemFont,sans-serif}main{max-width:1400px;margin:auto;padding:32px}h1{margin:0 0 8px;font-size:28px}h2{margin:0 0 16px;font-size:20px}p{color:var(--cp-text-muted);line-height:1.5}.card{background:var(--cp-surface);border:1px solid var(--cp-border);border-radius:16px;box-shadow:0 0 2px var(--cp-border),0 1px 2px var(--cp-border);padding:20px;margin:20px 0}.toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:16px}label{color:var(--cp-text-muted);font-size:13px}select,input{background:var(--cp-surface-soft);color:var(--cp-text);border:1px solid var(--cp-border);border-radius:.625rem;padding:8px 10px;font:inherit;max-width:390px}.tradeoff-control{display:flex;align-items:center;gap:8px;min-width:330px}.tradeoff-control[hidden]{display:none}.tradeoff-control input{width:180px;padding:0}.tradeoff-control output{min-width:100px;color:var(--cp-text);font-weight:600}.checkbox-control{display:flex;align-items:center;gap:6px}.checkbox-control input{margin:0}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-top:16px}.stat{background:var(--cp-surface-soft);border:1px solid var(--cp-border);border-radius:.625rem;padding:12px}.stat strong{display:block;font-size:24px}.stat span{color:var(--cp-text-muted);font-size:13px}.chart-wrap,.table-wrap{overflow:auto}svg{width:100%;min-width:860px;height:590px;background:var(--cp-surface-soft);border:1px solid var(--cp-border);border-radius:.625rem}.axis,.tick{fill:var(--cp-text-muted);font-size:12px}.grid,.axis-line{stroke:var(--cp-border)}.point{fill:var(--cp-link);stroke:var(--cp-surface);stroke-width:2;opacity:.88}.point.two-axis-frontier{fill:var(--cp-accent);stroke:var(--cp-accent-fg);stroke-width:3;opacity:1}.point.three-axis-only{fill:var(--cp-warning);stroke:var(--cp-accent-fg);stroke-width:3;opacity:1}.frontier-line{fill:none;stroke:var(--cp-accent);stroke-width:2;stroke-dasharray:5 5;opacity:.8}.legend,.matrix-legend{display:flex;flex-wrap:wrap;gap:14px;color:var(--cp-text-muted);font-size:13px;margin-top:10px}.legend i,.matrix-dot{display:inline-block;width:14px;height:14px;border-radius:999px;margin-right:5px;vertical-align:-2px;background:var(--cp-link);border:2px solid var(--cp-border)}.legend .frontier-key i{background:var(--cp-accent)}.legend .three-axis-key i{background:var(--cp-warning)}table{width:100%;border-collapse:collapse;min-width:850px}th,td{border-bottom:1px solid var(--cp-border);padding:9px;text-align:center}th{position:sticky;top:0;background:var(--cp-surface-soft);z-index:1}th:first-child,td:first-child{text-align:left;position:sticky;left:0;background:var(--cp-surface);z-index:2}th:first-child{background:var(--cp-surface-soft);z-index:3}.matrix-dot{width:18px;height:18px;margin:0;cursor:help}.matrix-dot.yes{background:var(--cp-success);border-color:var(--cp-success)}.matrix-dot.partial{background:var(--cp-warning);border-color:var(--cp-warning)}.matrix-dot.invalid{background:var(--cp-danger);border-color:var(--cp-danger)}.matrix-dot.no{background:var(--cp-text-muted);border-color:var(--cp-text-muted)}.matrix-dot.blank{background:var(--cp-surface);cursor:default}code{font-family:Consolas,"Courier New",Courier,monospace;background:var(--cp-surface-soft);border:1px solid var(--cp-border);border-radius:.625rem;padding:1px 5px}.tooltip{position:fixed;display:none;pointer-events:none;background:var(--cp-panel-strong);color:var(--cp-text);border:1px solid var(--cp-border-strong);border-radius:.625rem;padding:10px 12px;box-shadow:var(--cp-shadow);max-width:440px;font-size:13px;z-index:10}.muted{color:var(--cp-text-muted)}
</style>
</head>
<body><main>
<h1>Copilot model Pareto explorer for Artificial Analysis</h1>
<p id="subtitle"></p>
<section class="stats" id="stats"></section>
<section class="card">
<h2>Pareto chart</h2>
<div class="toolbar">
<label>Quality metric <select id="yMetric"></select></label>
<label>Speed metric <select id="xMetric"></select></label>
<label>Cost metric <select id="costMetric"></select></label>
<label>Family <select id="family"><option value="all">All</option></select></label>
</div>
<div class="toolbar">
<label>X-axis <select id="xMode"><option value="speed">Speed</option><option value="cost">Cost</option><option value="blend">Speed/cost blend</option></select></label>
<label class="checkbox-control"><input id="frontierOnly" type="checkbox">Show only Pareto frontier</label>
<label class="tradeoff-control" id="tradeoffControl" hidden>Blend
<span>Speed</span><input id="tradeoff" type="range" min="0" max="100" value="50"><span>Cost</span>
<output id="tradeoffLabel">Balanced</output></label>
</div>
<div class="chart-wrap"><svg id="chart" role="img" aria-label="Pareto scatter chart"></svg></div>
<div class="legend"><span><i></i>Tracked row</span><span class="frontier-key"><i></i>Two-axis frontier and dashed projection curve</span><span class="three-axis-key"><i></i>Three-axis frontier only</span><span>Circle Claude · square GPT · diamond Gemini · hexagon Grok · triangle other</span><span>Three-axis frontier uses the selected quality, speed, and cost metrics</span></div>
</section>
<section class="card">
<h2>Coverage matrix</h2>
<div class="toolbar"><label>Search <input id="search" placeholder="model or AA row"></label></div>
<div class="table-wrap"><table id="matrix"></table></div>
<div class="matrix-legend"><span><i class="matrix-dot yes"></i>Tracked</span><span><i class="matrix-dot invalid"></i>Invalid runtime after fallback</span><span><i class="matrix-dot partial"></i>Model exists, level missing or unmatched mode</span><span><i class="matrix-dot no"></i>No AA row</span><span><i class="matrix-dot blank"></i>Not exposed</span></div>
</section>
<section class="card"><h2>Provenance and notes</h2><div id="provenance"></div></section>
</main><div class="tooltip" id="tooltip"></div>
<script id="report-data" type="application/json">__REPORT_DATA__</script>
<script>
const DATA=JSON.parse(document.getElementById('report-data').textContent);
const xMetric=document.getElementById('xMetric'),yMetric=document.getElementById('yMetric'),costMetric=document.getElementById('costMetric'),xMode=document.getElementById('xMode'),family=document.getElementById('family'),tradeoffControl=document.getElementById('tradeoffControl'),tradeoff=document.getElementById('tradeoff'),tradeoffLabel=document.getElementById('tradeoffLabel'),frontierOnly=document.getElementById('frontierOnly'),search=document.getElementById('search'),tooltip=document.getElementById('tooltip');
const metricMap=new Map([...DATA.operational_metrics,...DATA.quality_metrics].map(m=>[m.key,m]));
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function css(n){return getComputedStyle(document.documentElement).getPropertyValue(n).trim()}
function fmt(v,d){if(v==null||!Number.isFinite(Number(v)))return'—';const n=Number(v),digits=d??(Math.abs(n)>0&&Math.abs(n)<2?3:1),s=n.toFixed(digits);return s.includes('.')?s.replace(/0+$/,'').replace(/\.$/,''):s}
function meta(k){return metricMap.get(k)||{label:k,higherBetter:true}}
function valid(k,v){if(v==null||v==='')return false;const n=Number(v);if(!Number.isFinite(n)||n<0)return false;if(k.startsWith('eval.artificial_analysis_')||k.includes('time_to_')||k==='metric.median_output_tokens_per_second')return n>0;return true}
function rows(){const f=family.value,x=xMetric.value,y=yMetric.value,cost=costMetric.value;return DATA.combos.filter(c=>c.tracked&&c.row&&Number(c.row.metrics['metric.median_output_tokens_per_second'])>0&&valid(x,c.row.metrics[x])&&valid(y,c.row.metrics[y])&&valid(cost,c.row.metrics[cost])&&(f==='all'||c.copilot_id.includes(f)))}
function dominates(a,b,x,y,cost){const ax=+a.row.metrics[x],bx=+b.row.metrics[x],ay=+a.row.metrics[y],by=+b.row.metrics[y],ac=+a.row.metrics[cost],bc=+b.row.metrics[cost],xm=meta(x).higherBetter!==false,ym=meta(y).higherBetter!==false;const xok=xm?ax>=bx:ax<=bx,yok=ym?ay>=by:ay<=by,xs=xm?ax>bx:ax<bx,ys=ym?ay>by:ay<by;return xok&&yok&&ac<=bc&&(xs||ys||ac<bc)}
function pareto(rs,x,y,cost){return rs.filter(a=>!rs.some(b=>a!==b&&dominates(b,a,x,y,cost)))}
function pareto2d(points,xHigher,yHigher){return points.filter(a=>!points.some(b=>a!==b&&(xHigher?b.xv>=a.xv:b.xv<=a.xv)&&(yHigher?b.yv>=a.yv:b.yv<=a.yv)&&((xHigher?b.xv>a.xv:b.xv<a.xv)||(yHigher?b.yv>a.yv:b.yv<a.yv))))}
function scale(v,min,max,a,b){return max===min?(a+b)/2:a+(v-min)*(b-a)/(max-min)}
function normalized(v,min,max,higher){if(max===min)return 1;const n=higher?(v-min)/(max-min):(max-v)/(max-min);return .05+.95*Math.max(0,Math.min(1,n))}
function projectedX(rows,c,x,cost){if(xMode.value==='speed')return+c.row.metrics[x];if(xMode.value==='cost')return+c.row.metrics[cost];const blend=Number(tradeoff.value)/100,xs=rows.map(r=>+r.row.metrics[x]),cs=rows.map(r=>+r.row.metrics[cost]),speed=normalized(+c.row.metrics[x],Math.min(...xs),Math.max(...xs),meta(x).higherBetter!==false),cheap=normalized(+c.row.metrics[cost],Math.min(...cs),Math.max(...cs),false);return speed**(1-blend)*cheap**blend}
function projectedMeta(){if(xMode.value==='speed')return meta(xMetric.value);if(xMode.value==='cost')return meta(costMetric.value);return{label:`Normalized efficiency (${tradeoffText()})`,higherBetter:true}}
function tradeoffText(){const cost=Number(tradeoff.value),speed=100-cost;return cost===50?'Balanced':`${speed}% speed / ${cost}% cost`}
function quantile(values,p){const s=[...values].sort((a,b)=>a-b),i=(s.length-1)*p,l=Math.floor(i),u=Math.ceil(i);return l===u?s[l]:s[l]+(s[u]-s[l])*(i-l)}
function outliers(points,key,higher){if(points.length<4)return new Set;const vals=points.map(p=>p[key]),q1=quantile(vals,.25),q3=quantile(vals,.75),iqr=q3-q1;if(!(iqr>0))return new Set;const fence=higher?q1-1.5*iqr:q3+1.5*iqr;return new Set(points.filter(p=>!p.front&&(higher?p[key]<fence:p[key]>fence)))}
function niceStep(span,n=5){const rough=span/Math.max(1,n),power=10**Math.floor(Math.log10(rough)),z=rough/power,f=z>=7.5?10:z>=3.5?5:z>=1.5?2:1;return f*power}
function niceAxis(vals){const rawMin=Math.min(...vals),rawMax=Math.max(...vals),span=rawMax-rawMin,fallback=Math.max(Math.abs(rawMax)*.1,.01),step=niceStep(span>0?span*1.1:fallback),pmin=span>0?rawMin-span*.05:rawMin-fallback*.5,pmax=span>0?rawMax+span*.05:rawMax+fallback*.5,min=Math.max(0,Math.floor(pmin/step)*step),max=Math.max(min+step,Math.ceil(pmax/step)*step),count=Math.round((max-min)/step);return{min,max,step,ticks:Array.from({length:count+1},(_,i)=>Number((min+i*step).toPrecision(14)))}}
function tick(v,step){const d=Math.max(0,-Math.floor(Math.log10(Math.abs(step)))),s=Number(v).toFixed(d);return s.includes('.')?s.replace(/0+$/,'').replace(/\.$/,''):s}
function shape(kind,x,y,r,frontierClass){const ns='http://www.w3.org/2000/svg';let n;if(kind==='claude'){n=document.createElementNS(ns,'circle');n.setAttribute('cx',x);n.setAttribute('cy',y);n.setAttribute('r',r)}else if(kind==='gpt'){n=document.createElementNS(ns,'rect');n.setAttribute('x',x-r);n.setAttribute('y',y-r);n.setAttribute('width',r*2);n.setAttribute('height',r*2);n.setAttribute('rx',2)}else if(kind==='gemini'){n=document.createElementNS(ns,'polygon');n.setAttribute('points',`${x},${y-r} ${x+r},${y} ${x},${y+r} ${x-r},${y}`)}else if(kind==='grok'){const points=Array.from({length:6},(_,i)=>{const a=Math.PI/3*i-Math.PI/6;return`${x+r*Math.cos(a)},${y+r*Math.sin(a)}`}).join(' ');n=document.createElementNS(ns,'polygon');n.setAttribute('points',points)}else{n=document.createElementNS(ns,'polygon');n.setAttribute('points',`${x},${y-r} ${x+r},${y+r} ${x-r},${y+r}`)}n.setAttribute('class','point'+(frontierClass?' '+frontierClass:''));return n}
function kind(id){return id.includes('claude')?'claude':id.includes('gpt')?'gpt':id.includes('gemini')?'gemini':id.includes('grok')?'grok':'other'}
function overlap(a,b){return!(a.x+a.w<b.x||b.x+b.w<a.x||a.y+a.h<b.y||b.y+b.h<a.y)}
function labelPos(text,x,y,used,right,top,bottom){const w=Math.max(56,text.length*6.2),tries=[[10,-10],[10,15],[-w-8,-10],[-w-8,15],[10,-26],[10,31]];for(const[dX,dY]of tries){const px=Math.max(82,Math.min(x+dX,right-w)),py=Math.max(top+14,Math.min(y+dY,bottom-4)),box={x:px,y:py-12,w,h:15};if(!used.some(u=>overlap(u,box))){used.push(box);return{x:px,y:py}}}return{x:Math.min(x+10,right-w),y:Math.min(y+15,bottom-4)}}
function showTip(text,e){tooltip.style.display='block';tooltip.style.left=e.clientX+12+'px';tooltip.style.top=e.clientY+12+'px';tooltip.innerHTML=text.split('\n').map(esc).join('<br>')}
function renderChart(){
 const svg=document.getElementById('chart'),xKey=xMetric.value,yKey=yMetric.value,costKey=costMetric.value,allRows=rows(),front3=pareto(allRows,xKey,yKey,costKey),front3Keys=new Set(front3.map(c=>c.copilot_id+'|'+c.reasoning)),xMeta=projectedMeta(),allProjected=allRows.map(c=>({c,xv:projectedX(allRows,c,xKey,costKey),yv:+c.row.metrics[yKey]})),front2=pareto2d(allProjected,xMeta.higherBetter!==false,meta(yKey).higherBetter!==false),front2Keys=new Set(front2.map(p=>p.c.copilot_id+'|'+p.c.reasoning)),visibleKeys=new Set([...front2Keys,...front3Keys]),projected=frontierOnly.checked?allProjected.filter(p=>visibleKeys.has(p.c.copilot_id+'|'+p.c.reasoning)):allProjected,W=1120,H=590,L=78,R=32,T=32,B=86,PR=W-R,PB=H-B;
 tradeoffControl.hidden=xMode.value!=='blend';tradeoffLabel.value=tradeoffText();
 svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.innerHTML='';if(!projected.length){svg.innerHTML=`<text x="${W/2}" y="${H/2}" text-anchor="middle" fill="${css('--cp-text-muted')}">No valid rows for this selection.</text>`;return}
 const pts=projected.map(p=>({...p,twoAxis:front2Keys.has(p.c.copilot_id+'|'+p.c.reasoning),threeAxis:front3Keys.has(p.c.copilot_id+'|'+p.c.reasoning)})),xo=outliers(pts,'xv',xMeta.higherBetter!==false),yo=outliers(pts,'yv',meta(yKey).higherBetter!==false),hasX=xo.size>0,hasY=yo.size>0,OL=PR-82,OT=PB-62,MR=hasX?OL-10:PR,MB=hasY?OT-10:PB,xA=niceAxis(pts.filter(p=>!xo.has(p)).map(p=>p.xv)),yA=niceAxis(pts.filter(p=>!yo.has(p)).map(p=>p.yv)),xS=v=>xMeta.higherBetter!==false?scale(v,xA.min,xA.max,MR,L):scale(v,xA.min,xA.max,L,MR),yS=v=>meta(yKey).higherBetter!==false?scale(v,yA.min,yA.max,MB,T):scale(v,yA.min,yA.max,T,MB);
 pts.forEach(p=>{p.x=xo.has(p)?OL+42:xS(p.xv);p.y=yo.has(p)?OT+32:yS(p.yv)});pts.filter(p=>xo.has(p)&&yo.has(p)).forEach((p,i)=>{p.x=OL+22+(i%3)*18;p.y=Math.min(PB-12,OT+26+Math.floor(i/3)*16)});
 if(hasX)svg.insertAdjacentHTML('beforeend',`<rect x="${OL}" y="${T}" width="${PR-OL}" height="${PB-T}" fill="${css('--cp-highlight')}" stroke="${css('--cp-border')}"/><text class="axis" x="${OL+6}" y="${T+16}">X outliers</text>`);
 if(hasY)svg.insertAdjacentHTML('beforeend',`<rect x="${L}" y="${OT}" width="${PR-L}" height="${PB-OT}" fill="${css('--cp-highlight')}" stroke="${css('--cp-border')}"/><text class="axis" x="${L+8}" y="${OT+16}">Y outliers</text>`);
 xA.ticks.forEach(v=>{const x=xS(v);svg.insertAdjacentHTML('beforeend',`<line class="grid" x1="${x}" x2="${x}" y1="${T}" y2="${MB}"/><text class="tick x-tick" x="${x}" y="${PB+24}" text-anchor="middle">${tick(v,xA.step)}</text>`)});
 yA.ticks.forEach(v=>{const y=yS(v);svg.insertAdjacentHTML('beforeend',`<line class="grid" x1="${L}" x2="${MR}" y1="${y}" y2="${y}"/><text class="tick y-tick" x="${L-10}" y="${y+4}" text-anchor="end">${tick(v,yA.step)}</text>`)});
 svg.insertAdjacentHTML('beforeend',`<line class="axis-line" x1="${L}" x2="${PR}" y1="${PB}" y2="${PB}"/><line class="axis-line" x1="${L}" x2="${L}" y1="${T}" y2="${PB}"/><text class="axis" x="${(L+MR)/2}" y="${H-30}" text-anchor="middle">${esc(xMeta.label)} (${xMeta.higherBetter!==false?'higher':'lower'} is better; better is left)</text><text class="axis" transform="translate(18 ${(T+MB)/2}) rotate(-90)" text-anchor="middle">${esc(meta(yKey).label)} (${meta(yKey).higherBetter!==false?'higher':'lower'} is better; better is up)</text><text class="axis" x="${L+8}" y="${T+18}">best quadrant</text>`);
 const frontierPts=pts.filter(p=>p.twoAxis).sort((a,b)=>a.x-b.x||a.y-b.y);if(frontierPts.length>1){const line=document.createElementNS('http://www.w3.org/2000/svg','polyline');line.setAttribute('class','frontier-line');line.setAttribute('points',frontierPts.map(p=>`${p.x},${p.y}`).join(' '));svg.appendChild(line)}
 const used=[{x:L+4,y:T+2,w:96,h:20},...pts.map(p=>({x:p.x-8,y:p.y-8,w:16,h:16}))];
 pts.forEach(p=>{const c=p.c,row=c.row,frontierClass=p.twoAxis?'two-axis-frontier':p.threeAxis?'three-axis-only':'',frontierText=p.twoAxis?'\nTwo-axis frontier'+(p.threeAxis?' and three-axis frontier':''):p.threeAxis?'\nThree-axis frontier only':'',title=`${c.copilot_id} / ${c.reasoning}${frontierText}\n${row.name}\n${xMeta.label}: ${fmt(p.xv)}${xo.has(p)?' (X outlier)':''}\n${meta(xKey).label}: ${fmt(row.metrics[xKey])}\n${meta(yKey).label}: ${fmt(p.yv)}${yo.has(p)?' (Y outlier)':''}\n${meta(costKey).label}: ${fmt(row.metrics[costKey])}` ,n=shape(kind(c.copilot_id),p.x,p.y,(p.twoAxis||p.threeAxis)?7:5,frontierClass);n.addEventListener('mousemove',e=>showTip(title,e));n.addEventListener('mouseleave',()=>tooltip.style.display='none');svg.appendChild(n);if(!p.twoAxis&&!p.threeAxis)return;const text=c.copilot_id+' '+(c.reasoning==='not supported'?'unknown':c.reasoning),pos=labelPos(text,p.x,p.y,used,MR,T,MB),line=document.createElementNS('http://www.w3.org/2000/svg','line');line.setAttribute('x1',p.x);line.setAttribute('y1',p.y);line.setAttribute('x2',pos.x);line.setAttribute('y2',pos.y-5);line.setAttribute('stroke',css('--cp-border-strong'));svg.appendChild(line);const label=document.createElementNS('http://www.w3.org/2000/svg','text');label.setAttribute('x',pos.x);label.setAttribute('y',pos.y);label.setAttribute('fill',css('--cp-text'));label.setAttribute('font-size','11');label.textContent=text;svg.appendChild(label)})
}
function dot(c){if(!c)return'blank';if(c.coverage==='tracked'||c.tracked)return'yes';if(c.coverage==='invalid_runtime')return'invalid';if(c.coverage==='no_row')return'no';return'partial'}
function renderMatrix(){const levels=['not supported',...new Set(DATA.model_matrix.flatMap(m=>m.reasoning_levels))],labels={'not supported':'none / unknown'},q=search.value.toLowerCase(),models=DATA.model_matrix.filter(m=>!q||m.copilot_id.toLowerCase().includes(q)||DATA.combos.filter(c=>c.copilot_id===m.copilot_id).some(c=>(c.row?.name||'').toLowerCase().includes(q))),map=new Map(DATA.combos.map(c=>[c.copilot_id+'|'+c.reasoning,c]));document.getElementById('matrix').innerHTML=`<thead><tr><th>Model</th>${levels.map(l=>`<th>${labels[l]||l}</th>`).join('')}</tr></thead><tbody>${models.map(m=>`<tr><td><code>${m.copilot_id}</code></td>${levels.map(l=>{const c=map.get(m.copilot_id+'|'+l),tip=c?`${c.status}${c.row?'\n'+c.row.name:''}`:'';return`<td><span class="matrix-dot ${dot(c)}" data-tip="${esc(tip)}"></span></td>`}).join('')}</tr>`).join('')}</tbody>`;document.querySelectorAll('#matrix [data-tip]').forEach(n=>{if(!n.dataset.tip)return;n.addEventListener('mousemove',e=>showTip(n.dataset.tip,e));n.addEventListener('mouseleave',()=>tooltip.style.display='none')})}
function populateOperationalMetrics(){const allowed=new Set(DATA.metric_pairs[yMetric.value]||[]),speedCurrent=xMetric.value,costCurrent=costMetric.value,speed=DATA.operational_metrics.filter(m=>allowed.has(m.key)&&DATA.speed_metric_keys.includes(m.key)),cost=DATA.operational_metrics.filter(m=>allowed.has(m.key)&&DATA.cost_metric_keys.includes(m.key));xMetric.innerHTML=speed.map(m=>`<option value="${m.key}">${esc(m.label)}</option>`).join('');costMetric.innerHTML=cost.map(m=>`<option value="${m.key}">${esc(m.label)}</option>`).join('');xMetric.value=speed.some(m=>m.key===speedCurrent)?speedCurrent:(speed[0]?.key||'');costMetric.value=cost.some(m=>m.key===costCurrent)?costCurrent:(cost[0]?.key||'')}
function setup(){yMetric.innerHTML=DATA.quality_metrics.map(m=>`<option value="${m.key}">${esc(m.label)}</option>`).join('');yMetric.value=DATA.quality_metrics.some(m=>m.key==='eval.artificial_analysis_coding_index')?'eval.artificial_analysis_coding_index':DATA.quality_metrics[0].key;populateOperationalMetrics();const families=[...new Set(DATA.model_matrix.map(m=>m.copilot_id.split('-')[0]))];family.insertAdjacentHTML('beforeend',families.map(f=>`<option value="${f}">${f[0].toUpperCase()+f.slice(1)}</option>`).join(''));const tracked=DATA.combos.filter(c=>c.tracked).length,partial=DATA.combos.filter(c=>!c.tracked&&c.candidate_names.length).length,briefcase=DATA.combos.filter(c=>c.row?.metrics?.['briefcase.elo']>0).length;document.getElementById('stats').innerHTML=`<div class="stat"><strong>${DATA.combos.length}</strong><span>model/reasoning combinations</span></div><div class="stat"><strong>${tracked}</strong><span>tracked rows</span></div><div class="stat"><strong>${briefcase}</strong><span>AA-Briefcase rows</span></div><div class="stat"><strong>${partial}</strong><span>model exists, effort missing</span></div><div class="stat"><strong>${DATA.quality_metrics.length}</strong><span>curated quality metrics</span></div><div class="stat"><strong>${DATA.operational_metrics.length}</strong><span>relevant efficiency metrics</span></div>`;document.getElementById('subtitle').textContent=`Generated ${DATA.generated_at}. ${DATA.attribution}`;const brief=DATA.sources.aa_briefcase_rsc;document.getElementById('provenance').innerHTML=`<p><strong>Copilot registry:</strong> ${esc(DATA.sources.copilot_registry.source)}${DATA.sources.copilot_registry.error?' — fallback: '+esc(DATA.sources.copilot_registry.error):''}</p><p><strong>AA API:</strong> ${DATA.sources.aa_api.rows} rows. <strong>AA Intelligence RSC:</strong> ${DATA.sources.aa_rsc.rows} rich rows. <strong>AA-Briefcase RSC:</strong> ${brief?.rows??0} rows${brief?.error?' — '+esc(brief.error):''}.</p><ul>${DATA.notes.map(n=>`<li>${esc(n)}</li>`).join('')}</ul>`;renderMatrix();renderChart()}
xMetric.addEventListener('change',renderChart);costMetric.addEventListener('change',renderChart);yMetric.addEventListener('change',()=>{populateOperationalMetrics();renderChart()});xMode.addEventListener('change',renderChart);family.addEventListener('change',renderChart);tradeoff.addEventListener('input',renderChart);frontierOnly.addEventListener('change',renderChart);search.addEventListener('input',renderMatrix);setup();
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
