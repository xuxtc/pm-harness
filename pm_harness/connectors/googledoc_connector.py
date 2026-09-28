"""connectors/googledoc_connector.py — 文档工具 Google Docs/Drive（doc_tool）。

通过 Google Drive API v3 列出指定文件夹的文档修订，监控规格/需求文档变更。
鉴权：creds_env 指向一个含 access_token 的 JSON（{"access_token": "..."}），
或环境变量本身即 token。需要用户自行用 OAuth/Service Account 取得 token
（harness 不内置 google 客户端库，保持零依赖）。缺失 token 时跳过。
"""
from __future__ import annotations

import json
import os

from ..model import WorkItem
from .base import BaseConnector


class GoogleDocConnector(BaseConnector):
    source = "googledoc"
    category = "doc_tool"

    def _token(self) -> str:
        env = self.cfg.get("creds_env", "GOOGLE_CREDS_JSON") or ""
        raw = os.environ.get(env, "")
        if not raw:
            return ""
        try:
            return json.loads(raw).get("access_token", raw)
        except Exception:
            return raw

    def collect(self) -> list[WorkItem]:
        if self.cfg.get("fixture"):
            return self._from_fixture()
        token = self._token()
        if not token:
            self.skip_reason = f"缺失凭证环境变量 {self.cfg.get('creds_env')}"
            return []
        folder = self.cfg.get("folder_id") or "root"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        q = f"'{folder}' in parents and mimeType='application/vnd.google-apps.document'"
        url = "https://www.googleapis.com/drive/v3/files?pageSize=200&fields=files(id,name,modifiedTime,owners)&q=" + __import__("urllib.request").quote(q)
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.load(r)
        except Exception as e:
            self.skip_reason = f"API 调用失败：{e}"
            return []
        items = []
        for f in data.get("files", []):
            items.append(WorkItem(
                source="googledoc", category="doc_tool",
                id=f.get("id", ""),
                kind="doc",
                title=f.get("name", ""),
                date=(f.get("modifiedTime") or "")[:10],
                author=(f.get("owners") or [{}])[0].get("displayName", ""),
                status="updated",
                desc="",
                raw=f,
            ))
        return items
