---
name: litellm-copilot
description: Use litellm with the GitHub Copilot provider for LLM calls, structured output, tool calling, and model selection. Covers when to use litellm vs the Copilot SDK, the three structured output strategies (json_schema, tool_choice, text_format), model discovery, Copilot multipliers, and Artificial Analysis benchmarks. Triggers on "litellm", "copilot llm", "structured output", "copilot models", "github_copilot", "LLM call", "tool calling", "copilot sdk vs litellm", "model selection", "premium requests".
---

# LiteLLM with GitHub Copilot Provider

Use `litellm` to call LLMs through the GitHub Copilot proxy with structured output, tool calling, and multi-model support. The `github_copilot/` provider authenticates via OAuth device flow and routes through the same API as Copilot Chat.

## When to Use litellm vs the Copilot SDK

| Use case | Use litellm | Use Copilot SDK |
|----------|-------------|-----------------|
| Structured output (JSON) | ✅ Native json_schema / tool_choice | ❌ No structured output support — prompt-parse with regex, ~10% failure |
| Batch processing / rating | ✅ Sync calls, easy parallelization | ❌ Designed for streaming |
| One-off LLM calls | ✅ Simple request/response | ⚠️ Overkill — session overhead |
| Streaming markdown | ❌ Possible but awkward | ✅ `CopilotClient` + `create_session` |
| Interactive sessions | ❌ Stateless per call | ✅ Session persists context across turns |
| Built-in tools (web search, code exec) | ❌ Not available | ✅ Copilot-managed tool execution |
| Multi-model selection | ✅ Any model via `github_copilot/MODEL` | ⚠️ Default model only |
| Tool calling | ✅ Native function calling | ❌ Not supported |
| Non-OpenAI models (Claude) | ✅ Via tool_choice fallback | ⚠️ Limited |

**Rule of thumb:** Use litellm for programmatic, one-off LLM calls (rating, analysis, structured extraction). Use the Copilot SDK for interactive multi-turn sessions, streaming generation, and when you need Copilot's built-in tools (web search, code interpreter, etc.).

## Setup

```bash
pip install litellm pydantic
```

First call triggers OAuth device flow (one-time):
```
Go to https://github.com/login/device and enter code: XXXX-XXXX
```

Token cached at `~/.config/litellm/github_copilot/api-key.json`.

## Basic Usage

```python
import litellm

# Simple completion
resp = litellm.completion(
    model="github_copilot/gpt-5.4-mini",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(resp.choices[0].message.content)
```

## Structured Output — Three Strategies

The Copilot proxy handles different model families differently. You need three strategies:

### Strategy 1: `response_format` (GPT on /chat/completions)

For GPT models accessible via `/chat/completions` (NOT gpt-5.4 family):

```python
from pydantic import BaseModel

class Rating(BaseModel):
    coherence: int    # 1-10
    surprise: int     # 1-10

resp = litellm.completion(
    model="github_copilot/gpt-5.2",
    messages=[{"role": "user", "content": "Rate this text..."}],
    response_format=Rating,  # Pydantic model → native json_schema
)
result = Rating.model_validate_json(resp.choices[0].message.content)
```

**Works with:** gpt-5-mini, gpt-5.1, gpt-5.2, gpt-4.1, gpt-4o, o3, o4

### Strategy 2: `tool_choice` (Claude, Gemini, non-OpenAI)

The Copilot proxy **strips `response_format`** for non-OpenAI models — it returns empty body or prose. Use forced function calling instead (same pattern as LangChain's `with_structured_output()`):

```python
import json

class Rating(BaseModel):
    coherence: int
    surprise: int

tool_schema = {
    "type": "function",
    "function": {
        "name": "Rating",
        "description": "Return a Rating object.",
        "parameters": Rating.model_json_schema(),
    },
}

resp = litellm.completion(
    model="github_copilot/claude-sonnet-4.6",
    messages=[{"role": "user", "content": "Rate this text..."}],
    tools=[tool_schema],
    tool_choice={"type": "function", "function": {"name": "Rating"}},
)

raw = resp.choices[0].message.tool_calls[0].function.arguments
parsed = json.loads(raw) if isinstance(raw, str) else raw
result = Rating.model_validate(parsed)
```

**Works with:** claude-sonnet-4.6, claude-haiku-4.5, claude-opus-4.6, gemini-2.5-pro, gemini-3-flash

### Strategy 3: `text_format` (gpt-5.4 family on /responses)

The gpt-5.4 models return `"unsupported_api_for_model"` on `/chat/completions`. They **only** work via the `/responses` API:

```python
import asyncio

class Rating(BaseModel):
    coherence: int
    surprise: int

resp = asyncio.run(litellm.aresponses(
    model="github_copilot/gpt-5.4-mini",
    input="Rate this text...",
    text_format=Rating,        # Native structured output
    max_output_tokens=200,
    timeout=30.0,
))

# Extract text from responses output
for item in resp.output:
    if hasattr(item, "content") and item.content:
        for c in item.content:
            if hasattr(c, "text"):
                result = Rating.model_validate_json(c.text)
```

**Works with:** gpt-5.4-mini, gpt-5.4, gpt-5.4-nano

### Auto-Dispatch Pattern

Combine all three in one function:

```python
def structured_completion(model: str, messages: list, schema: type[BaseModel], **kwargs) -> BaseModel:
    RESPONSES_ONLY = {"gpt-5.4-mini", "gpt-5.4", "gpt-5.4-nano"}
    short = model.rsplit("/", 1)[-1] if "/" in model else model
    model_lower = model.lower()

    if short in RESPONSES_ONLY:
        # Strategy 3: /responses API
        resp = asyncio.run(litellm.aresponses(
            model=model,
            input=messages[-1]["content"],
            text_format=schema,
            max_output_tokens=kwargs.pop("max_tokens", 4096),
            timeout=kwargs.pop("timeout", 60.0),
        ))
        for item in resp.output:
            if hasattr(item, "content") and item.content:
                for c in item.content:
                    if hasattr(c, "text"):
                        return schema.model_validate_json(c.text)

    elif "gpt" in model_lower or "o3" in model_lower or "o4" in model_lower:
        # Strategy 1: native json_schema
        resp = litellm.completion(model=model, messages=messages, response_format=schema, **kwargs)
        return schema.model_validate_json(resp.choices[0].message.content)

    else:
        # Strategy 2: tool_choice (Claude, Gemini, etc.)
        tool = {"type": "function", "function": {
            "name": schema.__name__,
            "description": f"Return a {schema.__name__} object.",
            "parameters": schema.model_json_schema(),
        }}
        resp = litellm.completion(model=model, messages=messages,
                                   tools=[tool],
                                   tool_choice={"type": "function", "function": {"name": schema.__name__}},
                                   **kwargs)
        raw = resp.choices[0].message.tool_calls[0].function.arguments
        return schema.model_validate(json.loads(raw) if isinstance(raw, str) else raw)
```

## Model Discovery

### List available models from Copilot

```python
import json
from pathlib import Path

# Read cached auth
auth = json.loads(Path("~/.config/litellm/github_copilot/api-key.json").expanduser().read_text())
api_endpoint = auth["endpoints"]["api"]
token = auth["token"]

import urllib.request
req = urllib.request.Request(f"{api_endpoint}/models",
                             headers={"Authorization": f"Bearer {token}"})
models = json.loads(urllib.request.urlopen(req).read())
for m in sorted(models["data"], key=lambda x: x["id"]):
    print(m["id"])
```

### Copilot Model Multipliers (Premium Requests)

Models consume premium requests at different rates. With **unlimited GHCP**, optimize for quality×speed, not cost.

| Multiplier | Models | Notes |
|------------|--------|-------|
| **0× (free)** | gpt-5-mini, gpt-4.1, gpt-4o | Always available, no premium cost |
| **0.33×** | gpt-5.4-mini, claude-haiku-4.5, gemini-3-flash | Cheap, good for batch work |
| **1×** | gpt-5.4, gpt-5.1, gpt-5.2, claude-sonnet-4/4.5/4.6, gemini-2.5-pro | Standard |
| **3×** | claude-opus-4.5, claude-opus-4.6 | Expensive, rarely worth it for programmatic use |

**For unlimited GHCP plans:** Multiplier is irrelevant — pick by quality and speed.

### Artificial Analysis Benchmarks

Query the [Artificial Analysis API](https://artificialanalysis.ai) for model quality/speed benchmarks:

```python
import urllib.request, json

req = urllib.request.Request(
    "https://artificialanalysis.ai/api/v2/data/llms/models",
    headers={"x-api-key": "YOUR_KEY"}
)
data = json.loads(urllib.request.urlopen(req).read())

for model in sorted(data, key=lambda x: x.get("quality_index", 0), reverse=True)[:10]:
    print(f"{model['name']}: quality={model.get('quality_index', '?')}, "
          f"speed={model.get('tokens_per_second', '?')} t/s")
```

**Key benchmarks for Copilot models** (as of 2026-04):

| Model | AA Quality | Speed | Best for |
|-------|-----------|-------|----------|
| gpt-5.4 | 56.8 | 80 t/s | High-quality reasoning, proposing |
| gpt-5.2 | 51.3 | 70 t/s | Alternative proposer |
| gpt-5.4-mini | 48.9 | 179 t/s | Best quality×speed, batch rating |
| gpt-5.1 | 47.7 | 112 t/s | Balanced |
| claude-sonnet-4.6 | 44.4 | 53 t/s | Diversity, different reasoning style |

**Recommended defaults:**
- **Rater** (batch, speed matters): `github_copilot/gpt-5.4-mini` — highest quality-per-second
- **Proposer** (reasoning, quality matters): `github_copilot/gpt-5.4` — top quality score

## Tool Calling

```python
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get weather for a city",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
            },
            "required": ["city"],
        },
    },
}]

resp = litellm.completion(
    model="github_copilot/gpt-5.4-mini",
    messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
    tools=tools,
)

if resp.choices[0].message.tool_calls:
    call = resp.choices[0].message.tool_calls[0]
    print(f"Function: {call.function.name}")
    print(f"Args: {call.function.arguments}")
```

## Gotchas

1. **Copilot proxy strips `response_format` for non-OpenAI models.** You get empty body or prose. Use `tool_choice` instead (Strategy 2).

2. **gpt-5.4 models fail on `/chat/completions`.** They return `"unsupported_api_for_model"`. Use `litellm.aresponses()` (Strategy 3).

3. **`litellm.aresponses()` is async.** Wrap with `asyncio.run()` from synchronous code.

4. **OAuth token expires.** litellm auto-refreshes, but you may see a warning: `"API key expired, refreshing"`. This is normal.

5. **Windows UTF-8.** When writing LLM output to files, always use `encoding="utf-8"` — reasoning text often contains Unicode (→, ×, etc.).

6. **litellm/pydantic are optional deps.** If your project deploys to a server (Azure Functions, etc.) that doesn't need LLM calls, keep them in `[project.optional-dependencies]` and lazy-import.

7. **The `text` parameter in `aresponses()`** controls response format config. The `text_format` parameter is a convenience that accepts a Pydantic model directly.

8. **Streaming with `/responses`.** Use `stream=True` in `aresponses()` for streaming. The return type changes to a streaming iterator.
