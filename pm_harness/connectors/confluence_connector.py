"""connectors/confluence_connector.py — 文档工具 Confluence（doc_tool）。

真实 REST 调用（/wiki/rest/api/content），Bearer token 鉴权。
用于监控规格/需求文档的修订（需求变更的文档侧信号）。
未配置 base_url 或缺失 token 时跳过。
"""
from __future__ import annotations

import json
import os

from ..model import WorkItem
from .base import BaseConnector


class ConfluenceConnector(BaseConnector):
    source = "confluence"
    category = "doc_tool"

    def collect(self) -> list[WorkItem]:
        if self.cfg.get("fixture"):
            return self._from_fixture()
        base = (self.cfg.get("base_url") or "").rstrip("/")
        if not base:
            self.skip_reason = "未配置 base_url"
            return []
        token = os.environ.get(self.cfg.get("token_env", "CONFLUENCE_TOKEN") or "")
        if not token:
            self.skip_reason = f"缺失凭证环境变量 {self.cfg.get('token_env')}"
            return []
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        url = f"{base}/wiki/rest/api/content?type=page&limit=200&expand=version"
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.load(r)
        except Exception as e:
            self.skip_reason = f"API 调用失败：{e}"
            return []
        items = []
        for page in data.get("results", []):
            ver = page.get("version", {})
            items.append(WorkItem(
                source="confluence", category="doc_tool",
                id=page.get("id", ""),
                kind="doc",
                title=page.get("title", ""),
                date=(ver.get("when") or "")[:10],
                author=(ver.get("by") or {}).get("displayName", ""),
                status="updated",
                desc="",
                raw=page,
            ))
        return items
