"""connectors — 多数据源接入层。

设计原则（用户需求）：
  - 数据源分三类：code_repo（代码仓库）/ pm_tool（项目管理）/ doc_tool（文档工具）
  - 同一项目内通常只用一种 pm_tool（Jira 或 Linear 二选一），但 harness 不强制；
    所有已启用且成功读取的源"平级互补"，合并为统一的 WorkItem 流。
  - 每个 connector 只在「配置启用 + 凭证/路径可用」时读取；否则跳过并说明原因，
    绝不编造数据。
  - 支持 fixture 字段（指向一份 WorkItem JSON），用于无凭证时的端到端测试与示例。

新增数据源：在 REGISTRY 注册一个 BaseConnector 子类即可，analyze/report 不动。
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Optional

from ..model import WorkItem
from .git_connector import GitConnector
from .jira_connector import JiraConnector
from .linear_connector import LinearConnector
from .confluence_connector import ConfluenceConnector
from .googledoc_connector import GoogleDocConnector

REGISTRY = {
    "git": GitConnector,
    "jira": JiraConnector,
    "linear": LinearConnector,
    "confluence": ConfluenceConnector,
    "googledoc": GoogleDocConnector,
}


def _http_get_json(url: str, headers: dict, timeout: int = 20):
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _http_post_json(url: str, headers: dict, payload: dict, timeout: int = 20):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


class SourceReport:
    def __init__(self, name: str, category: str, count: int, note: str = ""):
        self.name = name
        self.category = category
        self.count = count
        self.note = note


def collect_from_config(settings: dict) -> tuple[list[WorkItem], list[SourceReport]]:
    """按 settings["sources"] 实例化已启用的 connector，合并 WorkItem。

    返回 (items, reports)：items 为统一工作项列表；reports 描述每个源读取情况
    （用于报告里列出"本次实际读取了哪些源"）。
    """
    items: list[WorkItem] = []
    reports: list[SourceReport] = []
    sources = settings.get("sources", {})
    for name, cfg in sources.items():
        if not cfg.get("enabled"):
            continue
        cls = REGISTRY.get(name)
        if cls is None:
            reports.append(SourceReport(name, cfg.get("category", "?"), 0, "未知数据源，已忽略"))
            continue
        conn = cls(cfg)
        try:
            got = conn.collect()
            if got:
                items.extend(got)
                reports.append(SourceReport(name, conn.category, len(got), "已读取"))
            else:
                reports.append(SourceReport(name, conn.category, 0, conn.skip_reason or "未返回数据（未配置凭证/路径）"))
        except Exception as e:
            reports.append(SourceReport(name, conn.category, 0, f"读取失败：{e}"))
    return items, reports
