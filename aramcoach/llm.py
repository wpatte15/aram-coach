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


def run(system_file: Path, prompt: str, on_text=None, image: bytes | None = None, effort: str | None = None,
        on_start=None, max_tokens: int = 16000, tools=None):
    """Send one request to Claude.

    system_file: path to the system prompt. It is identical across calls, so it is cached.
    prompt: the user message.
    on_text: optional callback, called with the answer text received so far each time more
      arrives. Only the api backend streams; the cli backend never calls it.
    image: optional JPEG bytes sent with the prompt. Only the api backend supports it.
    effort: reasoning effort for this request. Defaults to the setting used during a match.
    on_start: optional callback, called once when the API has begun to answer. By then it holds
      the system prompt in its cache, so requests sent after this read it and do not write it
      again. Only the api backend calls it.
    max_tokens: the most the answer may run to, reasoning included. The research requests
      raise it: they reason at length and their answers are long. Only the api backend uses it.
    tools: optional calculations Claude may call before it answers (see tools.Toolbox): an
      object with `definitions`, `rounds` and `call(name, input) -> (text, failed)`. Only the
      api backend offers them. The caller must not promise them in the prompt otherwise.

    Returns (text, meta). meta has latency (seconds), token counts, and cost (US dollars, or
    None when unknown). With tools it adds `turns`, the seconds each answer took, and
    `tool_calls`, what was called.
    """
    if config.BACKEND == "api":
        return _run_api(system_file, prompt, on_text, image, effort or config.EFFORT, on_start, max_tokens, tools)
    return _run_cli(system_file, prompt, on_text, image, effort or config.EFFORT, on_start, max_tokens)


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
_last_sent = {}              # system prompt path -> when a request with it last began to be answered


def prompt_is_warm(system_file: Path) -> bool:
    """Whether the API still holds this system prompt in its cache, as far as this process knows.

    The cache keeps a prompt for five minutes after its last use. Requests sent together on a
    cold prompt each pay to write it, about four times the price of reading it.
    """
    return time.time() - _last_sent.get(str(system_file), 0.0) < 270


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


def _cost(tokens: dict) -> float | None:
    """US dollars for the tokens of one request: {input, write, read, output}. None for a model with no listed price."""
    price = _PRICES.get(config.MODEL)
    if price is None:
        return None
    rate_in, rate_out, rate_read = price
    dollars = (tokens["input"] * rate_in + tokens["write"] * rate_in * 1.25 + tokens["read"] * rate_read
               + tokens["output"] * rate_out) / 1_000_000
    return round(dollars * (2 if config.SPEED == "fast" else 1), 4)


# Tool definitions sent inside a message. See _run_api for why they are not in the request's `tools` field.
_TOOLS_BETA = "inline-tools-2026-09-15"
_LAST_STEP = "That was the last step of calculations. Answer now, in the format the request asks for."


def _answer(open_stream, request: dict, system_file: Path, on_text, on_start):
    """One answer from the API, streamed. Returns the finished message; raises LLMError with words for the player."""
    import anthropic

    for attempt in range(3):
        try:
            with open_stream(**request) as stream:
                _last_sent[str(system_file)] = time.time()
                if on_start is not None:
                    on_start()
                if on_text is not None:
                    received = ""
                    for chunk in stream.text_stream:
                        received += chunk
                        on_text(received)
                return stream.get_final_message()
        except ValueError:
            # A tool input arrived as JSON the SDK could not read at all. It raises before the call is
            # complete, so there is nothing to answer: the same request is sent again, twice at most.
            if attempt == 2:
                raise LLMError("Claude's request for a calculation could not be read.")
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


def _run_api(system_file: Path, prompt: str, on_text=None, image: bytes | None = None, effort: str = "low",
             on_start=None, max_tokens: int = 16000, tools=None):
    client = _api_client()
    content = [{"type": "text", "text": prompt}]
    if image is not None:
        content.insert(0, {"type": "image", "source": {
            "type": "base64", "media_type": "image/jpeg", "data": base64.standard_b64encode(image).decode("ascii")}})
    messages = [{"role": "user", "content": content}]
    request = {
        "model": config.MODEL,
        "max_tokens": max_tokens,
        # The system prompt (instructions plus item catalog) is the same for every call in a
        # patch. Marking it for caching makes repeat calls cheaper and faster.
        "system": [{"type": "text", "text": _system_text(system_file), "cache_control": {"type": "ephemeral"}}],
        "messages": messages,
        "output_config": {"effort": effort},
    }
    if config.SPEED == "fast":
        request["speed"] = "fast"
    betas = []
    if config.MODEL in _FALLBACK_MODELS:
        betas.append(_FALLBACK_BETA)
        request["fallbacks"] = "default"
    offered = tools is not None and bool(tools.definitions)
    if offered:
        # The definitions travel in a message after the request text, not in the top-level `tools` field.
        # That field is rendered in front of the system prompt, so a request with tools and one without would
        # each keep their own cached copy of the 49,000-token prompt, about $0.25 to write every time one of
        # them went cold, and the requests that get no tools (augment picks, the review) would read a
        # different prompt than before. This way every kind of request shares one cached prompt.
        # The request text is marked for caching too: the answer after a calculation reads it again.
        content[-1]["cache_control"] = {"type": "ephemeral"}
        messages.append({"role": "system", "content": [
            {"type": "tool_addition", "tool": {"type": "tool_definition", "definition": {**d, "eager_input_streaming": True}}}
            for d in tools.definitions]})
        betas.append(_TOOLS_BETA)
    if betas:
        open_stream = client.beta.messages.stream
        request["betas"] = betas
    else:
        open_stream = client.messages.stream

    started, tokens, turns, steps = time.time(), {"input": 0, "write": 0, "read": 0, "output": 0}, [], 0
    while True:
        asked = time.time()
        message = _answer(open_stream, request, system_file, on_text, on_start if not turns else None)
        turns.append(round(time.time() - asked, 1))
        usage = message.usage
        tokens["input"] += usage.input_tokens or 0
        tokens["write"] += usage.cache_creation_input_tokens or 0
        tokens["read"] += usage.cache_read_input_tokens or 0
        tokens["output"] += usage.output_tokens or 0
        if message.stop_reason == "refusal":
            raise LLMError("Claude declined to answer this request.")
        if message.stop_reason == "max_tokens":          # checked before any call is run: a cut-off input can still parse
            raise LLMError("Claude's answer was cut off before it finished.")
        calls = [block for block in message.content if block.type == "tool_use"] if offered else []
        if not calls:
            break
        if steps >= tools.rounds:
            raise LLMError("Claude kept asking for calculations instead of answering.")
        steps += 1
        results = []
        for block in calls:
            text, failed = tools.call(block.name, block.input)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": text, **({"is_error": True} if failed else {})})
        if steps >= tools.rounds:
            results.append({"type": "text", "text": _LAST_STEP})
        messages.append({"role": "assistant", "content": message.content})
        messages.append({"role": "user", "content": results})

    _last_sent[str(system_file)] = time.time()
    text = "".join(block.text for block in message.content if block.type == "text")
    meta = {
        "latency": round(time.time() - started, 1),
        "input_tokens": tokens["input"],
        "cached_tokens": tokens["read"],
        "cache_write_tokens": tokens["write"],
        "output_tokens": tokens["output"],
        "cost": _cost(tokens),
        "served_by": message.model,
    }
    if offered:
        meta.update(turns=turns, tool_calls=list(tools.calls))
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


def _run_cli(system_file: Path, prompt: str, on_text=None, image: bytes | None = None, effort: str = "low",
             on_start=None, max_tokens: int = 16000):
    if image is not None:
        raise LLMError("Reading the screen needs an API key in .env. The Claude Code login cannot send images here.")
    cmd = [
        find_claude(), "-p",
        "--model", config.MODEL,
        "--effort", effort,
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
