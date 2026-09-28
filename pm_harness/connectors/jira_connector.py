"""connectors/jira_connector.py — 项目管理工具 Jira（pm_tool）。

真实 REST 调用（Jira Cloud / Server 通用 /rest/api/3/search）。
凭证：email_env + token_env（API token），以 HTTP Basic 鉴权。
未配置 base_url 或缺失凭证时跳过，不编造数据。
"""
from __future__ import annotations

import base64
import os
import urllib.request

from ..model import WorkItem
from .base import BaseConnector


class JiraConnector(BaseConnector):
    source = "jira"
    category = "pm_tool"

    def collect(self) -> list[WorkItem]:
        if self.cfg.get("fixture"):
            return self._from_fixture()
        base = (self.cfg.get("base_url") or "").rstrip("/")
        if not base:
            self.skip_reason = "未配置 base_url"
            return []
        email = os.environ.get(self.cfg.get("email_env", "JIRA_EMAIL") or "")
        token = os.environ.get(self.cfg.get("token_env", "JIRA_API_TOKEN") or "")
        if not token:
            self.skip_reason = f"缺失凭证环境变量 {self.cfg.get('token_env')}"
            return []
        project = self.cfg.get("project_key") or ""
        jql = f"project = {project} ORDER BY updated DESC" if project else "ORDER BY updated DESC"
        auth = base64.b64encode(f"{email}:{token}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}
        url = f"{base}/rest/api/3/search?jql={urllib.request.quote(jql)}&maxResults=200"
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=20) as r:
                data = __import__("json").load(r)
        except Exception as e:
            self.skip_reason = f"API 调用失败：{e}"
            return []
        items = []
        for iss in data.get("issues", []):
            f = iss.get("fields", {})
            items.append(WorkItem(
                source="jira", category="pm_tool",
                id=iss.get("key", ""),
                kind=self._norm_kind((f.get("issuetype") or {}).get("name", "")),
                title=f.get("summary", ""),
                date=(f.get("updated") or f.get("created") or "")[:10],
                author=(f.get("assignee") or f.get("creator") or {}).get("displayName", ""),
                status=self._norm_status((f.get("status") or {}).get("name", "")),
                desc=(f.get("description") or "")[:500],
                raw=iss,
            ))
        return items
