"""config.py — 加载 harness 配置：领域词典、风险规则、数据源与 LLM 设置。

通用化核心：
  - 领域词典 / 风险阈值 外置为 config/domains/<name>.json
  - 数据源（git / jira / linear / confluence / googledoc）与 LLM provider
    外置为 config/settings.json，按配置启用、平级互补。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DOMAINS_DIR = os.path.join(ROOT, "config", "domains")
SETTINGS_PATH = os.path.join(ROOT, "config", "settings.json")


@dataclass
class DomainConfig:
    name: str
    modules: dict  # key -> {"cn","en","keywords":[...]}
    module_order: list
    rules: dict
    other_cn: str = "其他 / 基础"
    other_en: str = "Other / Foundation"


def _default_rules() -> dict:
    return {
        "security_late_frac": 0.6,   # 最早安全提交落在时间轴后该比例 => 事后补丁
        "high_escape_ratio": 1.5,    # 模块逃逸比 >= 该值且 feat>=2 => 质量逃逸
        "big_commit_files": 8,       # 单提交改动文件数 >= 该值 => 大爆炸提交
    }


def load_domain(name: str = "default") -> DomainConfig:
    """按名称加载领域词典；找不到则回退 default。"""
    path = os.path.join(DOMAINS_DIR, f"{name}.json")
    if not os.path.isfile(path):
        path = os.path.join(DOMAINS_DIR, "default.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    modules = data.get("modules", {})
    return DomainConfig(
        name=data.get("name", name),
        modules=modules,
        module_order=list(modules.keys()),
        rules={**_default_rules(), **data.get("rules", {})},
        other_cn=data.get("other_cn", "其他 / 基础"),
        other_en=data.get("other_en", "Other / Foundation"),
    )


def available_domains() -> list[str]:
    if not os.path.isdir(DOMAINS_DIR):
        return []
    return sorted(p[:-5] for p in os.listdir(DOMAINS_DIR) if p.endswith(".json"))


# —— 顶层 harness 设置（数据源 + LLM） ——
def _default_settings() -> dict:
    return {
        "domain": "default",
        "sources": {
            "git": {"enabled": True, "repo": "", "category": "code_repo"},
            "jira": {"enabled": False, "category": "pm_tool",
                     "base_url": "", "email_env": "JIRA_EMAIL", "token_env": "JIRA_API_TOKEN",
                     "project_key": ""},
            "linear": {"enabled": False, "category": "pm_tool",
                       "api_key_env": "LINEAR_API_KEY", "team_key": ""},
            "confluence": {"enabled": False, "category": "doc_tool",
                           "base_url": "", "token_env": "CONFLUENCE_TOKEN"},
            "googledoc": {"enabled": False, "category": "doc_tool",
                          "creds_env": "GOOGLE_CREDS_JSON", "folder_id": ""},
        },
        "llm": {
            "priority": ["shell", "ollama", "openai"],
            "shell": {"engine": "claude", "command": "claude", "args": ["-p"],
                      "model": "claude-code"},
            "ollama": {"model": "qwen2.5:3b", "base_url": "http://localhost:11434"},
            "openai": {"model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1",
                       "api_key_env": "OPENAI_API_KEY"},
        },
    }


def load_settings(path: Optional[str] = None) -> dict:
    """加载 config/settings.json；文件不存在时回退内置默认。

    用户提供的 path 会合并到默认之上（仅覆盖存在的键），保证缺字段不崩。
    """
    cfg = _default_settings()
    p = path or os.environ.get("HARNESS_SETTINGS") or SETTINGS_PATH
    if p and os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                user = json.load(f)
            _deep_merge(cfg, user)
        except Exception:
            pass
    return cfg


def _deep_merge(base: dict, over: dict) -> None:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
