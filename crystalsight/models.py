"""Pluggable model interface.

Every model implements ``complete(messages) -> ModelReply`` over OpenAI-style
chat messages. Image parts use the OpenAI ``image_url`` data-URL form.

Secrets: ``OpenAICompatModel`` reads the API key and base URL from environment
variables whose *names* are configured in ``configs/models.toml``. If an
``env_files`` entry is configured it is parsed at runtime with ``os.environ.setdefault``
(KEY=VALUE lines, paths relative to the repo root); values are never written to
logs, run records or reports.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paths import ROOT


@dataclass
class ModelReply:
    text: str
    usage: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    error: str | None = None


class Model:
    name: str = "model"
    supports_vision: bool = False

    def complete(self, messages: list[dict[str, Any]], *, context: dict[str, Any] | None = None) -> ModelReply:
        raise NotImplementedError


# --------------------------------------------------------------------- mocks
class MockModel(Model):
    """Deterministic offline model used to prove the pipeline end to end.

    mode="random": seeded guess with the right answer *type* (lower bound).
    mode="oracle": reads the gold answer from ``context`` (scorer self-test only;
                   never a benchmark result).
    In interactive channels it first emits a few legal actions / tool calls,
    exercising the TUI and tool loops, then answers.
    """

    supports_vision = True

    def __init__(self, mode: str = "random", seed: int = 0):
        self.mode = mode
        self.name = f"mock-{mode}"
        self.seed = seed

    def complete(self, messages, *, context=None) -> ModelReply:
        ctx = context or {}
        task = ctx.get("task", {})
        channel = ctx.get("channel")
        step = ctx.get("step", 0)
        rng = random.Random(f"{self.seed}:{task.get('id')}:{channel}")
        if channel == "tui" and step < 2:
            action = [
                {"action": "orbit", "arguments": {"yaw_deg": 45, "pitch_deg": 20}},
                {"action": "align", "arguments": {"axis": "c"}},
            ][step]
            return ModelReply(json.dumps(action))
        if channel == "tools" and step < 1:
            return ModelReply(json.dumps({"tool": "mck_analyze_summary", "arguments": {}}))
        if self.mode == "oracle":
            ans = task.get("gold")
        else:
            ans = _random_answer(task, rng)
        return ModelReply(json.dumps({"answer": ans}))


def _random_answer(task: dict, rng: random.Random) -> Any:
    t = task.get("answer_type")
    if t == "bool":
        return rng.choice([True, False])
    if t == "int":
        return rng.randint(1, 8)
    if t == "choice":
        return rng.choice(task.get("options") or ["?"])
    if t == "set":
        opts = task.get("options") or []
        return sorted(o for o in opts if rng.random() < 0.5)
    if t == "formula_set":
        return ["C1H1"]
    if t == "object":
        out = {}
        for k, spec in task.get("schema", {}).items():
            st = spec["type"]
            if st == "bool":
                out[k] = rng.choice([True, False])
            elif st == "int":
                out[k] = rng.randint(2, 8)
            elif st == "choice":
                out[k] = rng.choice(spec.get("options") or ["?"])
            elif st == "label":
                out[k] = rng.choice(spec.get("candidates") or ["?"])
            elif st == "set":
                opts = spec.get("options") or ["C", "N", "O"]
                out[k] = sorted(o for o in opts if rng.random() < 0.4)
        return out
    return None


# ------------------------------------------------------- OpenAI compatible
def load_env_file(path: Path) -> list[str]:
    """Load KEY=VALUE lines into os.environ (setdefault). Returns key names only."""
    names: list[str] = []
    if not path.exists():
        return names
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
        names.append(key.strip())
    return names


class OpenAICompatModel(Model):
    def __init__(self, cfg: dict[str, Any]):
        self.name = cfg["name"]
        self.model = cfg["model"]
        self.base_url_env = cfg["base_url_env"]
        self.api_key_env = cfg["api_key_env"]
        self.supports_vision = bool(cfg.get("vision", False))
        self.max_tokens = int(cfg.get("max_output_tokens", 2048))
        self.temperature = cfg.get("temperature", 0)
        self.timeout = float(cfg.get("timeout_s", 180))
        self.retries = int(cfg.get("max_retries", 3))
        self.json_mode = bool(cfg.get("json_mode", False))
        for env_file in cfg.get("env_files", []):
            ef = Path(os.path.expandvars(env_file))
            if not ef.is_absolute():
                from .paths import ROOT
                ef = ROOT / ef
            load_env_file(ef)
        # The model id can be overridden per deployment (gateways often prefix ids),
        # e.g. CRYSTALSIGHT_MODEL_DEEPSEEK=provider/DeepSeek-v4-Flash in the environment or .env.
        if cfg.get("model_env") and os.environ.get(cfg["model_env"]):
            self.model = os.environ[cfg["model_env"]]

    @staticmethod
    def _first_env(names) -> tuple[str | None, str | None]:
        for n in [names] if isinstance(names, str) else list(names):
            if os.environ.get(n):
                return n, os.environ[n]
        return None, None

    def _endpoint(self) -> tuple[str, str]:
        _, base = self._first_env(self.base_url_env)
        _, key = self._first_env(self.api_key_env)
        if not base:
            raise RuntimeError(f"missing env var {self.base_url_env}")
        if not key:
            raise RuntimeError(f"missing env var {self.api_key_env}")
        return base.rstrip("/") + "/chat/completions", key

    def complete(self, messages, *, context=None) -> ModelReply:
        url, key = self._endpoint()
        body: dict[str, Any] = {"model": self.model, "messages": messages,
                                "max_tokens": self.max_tokens, "stream": False}
        if self.temperature is not None:
            body["temperature"] = self.temperature
        if self.json_mode:
            body["response_format"] = {"type": "json_object"}
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        last = "unknown"
        for attempt in range(self.retries + 1):
            t0 = time.monotonic()
            req = urllib.request.Request(url, data=data, method="POST", headers={
                "content-type": "application/json", "authorization": f"Bearer {key}",
                "user-agent": "CrystalSight/0.1"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    raw = json.loads(r.read().decode("utf-8"))
                msg = raw["choices"][0]["message"]
                text = msg.get("content") or ""
                return ModelReply(text, usage=raw.get("usage", {}) or {},
                                  latency_ms=(time.monotonic() - t0) * 1000)
            except urllib.error.HTTPError as e:
                detail = ""
                try:
                    detail = e.read().decode("utf-8", "replace")[:300]
                except Exception:  # noqa: BLE001
                    pass
                last = f"HTTP {e.code}: {_scrub(detail, key)}"
                if e.code != 429 and e.code < 500:
                    break
            except Exception as e:  # noqa: BLE001
                last = f"{type(e).__name__}: {_scrub(str(e), key)}"
            time.sleep(min(20, 2 ** attempt))
        return ModelReply("", error=last)


def _scrub(text: str, key: str) -> str:
    return text.replace(key, "<redacted>") if key else text


# ------------------------------------------------------------- registry
def load_models(spec: list[str], config_path: Path | None = None) -> list[Model]:
    config_path = config_path or ROOT / "configs" / "models.toml"
    cfgs = {}
    if config_path.exists():
        cfgs = {m["name"]: m for m in tomllib.loads(config_path.read_text(encoding="utf-8-sig")).get("models", [])}
    out: list[Model] = []
    for name in spec:
        if name.startswith("mock"):
            mode = name.split("-", 1)[1] if "-" in name else "random"
            out.append(MockModel(mode))
        elif name in cfgs:
            out.append(OpenAICompatModel(cfgs[name]))
        else:
            raise KeyError(f"unknown model {name!r}; known: mock-random, mock-oracle, {sorted(cfgs)}")
    return out


_JSON_RE = re.compile(r"\{.*\}", re.S)


def extract_json(text: str) -> dict | None:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    cands = [fence.group(1)] if fence else []
    m = _JSON_RE.search(text)
    if m:
        cands.append(m.group(0))
    for c in cands:
        try:
            v = json.loads(c)
            if isinstance(v, dict):
                return v
        except json.JSONDecodeError:
            continue
    return None
