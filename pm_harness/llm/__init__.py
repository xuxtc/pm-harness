"""llm — 可配置的 LLM provider 抽象层。

用户需求优先级（省钱）：
  1. shell  → Claude Code / WorkBuddy 等 agentic harness（command 调用，通常已是订阅）
  2. ollama → 本地模型（免费、离线）
  3. openai → 任意 OpenAI 兼容 API（按 token 计费，最后才用）

resolve_provider(llm_cfg) 按 priority 顺序返回「第一个可用」的 provider；
全部不可用时返回 None，由上层走模板降级（仍基于真实数字）。
零外部依赖：shell 用 subprocess，ollama/openai 用 urllib。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
from typing import Optional


class BaseProvider:
    name = "base"

    def available(self) -> bool:
        raise NotImplementedError

    def generate(self, prompt: str, timeout: int = 300) -> str:
        raise NotImplementedError


class OllamaProvider(BaseProvider):
    name = "ollama"

    def __init__(self, cfg: dict):
        self.base = (cfg.get("base_url") or "http://localhost:11434").rstrip("/")
        self.model = cfg.get("model", "qwen2.5:3b")

    def available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=4):
                return True
        except Exception:
            return False

    def generate(self, prompt: str, timeout: int = 300) -> str:
        payload = json.dumps({
            "model": self.model, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.3, "num_predict": 300},
        }).encode("utf-8")
        req = urllib.request.Request(f"{self.base}/api/generate", data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read()).get("response", "").strip()


class OpenAICompatProvider(BaseProvider):
    name = "openai"

    def __init__(self, cfg: dict):
        self.base = (cfg.get("base_url") or "https://api.openai.com/v1").rstrip("/")
        self.model = cfg.get("model", "gpt-4o-mini")
        self.key_env = cfg.get("api_key_env", "OPENAI_API_KEY")

    def available(self) -> bool:
        return bool(os.environ.get(self.key_env))

    def generate(self, prompt: str, timeout: int = 300) -> str:
        key = os.environ.get(self.key_env)
        if not key:
            raise RuntimeError(f"缺失环境变量 {self.key_env}")
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3, "max_tokens": 400,
        }).encode("utf-8")
        req = urllib.request.Request(f"{self.base}/chat/completions", data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {key}")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
        return data["choices"][0]["message"]["content"].strip()


class ShellProvider(BaseProvider):
    name = "shell"

    def __init__(self, cfg: dict):
        self.command = cfg.get("command", "claude")
        self.args = cfg.get("args", ["-p"])
        self.model = cfg.get("model", "claude-code")

    def available(self) -> bool:
        return bool(shutil.which(self.command))

    def generate(self, prompt: str, timeout: int = 300) -> str:
        cmd = [self.command] + list(self.args) + [prompt]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[-300:])
        return proc.stdout.strip()


def resolve_provider(llm_cfg: Optional[dict]) -> Optional[BaseProvider]:
    """按 priority 返回第一个可用的 provider（省钱顺序：shell > ollama > openai）。"""
    if not llm_cfg:
        return None
    priority = llm_cfg.get("priority", ["shell", "ollama", "openai"])
    builders = {
        "shell": lambda b: ShellProvider(b),
        "ollama": lambda b: OllamaProvider(b),
        "openai": lambda b: OpenAICompatProvider(b),
    }
    for key in priority:
        block = llm_cfg.get(key)
        if not block:
            continue
        provider = builders.get(key)
        if not provider:
            continue
        p = provider(block)
        if p.available():
            return p
    return None
