"""Thin, isolated Anthropic client. Uses forced tool-use for schema-bound JSON output.

The API key is read only from the environment / local .env and is never logged or returned.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from src.config import ROOT


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self, settings: dict):
        load_dotenv(ROOT / ".env")
        key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
        self._key = key if key and not key.lower().startswith("your-") else ""
        cfg = settings["llm"]
        self.model = os.getenv(cfg["model_env"], cfg["default_model"])
        self.max_calls = int(os.getenv("LLM_MAX_CALLS", "130"))
        self.max_retries = cfg["max_retries"]
        self.calls = 0
        self.stats = {"attempts": 0, "schema_valid": 0, "api_errors": 0, "input_tokens": 0, "output_tokens": 0,
                      "cache_read_tokens": 0}
        self._client = None
        self._log = ROOT / "outputs" / "llm_audit_log.jsonl"

    @property
    def available(self) -> bool:
        return bool(self._key)

    def status(self) -> str:
        """Human-readable status; never includes the key."""
        return (f"Anthropic API key {'found' if self.available else 'NOT set (running in deterministic mode)'}; "
                f"model={self.model}; call cap={self.max_calls}")

    def _sdk(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._key)
        return self._client

    def _scrub(self, text: str) -> str:
        return text.replace(self._key, "***") if self._key else text

    def call_tool(self, *, system: str, user: str, model_cls: type[BaseModel], tool_name: str,
                  description: str, max_tokens: int, tag: str) -> BaseModel | None:
        if not self.available:
            raise LLMUnavailable("ANTHROPIC_API_KEY is not configured")
        tool = {"name": tool_name, "description": description, "input_schema": model_cls.model_json_schema()}
        messages = [{"role": "user", "content": user}]
        for attempt in range(self.max_retries + 1):
            if self.calls >= self.max_calls:
                self._audit(tag, attempt, "call_cap_reached")
                return None
            self.calls += 1
            self.stats["attempts"] += 1
            try:
                resp = self._sdk().messages.create(
                    model=self.model, max_tokens=max_tokens,
                    system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                    messages=messages, tools=[tool], tool_choice={"type": "tool", "name": tool_name},
                )
            except Exception as exc:  # network/auth/rate-limit: report the type only, scrubbed
                self.stats["api_errors"] += 1
                self._audit(tag, attempt, f"api_error:{type(exc).__name__}:{self._scrub(str(exc))[:120]}")
                time.sleep(min(2 ** attempt, 8))
                continue
            u = resp.usage
            self.stats["input_tokens"] += getattr(u, "input_tokens", 0) or 0
            self.stats["output_tokens"] += getattr(u, "output_tokens", 0) or 0
            self.stats["cache_read_tokens"] += getattr(u, "cache_read_input_tokens", 0) or 0
            block = next((b for b in resp.content if getattr(b, "type", "") == "tool_use"), None)
            if block is None:
                self._audit(tag, attempt, "no_tool_use")
                continue
            try:
                obj = model_cls.model_validate(block.input)
                self.stats["schema_valid"] += 1
                self._audit(tag, attempt, "ok")
                return obj
            except ValidationError as exc:
                self._audit(tag, attempt, f"schema_invalid:{len(exc.errors())} errors")
                messages = [messages[0], {"role": "assistant", "content": resp.content},
                            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": block.id, "is_error": True,
                                                          "content": f"Schema validation failed: {exc.errors()[:3]}. Call the tool again with valid fields."}]}]
        return None

    def _audit(self, tag: str, attempt: int, outcome: str) -> None:
        try:
            self._log.parent.mkdir(parents=True, exist_ok=True)
            rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "tag": tag, "attempt": attempt, "outcome": outcome,
                   "tag_hash": hashlib.sha1(tag.encode()).hexdigest()[:8]}
            with open(self._log, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
        except OSError:
            pass
