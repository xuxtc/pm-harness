"""connectors/git_connector.py — 代码仓库数据源（code_repo）。

复用 miner 的 git 解析；repo 来自 cfg["repo"]（cli 会用 --repo 覆盖注入）。
"""
from __future__ import annotations

import os

from .. import miner
from ..model import WorkItem
from .base import BaseConnector


class GitConnector(BaseConnector):
    source = "git"
    category = "code_repo"

    def collect(self) -> list[WorkItem]:
        if self.cfg.get("fixture"):
            return self._from_fixture()
        repo = self.cfg.get("repo") or ""
        if not repo or not os.path.isdir(f"{repo}/.git"):
            self.skip_reason = f"git 仓库路径不可用：{repo}"
            return []
        commits = miner.get_commits(repo)
        miner.enrich_with_numstat(commits, repo)
        return commits
