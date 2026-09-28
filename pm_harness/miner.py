"""miner.py — 从 git 提交历史挖掘结构化交付信号（git connector 的底层解析）。

只依赖 git 与标准库。每条提交都保留原始 hash，保证下游结论可溯源。
产出统一的 WorkItem（source=git, category=code_repo）。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import date
from typing import Optional

from .model import WorkItem

# 约定式提交：type(scope): description
CONV_RE = re.compile(
    r"^(?P<type>feat|fix|refactor|test|chore|docs|security|perf|style|build|ci|revert)"
    r"(\((?P<scope>[^)]+)\))?:\s*(?P<desc>.*)$",
    re.IGNORECASE,
)

# 非约定式提交的兜底类型推断（按关键词）
FALLBACK_TYPE = [
    (r"修复|fix|bug", "fix"),
    (r"新增|增加|feat|support", "feat"),
    (r"重构|refactor", "refactor"),
    (r"文档|docs", "docs"),
    (r"安全|security", "security"),
    (r"性能|perf", "perf"),
]


# 历史类名别名，便于平滑迁移（analyze 仍可能引用 Commit）
Commit = WorkItem


def _git(repo: str, args: list[str]) -> str:
    cmd = ["git", "-C", repo] + args
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"git 执行失败: {' '.join(cmd)}\n{proc.stderr}")
    return proc.stdout


def _parse_type_scope(subject: str):
    m = CONV_RE.match(subject.strip())
    if m:
        return m.group("type").lower(), (m.group("scope") or "").lower(), m.group("desc").strip()
    # 兜底
    low = subject.lower()
    for pat, t in FALLBACK_TYPE:
        if re.search(pat, low):
            return t, None, subject.strip()
    return "chore", None, subject.strip()


def get_commits(repo: str) -> list[Commit]:
    """返回结构化的提交列表（按时间从旧到新）。"""
    out = _git(repo, [
        "log", "--all", "--date=short",
        "--pretty=format:%H%x1f%ad%x1f%an%x1f%s",
    ])
    commits: list[Commit] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\x1f")
        if len(parts) < 4:
            continue
        h, d, a, s = parts[0], parts[1], parts[2], parts[3]
        t, scope, desc = _parse_type_scope(s)
        commits.append(WorkItem(
            source="git", category="code_repo",
            id=h[:7], kind=t, title=s.strip(), date=d, author=a,
            scope=scope or "", subject=s.strip(), desc=desc,
        ))
    # 按日期升序（git log 默认从新到旧，反转）
    commits.reverse()
    return commits


def get_numstat(repo: str) -> dict[str, dict]:
    """聚合每提交的增删行数与文件数。"""
    out = _git(repo, [
        "log", "--all", "--pretty=format:%H", "--numstat",
    ])
    stats: dict[str, dict] = {}
    cur = None
    for raw in out.splitlines():
        if raw.strip() == "":
            continue
        if "\t" not in raw and not raw.startswith(("+", "-")) and len(raw) == 40:
            # 新提交 hash 行（full hash）
            cur = raw[:7]
            stats.setdefault(cur, {"ins": 0, "del": 0, "files": 0})
            continue
        # numstat 行： +ins\t-del\tfile  （二进制文件为 -\t-）
        m = re.match(r"^(\d+|\-)\t(\d+|\-)\t", raw)
        if m and cur:
            a, b = m.group(1), m.group(2)
            ins = int(a) if a != "-" else 0
            dele = int(b) if b != "-" else 0
            stats[cur]["ins"] += ins
            stats[cur]["del"] += dele
            stats[cur]["files"] += 1
    return stats


def enrich_with_numstat(commits: list[Commit], repo: str) -> None:
    stats = get_numstat(repo)
    for c in commits:
        if c.hash in stats:
            c.insertions = stats[c.hash]["ins"]
            c.deletions = stats[c.hash]["del"]
            c.files = stats[c.hash]["files"]


def repo_meta(repo: str) -> dict:
    """读取仓库基本信息：项目标识（package.json / project.config.json）与首末提交日期。

    只读取通用工程元数据里的**项目名与描述**，不采集任何凭证或标识符（如 appid）。
    """
    meta: dict[str, str] = {}
    for cand, keys in (("package.json", ("name", "description")),
                       ("project.config.json", ("projectname", "description"))):
        p = f"{repo}/{cand}"
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            continue
        if isinstance(cfg, dict):
            if cfg.get(keys[0]):
                meta["projectname"] = str(cfg[keys[0]])
            if cfg.get(keys[1]):
                meta["description"] = str(cfg[keys[1]])
        if meta.get("projectname"):
            break
    try:
        first = _git(repo, ["log", "--reverse", "--date=short", "--pretty=format:%ad"]).splitlines()[0]
        last = _git(repo, ["log", "-1", "--date=short", "--pretty=format:%ad"]).strip()
        meta["first_commit"] = first
        meta["last_commit"] = last
    except Exception:
        pass
    return meta
