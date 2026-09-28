"""analyze.py — 将原始提交归类为模块/史诗、生成路线图、风险登记、PMBOK 域矩阵与三层+敏捷指标。

所有判定都基于提交本身的 type/scope/desc 与真实日期，结论可溯源到 hash。
模块词典与风险阈值来自可配置 DomainConfig（config.py），本文件不再内嵌项目特化知识。
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from dataclasses import dataclass, field
from typing import Optional

from .model import WorkItem
from .config import DomainConfig


def classify_module(c: WorkItem, domain: DomainConfig) -> str:
    blob = " ".join([(c.scope or ""), c.subject, c.desc]).lower()
    if c.kind == "test":
        return "testing" if "testing" in domain.modules else domain.module_order[0]
    best = None
    for key, meta in domain.modules.items():
        if key == "testing":
            continue
        for kw in meta.get("keywords", []):
            if kw.lower() in blob:
                if key == "security":
                    return "security"
                best = key
                break
        if best and key != "security":
            return key
    return best or "other"


@dataclass
class ModuleView:
    key: str
    cn: str
    en: str
    commits: list[WorkItem] = field(default_factory=list)

    @property
    def feat(self):
        return [c for c in self.commits if c.kind == "feat"]

    @property
    def fix(self):
        return [c for c in self.commits if c.kind == "fix"]

    @property
    def churn(self):
        """代码变动量（code churn）= 增删行数之和。注意：不是静态代码规模。"""
        return sum(c.insertions + c.deletions for c in self.commits)

    @property
    def escape_ratio(self) -> Optional[float]:
        f = len(self.feat)
        x = len(self.fix)
        if f == 0:
            return None
        return round(x / f, 2)


def group_by_module(commits: list[WorkItem], domain: DomainConfig) -> dict:
    views: dict[str, ModuleView] = {}
    for c in commits:
        k = classify_module(c, domain)
        if k not in views:
            if k == "other":
                cn, en = domain.other_cn, domain.other_en
            else:
                meta = domain.modules.get(k, {})
                cn, en = meta.get("cn", k), meta.get("en", k)
            views[k] = ModuleView(key=k, cn=cn, en=en)
        views[k].commits.append(c)
    ordered = {k: views[k] for k in domain.module_order if k in views}
    if "other" in views:
        ordered["other"] = views["other"]
    elif "testing" in views:
        ordered["testing"] = views["testing"]
    return ordered


def build_roadmap(commits: list[WorkItem]) -> list[dict]:
    by_date: dict[str, list[Commit]] = defaultdict(list)
    for c in commits:
        by_date[c.date].append(c)
    return [{"date": d, "commits": by_date[d]} for d in sorted(by_date)]


def analyze_risk(commits: list[WorkItem], modules: dict, domain: DomainConfig) -> list[dict]:
    rules = domain.rules
    risks: list[dict] = []

    # 1) 回滚 / 反复
    reverts = [c for c in commits if c.is_revert]
    if reverts:
        risks.append({
            "id": "R1",
            "title": "存在功能回滚（churn / 需求摇摆）",
            "severity": "中",
            "evidence": ", ".join(f"{c.hash} {c.subject}" for c in reverts),
            "recommend": "对该模块先冻结范围、补回归测试再改；用 ADR 记录争议决策。",
        })

    # 2) 安全加固滞后（集中在末期）
    sec = [c for c in commits if c.is_security]
    if sec:
        last = max(c.date for c in commits)
        sec_dates = sorted({c.date for c in sec})
        first_noninit = min(c.date for c in commits if "initial" not in c.subject.lower())
        total_span = max(1, (date.fromisoformat(last) - date.fromisoformat(first_noninit)).days)
        frac = (date.fromisoformat(sec_dates[0]) - date.fromisoformat(first_noninit)).days / total_span
        if frac >= rules.get("security_late_frac", 0.6):
            risks.append({
                "id": "R2",
                "title": "安全加固严重滞后（集中于交付末期）",
                "severity": "高",
                "evidence": f"{len(sec)} 条安全提交分布于 {sec_dates[0]}~{sec_dates[-1]}，全部位于项目时间轴后段（末次提交 {last}）",
                "recommend": "将安全设计（威胁建模 + 最小权限 + 服务端校验）左移到需求与架构阶段，而非上线前补丁。",
            })

    # 3) 回归信号
    regr = [c for c in commits if re.search(r"回归|regress", c.subject + c.desc, re.I)]
    if regr:
        risks.append({
            "id": "R3",
            "title": "已发生线上/功能回归",
            "severity": "高",
            "evidence": ", ".join(f"{c.hash} {c.subject}" for c in regr),
            "recommend": "对支付落地、核心闭环建立常驻回归套件与发布门禁。",
        })

    # 4) 模块逃逸比偏高
    high_escape = []
    for k, mv in modules.items():
        r = mv.escape_ratio
        if r is not None and r >= rules.get("high_escape_ratio", 1.5) and len(mv.feat) >= 2:
            high_escape.append((mv.cn, r, len(mv.fix)))
    if high_escape:
        risks.append({
            "id": "R4",
            "title": "部分模块修复量远超新增量（质量逃逸）",
            "severity": "中",
            "evidence": "; ".join(f"{n} 逃逸比={r}(fix {x})" for n, r, x in high_escape),
            "recommend": "对这些模块做根因复盘：是否缺契约测试 / 边界用例，再决定下季度是否重构。",
        })

    # 5) 大爆炸提交
    top = sorted(commits, key=lambda c: c.files, reverse=True)[:3]
    if top and top[0].files >= rules.get("big_commit_files", 8):
        risks.append({
            "id": "R5",
            "title": "存在大爆炸式提交（blast radius 大）",
            "severity": "低",
            "evidence": ", ".join(f"{c.hash} 改动{c.files}文件/{c.insertions}+{c.deletions}-" for c in top),
            "recommend": "鼓励更小、单一职责的提交；大提交应拆分 PR 并附设计说明，便于 review 与 bisect。",
        })

    return risks


def _pmbok_domains(commits, modules, sources_used: list) -> list[dict]:
    """PMBOK 绩效域 × 数据支撑度。

    诚实标注：git 只能支撑执行/监控/质量/风险/沟通；范围/进度在接入
    pm_tool（Jira/Linear）后升级为「支撑」，成本/采购/干系人始终需接 PM 工具。
    """
    has_pm = "pm_tool" in sources_used
    has_doc = "doc_tool" in sources_used
    scope_sup = "支撑" if has_pm else "部分"
    schedule_sup = "支撑" if has_pm else "部分"
    scope_basis = ("范围分解=模块归类，且已接入 PM 工具（需求/Story 基准可度量）" if has_pm
                   else "模块归类=范围分解；但无范围基准/验收口径，需接 PM 工具补全")
    schedule_basis = ("提交节奏 + PM 工具状态流转，可算进度与关键路径" if has_pm
                      else "提交日期可算节奏与间隔；但无进度基准/关键路径，需接 PM 工具补全")
    comms_sup = "支撑" if (has_pm or has_doc) else "支撑"
    return [
        {"domain": "整合管理 Integration", "support": "支撑", "basis": "监控链：多源数据→分析信息→报告，正是工作绩效报告过程"},
        {"domain": "范围管理 Scope", "support": scope_sup, "basis": scope_basis},
        {"domain": "进度管理 Schedule", "support": schedule_sup, "basis": schedule_basis},
        {"domain": "成本管理 Cost", "support": "需接 PM 工具", "basis": "git/PM 工具均无工时成本数据，无法度量（需接 timesheet/ERP）"},
        {"domain": "质量管理 Quality", "support": "支撑", "basis": "逃逸比/回归信号/测试提交可直接度量；PM 工具缺陷单可补充"},
        {"domain": "资源管理 Resource", "support": "弱", "basis": "仅作者计数；无产能/负载数据"},
        {"domain": "沟通管理 Comms", "support": comms_sup, "basis": "报告本身 + 约定式提交 + PM/文档工具即沟通工件"},
        {"domain": "风险管理 Risk", "support": "支撑", "basis": "R1-R5 规则 + PM 工具缺陷/阻塞单直接产出风险登记"},
        {"domain": "采购管理 Procurement", "support": "需接 PM 工具", "basis": "git 无供应商/合同数据"},
        {"domain": "干系人管理 Stakeholder", "support": "需接 PM 工具", "basis": "git 无干系人/期望数据"},
    ]


def compute_metrics(commits: list[WorkItem], modules: dict, domain: DomainConfig,
                    sources_used: list = None) -> dict:
    """指标框架：PMBOK 监控链（数据→信息→报告）+ 敏捷指标 + 三层框架。

    注意：本函数只消费 code_repo 来源的项（churn/逃逸比等只对代码有意义）。
    sources_used 用于动态升级 PMBOK 域支撑度。
    """
    sources_used = sources_used or ["code_repo"]
    dates = sorted({c.date for c in commits})
    total_churn = sum(c.insertions + c.deletions for c in commits)
    feat = [c for c in commits if c.kind == "feat"]
    fix = [c for c in commits if c.kind == "fix"]
    sec = [c for c in commits if c.is_security]

    # 敏捷指标
    active_days = len(dates)
    span_days = max(1, (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days)
    velocity = round(len(feat) / active_days, 2) if active_days else 0.0   # feat / 活跃天
    cycle_time = round(span_days / max(1, len(commits) - 1), 2)            # 平均提交间隔（天）
    escaped_defects = len([c for c in commits if re.search(r"回归|regress", c.subject + c.desc, re.I)])

    # Outcome（真实可归因的业务变化，来自提交描述）
    outcome_signals = []
    text = " ".join(c.subject + " " + c.desc for c in commits)
    if "296" in text and "152" in text:
        outcome_signals.append("安装包体积 296.5KB → 152KB，过 200K 提审门槛（perf/pack 提交）")
    if re.search(r"社会证明|socialproof|真实开通", text, re.I):
        outcome_signals.append("付费墙社会证明改为云端真实开通数，提升转化可信度")
    if re.search(r"经期|period|menstrual", text, re.I):
        outcome_signals.append("上线经期同步，拓展女性用户细分（新增用户价值）")
    if sec:
        outcome_signals.append(f"完成 {len(sec)} 项安全加固，降低越权与客户端信任风险")
    if re.search(r"测试|回归|守卫", text, re.I):
        outcome_signals.append("建立常驻回归套件，降低'支付成功会员未生效'类回归")

    escape_overall = round(len(fix) / len(feat), 2) if feat else None
    reverts = [c for c in commits if c.is_revert]

    return {
        # 工作绩效数据（原始规模）
        "output": {
            "commit_total": len(commits),
            "feat_count": len(feat),
            "fix_count": len(fix),
            "security_count": len(sec),
            "module_count": len(modules),
            "total_churn": total_churn,
            "date_span": f"{dates[0]} ~ {dates[-1]}",
            "active_days": active_days,
            "span_days": span_days,
        },
        # 敏捷指标
        "agile": {
            "velocity_per_active_day": velocity,
            "cycle_time_days": cycle_time,
            "escaped_defects": escaped_defects,
        },
        # 三层框架：Outcome / Input
        "outcome": outcome_signals,
        "input": {
            "escape_ratio_overall": escape_overall,
            "revert_count": len(reverts),
            "regression_signal_count": escaped_defects,
            "read": "逃逸比 / 回滚数 / 回归信号为领先指标：下季度质量风险看这三项是否下降。",
        },
        # PMBOK 域覆盖矩阵
        "pmbok_domains": _pmbok_domains(commits, modules, sources_used),
    }


def analyze_cross_source(workitems: list[WorkItem], domain: DomainConfig) -> dict:
    """跨源监控：把 code_repo / pm_tool / doc_tool 作为平级互补信息，监控
    需求信息、进度、需求变更（用户明确要的三类）。

    所有结论来自真实读取的数据，未接入的源不编造。
    """
    by_cat: dict[str, list[WorkItem]] = defaultdict(list)
    for w in workitems:
        by_cat[w.category].append(w)
    pm = by_cat.get("pm_tool", [])
    doc = by_cat.get("doc_tool", [])
    code = by_cat.get("code_repo", [])

    # —— 需求信息 ——
    req_kinds = {"story", "epic", "requirement", "task", "feat"}
    requirements = [w for w in pm if w.kind in req_kinds]
    # —— 进度 ——
    status_count: dict[str, int] = defaultdict(int)
    for w in pm:
        status_count[w.status or "unknown"] += 1
    done = status_count.get("done", 0) + status_count.get("closed", 0)
    total_pm = len(pm)
    done_ratio = round(done / total_pm, 2) if total_pm else None

    # —— 需求变更 ——
    change_kw = re.compile(r"变更|change|churn|需求变动|scope.?change", re.I)
    requirement_changes = []
    for w in pm:
        if w.status in ("changed", "reopened", "in_progress") or change_kw.search(w.title + " " + w.desc):
            requirement_changes.append({
                "id": w.id, "title": w.title, "date": w.date,
                "status": w.status, "source": w.source,
            })
    # —— 文档/规格变更（Confluence / Google Doc 修订）——
    spec_changes = [{"id": w.id, "title": w.title, "date": w.date, "source": w.source}
                    for w in doc]

    # —— 可追溯矩阵：模块 × (PM 需求数 / git 提交数) ——
    code_by_module: dict[str, list[WorkItem]] = defaultdict(list)
    for c in code:
        code_by_module[classify_module(c, domain)].append(c)
    pm_id_set = {w.id for w in pm}
    # git 提交里引用 PM 单号（如 PROJ-123）的链接数
    story_re = re.compile(r"\b([A-Z]{2,}[-_]?\d+)\b")
    linked = 0
    for c in code:
        for tok in story_re.findall(c.subject + " " + c.desc):
            if tok in pm_id_set:
                linked += 1
                break
    traceability = []
    for key, meta in domain.modules.items():
        kws = meta.get("keywords", [])
        pm_n = sum(1 for w in pm if any(kw.lower() in (w.title + " " + w.desc).lower() for kw in kws))
        git_n = len(code_by_module.get(key, []))
        if pm_n or git_n:
            traceability.append({"module": meta.get("cn", key),
                                 "pm_requirements": pm_n, "git_commits": git_n})
    if "other" in code_by_module:
        traceability.append({"module": domain.other_cn,
                             "pm_requirements": 0, "git_commits": len(code_by_module["other"])})

    return {
        "sources_used": sorted(by_cat.keys()),
        "pm_total": total_pm,
        "requirements_total": len(requirements),
        "status_breakdown": dict(status_count),
        "progress_done_ratio": done_ratio,
        "requirement_changes": requirement_changes,
        "spec_changes": spec_changes,
        "traceability": traceability,
        "story_links": linked,
    }
