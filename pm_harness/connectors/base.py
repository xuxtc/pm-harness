"""connectors/base.py — 所有数据源 connector 的基类。"""
from __future__ import annotations

import json
import os
from typing import Optional

from ..model import WorkItem

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class BaseConnector:
    source: str = "unknown"
    category: str = "other"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.skip_reason: Optional[str] = None

    def enabled(self) -> bool:
        return bool(self.cfg.get("enabled"))

    def collect(self) -> list[WorkItem]:
        """子类实现。默认：若配置了 fixture 则读取样例，否则返回空。"""
        if self.cfg.get("fixture"):
            return self._from_fixture()
        return []

    def _from_fixture(self) -> list[WorkItem]:
        path = self.cfg["fixture"]
        if not os.path.isabs(path):
            path = os.path.join(ROOT, path)
        if not os.path.isfile(path):
            self.skip_reason = f"fixture 文件不存在：{path}"
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [WorkItem.from_dict(d) for d in data]

    @staticmethod
    def _norm_kind(t: str) -> str:
        s = (t or "").lower()
        if "story" in s:
            return "story"
        if "epic" in s:
            return "epic"
        if "bug" in s or "缺陷" in s:
            return "fix"
        if "task" in s or "subtask" in s:
            return "task"
        if "feature" in s or "需求" in s or "feature" in s:
            return "feat"
        return "requirement"

    @staticmethod
    def _norm_status(s: str) -> str:
        return (s or "unknown").strip().lower()
