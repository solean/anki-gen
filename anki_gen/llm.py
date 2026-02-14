from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List


class LlmError(RuntimeError):
    pass


class LlmHttpError(LlmError):
    def __init__(
        self,
        status_code: int,
        body: str,
        error_param: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.body = body
        self.error_param = error_param
        self.error_message = error_message or ""
        super().__init__(f"LLM HTTP error {status_code}: {body}")


@dataclass(frozen=True)
class LlmItem:
    line_id: int
    jp: str
    en: str


@dataclass(frozen=True)
class LlmSelection:
    line_id: int
    keep: bool
    focus: str
    gloss: str
    reason: str


@dataclass(frozen=True)
class LlmConfig:
    model: str
    api_key: str
    provider: str
    api_base: str
    endpoint: str
    temperature: float
    batch_size: int
    timeout_s: int
    level: str
    reasoning_effort: str = "minimal"
    app_name: str = ""
    site_url: str = ""
    anthropic_version: str = "2023-06-01"
    debug: bool = False
    debug_file: str = ""


def _normalize_endpoint(api_base: str, endpoint: str) -> str:
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint
    return f"{api_base.rstrip('/')}/{endpoint.lstrip('/')}"


def _is_openai_compatible(provider: str) -> bool:
    return provider in {"openai", "openrouter"}


def _debug_log(config: LlmConfig, message: str) -> None:
    if not config.debug and not config.debug_file:
        return

    stamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    line = f"[anki_gen.llm {stamp}] {message}"
    if config.debug:
        print(line, file=sys.stderr)
    if config.debug_file:
        parent = os.path.dirname(config.debug_file)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(config.debug_file, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")


def _build_prompts(items: List[LlmItem], level: str) -> tuple[str, str]:
    system = (
        "You select subtitle lines that make good language-learning flashcards. "
        "Pick broadly useful vocabulary or grammar and avoid proper nouns, locations, "
        "very specific facts, or context-only lines. Prefer shorter, general lines. "
        "Return strict JSON only."
    )
    user = (
        "Task: decide which lines should become Anki cards.\n"
        f"Learner proficiency: {level}\n"
        "Rules:\n"
        "- keep=true only if the line teaches useful vocab/grammar for this level\n"
        "- avoid names, locations, brand names, specific events, or overly niche content\n"
        "- beginner: favor high-frequency words and basic grammar\n"
        "- intermediate: allow less common but still general words/structures\n"
        "- advanced: allow idioms, nuanced grammar, and rarer but still useful words\n"
        "- focus: the key word or short phrase to study (empty if keep=false)\n"
        "- gloss: short English meaning for focus (1-4 words, empty if keep=false)\n"
        "- reason: short reason (max 12 words)\n"
        "Output JSON array of objects with keys: line_id, keep, focus, gloss, reason.\n"
        "Input JSON:\n"
        f"{json.dumps([item.__dict__ for item in items], ensure_ascii=False)}"
    )
    return system, user


def _build_payload(config: LlmConfig, items: List[LlmItem], completion_tokens: int) -> dict:
    system, user = _build_prompts(items, config.level)
    if config.provider == "anthropic":
        return {
            "model": config.model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "max_tokens": completion_tokens,
            "temperature": config.temperature,
        }
    if config.provider == "openrouter":
        payload = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": config.temperature,
            "max_tokens": completion_tokens,
        }
        if config.reasoning_effort:
            payload["reasoning"] = {"effort": config.reasoning_effort}
        return payload

    return {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": config.temperature,
        "max_completion_tokens": completion_tokens,
        "reasoning_effort": config.reasoning_effort,
    }


def _build_headers(config: LlmConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if config.provider == "anthropic":
        headers["x-api-key"] = config.api_key
        headers["anthropic-version"] = config.anthropic_version
        return headers

    headers["Authorization"] = f"Bearer {config.api_key}"
    if config.provider == "openrouter":
        if config.site_url:
            headers["HTTP-Referer"] = config.site_url
        if config.app_name:
            headers["X-Title"] = config.app_name
    return headers


def _post_json(url: str, payload: dict, headers: dict[str, str], timeout_s: int, config: LlmConfig) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for key, value in headers.items():
        req.add_header(key, value)
    _debug_log(config, f"POST {url}")
    _debug_log(config, f"Request payload: {json.dumps(payload, ensure_ascii=False)}")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8")
            _debug_log(config, f"Response status: {resp.status}")
            _debug_log(config, f"Response body: {body}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        _debug_log(config, f"Response status: {exc.code}")
        _debug_log(config, f"Response body: {detail}")
        error_param: str | None = None
        error_message: str | None = None
        try:
            decoded = json.loads(detail)
            error_obj = decoded.get("error", {})
            if isinstance(error_obj, dict):
                maybe_param = error_obj.get("param")
                if isinstance(maybe_param, str):
                    error_param = maybe_param
                maybe_message = error_obj.get("message")
                if isinstance(maybe_message, str):
                    error_message = maybe_message
        except (json.JSONDecodeError, AttributeError):
            pass
        raise LlmHttpError(
            status_code=exc.code,
            body=detail,
            error_param=error_param,
            error_message=error_message,
        ) from exc
    except urllib.error.URLError as exc:
        raise LlmError(f"LLM request failed: {exc.reason}") from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise LlmError(f"LLM response was not JSON: {body[:200]}") from exc


def _extract_json_array(text: str) -> list:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise LlmError("LLM response did not contain a JSON array")
    snippet = text[start : end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError as exc:
        raise LlmError(f"LLM response JSON parse failed: {exc}") from exc


def _parse_selections(raw: list, valid_ids: set[int]) -> List[LlmSelection]:
    selections: List[LlmSelection] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        line_id = item.get("line_id")
        if isinstance(line_id, str) and line_id.isdigit():
            line_id = int(line_id)
        if not isinstance(line_id, int) or line_id not in valid_ids:
            continue
        keep_value = item.get("keep", False)
        keep_bool = _parse_bool(keep_value)
        focus = item.get("focus") or ""
        gloss = item.get("gloss") or ""
        reason = item.get("reason") or ""
        selections.append(
            LlmSelection(
                line_id=line_id,
                keep=keep_bool,
                focus=str(focus).strip(),
                gloss=str(gloss).strip(),
                reason=str(reason).strip(),
            )
        )
    return selections


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "t"}
    return False


def _extract_message_content(response: dict, config: LlmConfig) -> str:
    content = None
    if _is_openai_compatible(config.provider):
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmError("LLM response missing choices/message/content") from exc
    elif config.provider == "anthropic":
        try:
            content = response["content"]
        except (KeyError, TypeError) as exc:
            raise LlmError("Anthropic response missing content") from exc

    if isinstance(content, str):
        _debug_log(config, f"Parsed content (str): {content}")
        return content

    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
                else:
                    # OpenAI-compatible list fragments may still expose "text".
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
        joined = "\n".join(parts)
        _debug_log(config, f"Parsed content (list->str): {joined}")
        return joined

    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            _debug_log(config, f"Parsed content (dict->str): {text}")
            return text

    _debug_log(config, f"Unsupported content type: {type(content).__name__}")
    raise LlmError("LLM response content had an unsupported format")


def _extract_finish_reason(response: dict) -> str:
    if "choices" in response:
        try:
            finish_reason = response["choices"][0]["finish_reason"]
        except (KeyError, IndexError, TypeError):
            return ""
        return finish_reason if isinstance(finish_reason, str) else ""
    stop_reason = response.get("stop_reason")
    return stop_reason if isinstance(stop_reason, str) else ""


def _lower_message(exc: LlmHttpError) -> str:
    return exc.error_message.lower() if exc.error_message else ""


def _apply_400_retry(exc: LlmHttpError, payload: dict, completion_tokens: int, config: LlmConfig) -> bool:
    if exc.status_code != 400:
        return False
    msg = _lower_message(exc)

    if config.provider == "openai":
        if exc.error_param == "temperature" and "temperature" in payload:
            payload.pop("temperature", None)
            _debug_log(config, "Retrying without temperature")
            return True
        if exc.error_param == "reasoning_effort" and "reasoning_effort" in payload:
            payload.pop("reasoning_effort", None)
            _debug_log(config, "Retrying without reasoning_effort")
            return True
        if exc.error_param == "max_tokens" and "max_tokens" in payload:
            payload.pop("max_tokens", None)
            payload["max_completion_tokens"] = completion_tokens
            _debug_log(config, "Retrying with max_completion_tokens")
            return True
        if exc.error_param == "max_completion_tokens" and "max_completion_tokens" in payload:
            payload.pop("max_completion_tokens", None)
            payload["max_tokens"] = completion_tokens
            _debug_log(config, "Retrying with max_tokens")
            return True
        if "temperature" in msg and "temperature" in payload:
            payload.pop("temperature", None)
            _debug_log(config, "Retrying without temperature (message heuristic)")
            return True
        if "reasoning_effort" in msg and "reasoning_effort" in payload:
            payload.pop("reasoning_effort", None)
            _debug_log(config, "Retrying without reasoning_effort (message heuristic)")
            return True
        if "max_completion_tokens" in msg and "max_completion_tokens" in payload:
            payload.pop("max_completion_tokens", None)
            payload["max_tokens"] = completion_tokens
            _debug_log(config, "Retrying with max_tokens (message heuristic)")
            return True
        if "max_tokens" in msg and "max_tokens" in payload:
            payload.pop("max_tokens", None)
            payload["max_completion_tokens"] = completion_tokens
            _debug_log(config, "Retrying with max_completion_tokens (message heuristic)")
            return True
        return False

    if config.provider == "openrouter":
        if (exc.error_param == "temperature" or "temperature" in msg) and "temperature" in payload:
            payload.pop("temperature", None)
            _debug_log(config, "Retrying without temperature")
            return True
        if (
            exc.error_param in {"reasoning", "reasoning_effort"}
            or "reasoning" in msg
            or "reasoning_effort" in msg
        ) and "reasoning" in payload:
            payload.pop("reasoning", None)
            _debug_log(config, "Retrying without reasoning")
            return True
        if exc.error_param == "max_completion_tokens" and "max_completion_tokens" in payload:
            payload.pop("max_completion_tokens", None)
            payload["max_tokens"] = completion_tokens
            _debug_log(config, "Retrying with max_tokens")
            return True
        if exc.error_param == "max_tokens" and "max_tokens" in payload:
            payload.pop("max_tokens", None)
            payload["max_completion_tokens"] = completion_tokens
            _debug_log(config, "Retrying with max_completion_tokens")
            return True
        if "max_completion_tokens" in msg and "max_completion_tokens" in payload:
            payload.pop("max_completion_tokens", None)
            payload["max_tokens"] = completion_tokens
            _debug_log(config, "Retrying with max_tokens (message heuristic)")
            return True
        if "max_tokens" in msg and "max_tokens" in payload:
            payload.pop("max_tokens", None)
            payload["max_completion_tokens"] = completion_tokens
            _debug_log(config, "Retrying with max_completion_tokens (message heuristic)")
            return True
        return False

    if config.provider == "anthropic":
        if (exc.error_param == "temperature" or "temperature" in msg) and "temperature" in payload:
            payload.pop("temperature", None)
            _debug_log(config, "Retrying without temperature")
            return True
    return False


def _apply_length_retry(payload: dict, finish_reason: str, config: LlmConfig) -> bool:
    if finish_reason not in {"length", "max_tokens"}:
        return False

    if config.provider == "openai":
        effort = payload.get("reasoning_effort")
        if effort != "minimal" and "reasoning_effort" in payload:
            payload["reasoning_effort"] = "minimal"
            _debug_log(config, "Retrying with reasoning_effort=minimal after length stop")
            return True
        if "max_completion_tokens" in payload and int(payload["max_completion_tokens"]) < 4000:
            payload["max_completion_tokens"] = min(4000, int(payload["max_completion_tokens"]) * 2)
            _debug_log(
                config,
                f"Retrying with max_completion_tokens={payload['max_completion_tokens']} after length stop",
            )
            return True
        if "max_tokens" in payload and int(payload["max_tokens"]) < 4000:
            payload["max_tokens"] = min(4000, int(payload["max_tokens"]) * 2)
            _debug_log(config, f"Retrying with max_tokens={payload['max_tokens']} after length stop")
            return True
        return False

    if config.provider == "openrouter":
        if "max_tokens" in payload and int(payload["max_tokens"]) < 4000:
            payload["max_tokens"] = min(4000, int(payload["max_tokens"]) * 2)
            _debug_log(config, f"Retrying with max_tokens={payload['max_tokens']} after length stop")
            return True
        if "max_completion_tokens" in payload and int(payload["max_completion_tokens"]) < 4000:
            payload["max_completion_tokens"] = min(4000, int(payload["max_completion_tokens"]) * 2)
            _debug_log(
                config,
                f"Retrying with max_completion_tokens={payload['max_completion_tokens']} after length stop",
            )
            return True
        return False

    if "max_tokens" in payload and int(payload["max_tokens"]) < 4000:
        payload["max_tokens"] = min(4000, int(payload["max_tokens"]) * 2)
        _debug_log(config, f"Retrying with max_tokens={payload['max_tokens']} after length stop")
        return True
    return False


def _request_batch(items: List[LlmItem], config: LlmConfig) -> List[LlmSelection]:
    url = _normalize_endpoint(config.api_base, config.endpoint)
    headers = _build_headers(config)
    completion_tokens = 1200
    payload = _build_payload(config, items, completion_tokens)
    response = None
    for _ in range(8):
        try:
            response = _post_json(url, payload, headers, config.timeout_s, config)
        except LlmHttpError as exc:
            if not _apply_400_retry(exc, payload, completion_tokens, config):
                raise
            continue

        finish_reason = _extract_finish_reason(response)
        try:
            content = _extract_message_content(response, config)
            raw = _extract_json_array(content)
            return _parse_selections(raw, {item.line_id for item in items})
        except LlmError:
            if _apply_length_retry(payload, finish_reason, config):
                continue
            raise
    if response is None:
        raise LlmError("LLM request failed after compatibility retries")
    raise LlmError("LLM request did not produce a parseable response")


def _batch_items(items: List[LlmItem], batch_size: int) -> List[List[LlmItem]]:
    if batch_size <= 0:
        return [items]
    return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]


def select_candidates(items: Iterable[LlmItem], config: LlmConfig) -> List[LlmSelection]:
    items_list = list(items)
    if not items_list:
        return []

    selections: List[LlmSelection] = []
    batches = _batch_items(items_list, config.batch_size)
    for batch in batches:
        try:
            selections.extend(_request_batch(batch, config))
        except LlmError as exc:
            # Fallback: split difficult large batches to improve JSON compliance.
            if len(batch) <= 1:
                raise
            _debug_log(
                config,
                f"Batch of {len(batch)} failed ({exc}); retrying as two smaller batches",
            )
            mid = len(batch) // 2
            selections.extend(_request_batch(batch[:mid], config))
            selections.extend(_request_batch(batch[mid:], config))
        if len(batches) > 1:
            time.sleep(0.2)
    return selections
