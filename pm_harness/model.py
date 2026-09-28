"""model.py — 统一工作项模型 WorkItem。

设计意图：harness 支持多数据源（代码仓库 / 项目管理工具 / 文档工具）。
所有 connector 都把自己的原始记录归一化为 WorkItem，下游 analyze/report
只消费 WorkItem，不关心来源。

git 提交、Jira issue、Linear issue、Confluence/Google Doc 修订，落到同一
结构，靠 source / category / kind / status 区分语义：
  - category: code_repo | pm_tool | doc_tool   （用户要求的分类）
  - source:   git | jira | linear | confluence | googledoc
  - kind:     归一化类型（feat/fix/story/epic/req_change/doc/update/security/revert...）
  - status:   pm/doc 工具里的状态（todo/in_progress/done/changed/reopened）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WorkItem:
    source: str            # git | jira | linear | confluence | googledoc
    category: str          # code_repo | pm_tool | doc_tool
    id: str                # 来源内唯一 ID（git 短 hash / JIRA-123 / DOC-xx）
    kind: str              # 归一化类型
    title: str
    date: str              # 事件日期 ISO（提交日 / issue 创建或变更日 / 文档修订日）
    author: str = ""
    status: Optional[str] = None      # pm/doc 工具状态；code_repo 恒为 done
    churn: int = 0         # code_repo：增删行数之和
    files: int = 0         # code_repo：改动文件数
    scope: str = ""        # 原提交 scope（仅 code_repo 有意义）
    subject: str = ""      # 原提交 subject / issue 标题
    desc: str = ""         # 原提交描述 / issue 正文摘要
    insertions: int = 0
    deletions: int = 0
    raw: dict = field(default_factory=dict)

    # —— 保持与原 Commit 的兼容语义，便于 analyze 复用 ——
    @property
    def is_revert(self) -> bool:
        return self.kind == "revert" or self.subject.lower().startswith("revert")

    @property
    def is_security(self) -> bool:
        return self.kind == "security" or "security" in (self.scope or "").lower()

    @property
    def type(self) -> str:
        """兼容旧代码对 c.type 的引用。"""
        return self.kind

    @property
    def hash(self) -> str:
        """兼容旧代码对 c.hash（git 短哈希）的引用，映射为 id。"""
        return self.id

    @classmethod
    def from_dict(cls, d: dict) -> "WorkItem":
        return cls(
            source=d.get("source", "git"),
            category=d.get("category", "code_repo"),
            id=str(d.get("id", "")),
            kind=d.get("kind", "chore"),
            title=d.get("title", ""),
            date=d.get("date", ""),
            author=d.get("author", ""),
            status=d.get("status"),
            churn=int(d.get("churn", 0)),
            files=int(d.get("files", 0)),
            scope=d.get("scope", ""),
            subject=d.get("subject", ""),
            desc=d.get("desc", ""),
            insertions=int(d.get("insertions", 0)),
            deletions=int(d.get("deletions", 0)),
            raw=d.get("raw", {}),
        )
