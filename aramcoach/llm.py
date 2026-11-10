"""Claude backends.

`run` sends one request and returns the answer text. Two backends exist:

- api: the Anthropic SDK with an API key. Used when ANTHROPIC_API_KEY is set (see config.py).
- cli: the Claude Code CLI in headless mode (`claude -p`), which uses the Claude login on
  this machine. Used when there is no API key. It cannot stream or read images.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from . import config


class LLMError(RuntimeError):
    pass


def run(system_file: Path, prompt: str, on_text=None, image: bytes | None = None):
    """Send one request to Claude.

    system_file: path to the system prompt. It is identical across calls, so it is cached.
    prompt: the user message.
    on_text: optional callback, called with the answer text received so far each time more
      arrives. Only the api backend streams; the cli backend never calls it.
    image: optional JPEG bytes sent with the prompt. Only the api backend supports it.

    Returns (text, meta). meta has latency (seconds), token counts, and cost (US dollars, or
    None when unknown).
    """
    backend = _run_api if config.BACKEND == "api" else _run_cli
    return backend(system_file, prompt, on_text, image)


# ---- API backend -----------------------------------------------------------

# US dollars per million tokens: (input, output, cache read). Cache writes cost 1.25x input.
# Fast mode doubles the rate. Models missing from this table report no cost.
_PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10),
    "claude-fable-5-2": (8.00, 40.00, 0.20),
}
# Models that support server-side refusal fallback: if a safety classifier declines a
# request, the API re-runs it on another model instead of returning the refusal.
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-2"}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"

_client = None
_system_cache = {}


def _api_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=config.API_KEY, timeout=config.LLM_TIMEOUT, max_retries=1)
    return _client


def warm_up():
    """Load the SDK ahead of the first request.

    Importing it takes about six seconds on this machine. Doing that at launch keeps the
    delay out of the first plan of a game.
    """
    if config.BACKEND == "api":
        _api_client()


def _system_text(path: Path) -> str:
    key = (str(path), path.stat().st_mtime_ns)
    if key not in _system_cache:
        _system_cache.clear()
        _system_cache[key] = path.read_text(encoding="utf-8")
    return _system_cache[key]


def _cost(usage) -> float | None:
    price = _PRICES.get(config.MODEL)
    if price is None:
        return None
    rate_in, rate_out, rate_read = price
    dollars = (
        (usage.input_tokens or 0) * rate_in
        + (usage.cache_creation_input_tokens or 0) * rate_in * 1.25
        + (usage.cache_read_input_tokens or 0) * rate_read
        + (usage.output_tokens or 0) * rate_out
    ) / 1_000_000
    return round(dollars * (2 if config.SPEED == "fast" else 1), 4)


def _run_api(system_file: Path, prompt: str, on_text=None, image: bytes | None = None):
    import anthropic

    client = _api_client()
    content = [{"type": "text", "text": prompt}]
    if image is not None:
        content.insert(0, {"type": "image", "source": {
            "type": "base64", "media_type": "image/jpeg", "data": base64.standard_b64encode(image).decode("ascii")}})
    request = {
        "model": config.MODEL,
        "max_tokens": 16000,
        # The system prompt (instructions plus item catalog) is the same for every call in a
        # patch. Marking it for caching makes repeat calls cheaper and faster.
        "system": [{"type": "text", "text": _system_text(system_file), "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": content}],
        "output_config": {"effort": config.EFFORT},
    }
    if config.SPEED == "fast":
        request["speed"] = "fast"
    if config.MODEL in _FALLBACK_MODELS:
        open_stream = client.beta.messages.stream
        request.update(betas=[_FALLBACK_BETA], fallbacks="default")
    else:
        open_stream = client.messages.stream

    started = time.time()
    try:
        with open_stream(**request) as stream:
            if on_text is not None:
                received = ""
                for chunk in stream.text_stream:
                    received += chunk
                    on_text(received)
            message = stream.get_final_message()
    except anthropic.AuthenticationError:
        raise LLMError("The API key was rejected. Check ANTHROPIC_API_KEY in the .env file.")
    except anthropic.PermissionDeniedError as exc:
        raise LLMError(f"The API key is not allowed to do this: {exc.message}")
    except anthropic.NotFoundError:
        raise LLMError(f"The model '{config.MODEL}' was not found. Check ARAMCOACH_MODEL.")
    except anthropic.RateLimitError:
        raise LLMError("Rate limited by the API. The coach retries shortly.")
    except anthropic.BadRequestError as exc:
        raise LLMError(f"The API rejected the request: {exc.message}")   # includes an exhausted credit balance
    except anthropic.APIStatusError as exc:
        raise LLMError(f"API error {exc.status_code}: {exc.message}")
    except anthropic.APIConnectionError:
        raise LLMError("Could not reach the Claude API. Check the internet connection.")

    if message.stop_reason == "refusal":
        raise LLMError("Claude declined to answer this request.")
    if message.stop_reason == "max_tokens":
        raise LLMError("Claude's answer was cut off before it finished.")
    text = "".join(block.text for block in message.content if block.type == "text")
    usage = message.usage
    meta = {
        "latency": round(time.time() - started, 1),
        "input_tokens": usage.input_tokens or 0,
        "cached_tokens": usage.cache_read_input_tokens or 0,
        "cache_write_tokens": usage.cache_creation_input_tokens or 0,
        "output_tokens": usage.output_tokens or 0,
        "cost": _cost(usage),
        "served_by": message.model,
    }
    return text, meta


# ---- CLI backend -----------------------------------------------------------

def find_claude() -> str:
    override = os.environ.get("ARAMCOACH_CLAUDE")
    if override:
        return override
    shim = shutil.which("claude")
    if shim:
        # The npm shim is a .cmd file, and cmd.exe mangles long arguments. Call the binary behind it.
        exe = Path(shim).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        return str(exe) if exe.exists() else shim
    raise LLMError("The `claude` command was not found. Install Claude Code or add an API key to .env.")


def _run_cli(system_file: Path, prompt: str, on_text=None, image: bytes | None = None):
    if image is not None:
        raise LLMError("Reading the screen needs an API key in .env. The Claude Code login cannot send images here.")
    cmd = [
        find_claude(), "-p",
        "--model", config.MODEL,
        "--effort", config.EFFORT,
        "--tools", "",                    # plain question and answer: no file or shell tools
        "--safe-mode",                    # ignore personal CLAUDE.md, hooks, plugins, and MCP servers
        "--strict-mcp-config",
        "--no-session-persistence",
        "--disable-slash-commands",
        "--system-prompt-file", str(system_file),
        "--output-format", "json",
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=prompt.encode("utf-8"),
            capture_output=True,
            timeout=config.LLM_TIMEOUT,
            cwd=str(config.CACHE_DIR),
            # Without this flag Windows can open a console window, which would steal focus from the game.
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired:
        raise LLMError(f"Claude did not answer within {config.LLM_TIMEOUT} seconds.")
    except OSError as exc:
        raise LLMError(f"Could not start Claude: {exc}")

    stdout = proc.stdout.decode("utf-8", "replace").strip()
    try:
        result = json.loads(stdout)
    except ValueError:
        detail = proc.stderr.decode("utf-8", "replace").strip() or stdout
        raise LLMError(f"Claude returned no usable output (exit code {proc.returncode}): {detail[:300]}")
    if result.get("is_error") or result.get("subtype") != "success":
        raise LLMError(f"Claude call failed: {str(result.get('result') or result.get('subtype'))[:300]}")

    usage = result.get("usage") or {}
    meta = {
        "latency": round((result.get("duration_ms") or 0) / 1000, 1),
        "input_tokens": usage.get("input_tokens", 0),
        "cached_tokens": usage.get("cache_read_input_tokens", 0),
        "cache_write_tokens": usage.get("cache_creation_input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cost": None,                     # covered by the Claude subscription
    }
    return result.get("result") or "", meta
