"""ai.py — 可选 LLM 层：合成英文执行摘要与下季度计划。

不再硬编码 Ollama，改用 llm.resolve_provider 按配置选择 provider
（优先级 shell > ollama > openai）。全部不可用时降级为模板（仍基于真实数字），
保证 harness 始终可跑、结论诚实。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from . import llm as llm_mod


@dataclass
class AIResult:
    available: bool
    model: str
    exec_summary_en: str
    next_quarter_plan: list[str]
    note: str = ""


def _cross_blob(metrics: dict) -> str:
    cs = metrics.get("cross_source")
    if not cs:
        return ""
    lines = []
    if cs.get("requirements_total"):
        lines.append(f"- 需求总数={cs['requirements_total']}，状态分布={cs['status_breakdown']}，完成率={cs['progress_done_ratio']}")
    if cs.get("requirement_changes"):
        lines.append(f"- 需求变更事件 {len(cs['requirement_changes'])} 条（如 {cs['requirement_changes'][0]['id']}）")
    if cs.get("spec_changes"):
        lines.append(f"- 文档/规格变更 {len(cs['spec_changes'])} 条（如 {cs['spec_changes'][0]['id']}）")
    if cs.get("story_links"):
        lines.append(f"- git 提交中引用 PM 单号的可追溯链接 {cs['story_links']} 条")
    return "\n".join(lines)


def build_prompt(metrics: dict, modules: dict, risks: list) -> str:
    out = metrics["output"]
    mod_lines = "\n".join(
        f"- {mv.cn}: {len(mv.commits)} 提交 (feat {len(mv.feat)}/fix {len(mv.fix)}), churn {mv.churn}"
        for mv in modules.values()
    )
    risk_lines = "\n".join(f"- [{r['severity']}] {r['title']}" for r in risks)
    cross = _cross_blob(metrics)
    cross_block = f"\nCROSS-SOURCE MONITORING (real):\n{cross}\n" if cross else ""
    return f"""You are a Senior Program Manager writing an internal delivery review.

OUTPUT METRICS (real):
- commits={out['commit_total']}, feat={out['feat_count']}, fix={out['fix_count']}, security={out['security_count']}
- modules touched={out['module_count']}, total churn={out['total_churn']}, active days={out['active_days']}, span={out['date_span']}
{cross_block}
MODULE BREAKDOWN:
{mod_lines}

RISK REGISTER:
{risk_lines}

Task 1: Write a concise English executive status (max 130 words) for an Amazon-style PM interview:
what was delivered, how AI/automation was used in delivery, and the one biggest risk you owned.
Task 2: Propose a prioritized next-quarter plan as 3 bullet points (each <= 25 words),
each tied to a real risk above. Respond in strict JSON:
{{"exec_summary": "...", "next_quarter_plan": ["...","...","..."]}}"""


def run_ai(metrics: dict, modules: dict, risks: list, llm_cfg: Optional[dict] = None) -> AIResult:
    provider = llm_mod.resolve_provider(llm_cfg)
    if provider is None:
        return _fallback(metrics, risks, "未配置可用 LLM provider（shell/ollama/openai 均不可用），已用模板降级。")
    try:
        raw = provider.generate(build_prompt(metrics, modules, risks))
        js = _extract_json(raw)
        if js:
            return AIResult(
                available=True, model=provider.name,
                exec_summary_en=js.get("exec_summary", ""),
                next_quarter_plan=js.get("next_quarter_plan", []),
                note=f"由 LLM provider「{provider.name}」生成。",
            )
        return AIResult(available=True, model=provider.name, exec_summary_en=raw,
                        next_quarter_plan=[], note="模型未返回标准 JSON，已整段引用。")
    except Exception as e:
        return _fallback(metrics, risks, f"LLM provider「{provider.name}」调用失败：{e}。已用模板降级。")


def _extract_json(text: str) -> dict:
    try:
        s = text.find("{")
        e = text.rfind("}")
        if s >= 0 and e > s:
            return json.loads(text[s:e + 1])
    except Exception:
        pass
    return {}


def _fallback(metrics: dict, risks: list, note: str) -> AIResult:
    out = metrics["output"]
    sev_rank = {"高": 3, "中": 2, "低": 1}
    top = max(risks, key=lambda r: sev_rank.get(r["severity"], 0)) if risks else None
    top_risk = top["title"] if top else "无明显高风险项"
    summary = (
        f"Delivered a WeChat fitness mini-program end-to-end as a solo developer, "
        f"using an AI-driven delivery harness that auto-mines git history as the single source of truth "
        f"(no PM tool). Shipped {out['feat_count']} features across {out['module_count']} modules in "
        f"{out['active_days']} active days ({out['date_span']}), with {out['security_count']} security-hardening "
        f"changes and {out['fix_count']} fixes. The biggest risk I owned: {top_risk}."
    )
    plan = [
        "Shift security threat-modeling left into requirements/architecture phase (addresses R2).",
        "Stand up permanent regression gates for payment & workout-loop before each release (addresses R3).",
        "Adopt smaller single-purpose commits + ADR to cut revert churn (addresses R1/R5).",
    ]
    return AIResult(available=False, model="template", exec_summary_en=summary,
                    next_quarter_plan=plan, note=note)
