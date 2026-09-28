"""connectors/linear_connector.py — 项目管理工具 Linear（pm_tool）。

真实 GraphQL 调用（https://api.linear.app/graphql），Bearer token 鉴权。
未配置 api_key_env 时跳过。
"""
from __future__ import annotations

import json
import os

from ..model import WorkItem
from .base import BaseConnector


class LinearConnector(BaseConnector):
    source = "linear"
    category = "pm_tool"

    def collect(self) -> list[WorkItem]:
        if self.cfg.get("fixture"):
            return self._from_fixture()
        token = os.environ.get(self.cfg.get("api_key_env", "LINEAR_API_KEY") or "")
        if not token:
            self.skip_reason = f"缺失凭证环境变量 {self.cfg.get('api_key_env')}"
            return []
        team = self.cfg.get("team_key") or ""
        headers = {"Authorization": token, "Content-Type": "application/json"}
        query = """
        query($team: String) {
          issues(filter: {team: {key: {eq: $team}}}) {
            nodes { identifier title description state { name } createdAt updatedAt
                    assignee { name } priority }
          }
        }"""
        try:
            data = self._post(headers, query, team)
        except Exception as e:
            self.skip_reason = f"API 调用失败：{e}"
            return []
        items = []
        for iss in data.get("data", {}).get("issues", {}).get("nodes", []):
            items.append(WorkItem(
                source="linear", category="pm_tool",
                id=iss.get("identifier", ""),
                kind=self._norm_kind(iss.get("title", "")),
                title=iss.get("title", ""),
                date=(iss.get("updatedAt") or iss.get("createdAt") or "")[:10],
                author=(iss.get("assignee") or {}).get("name", ""),
                status=self._norm_status((iss.get("state") or {}).get("name", "")),
                desc=(iss.get("description") or "")[:500],
                raw=iss,
            ))
        return items

    @staticmethod
    def _post(headers, query, team):
        import urllib.request
        payload = {"query": query, "variables": {"team": team}}
        body = json.dumps(payload).encode()
        req = urllib.request.Request("https://api.linear.app/graphql",
                                     data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
