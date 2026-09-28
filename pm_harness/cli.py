"""cli.py — 串联整个 harness 的命令行入口。

两个出口：
  - run()          一次性全量报告
  - analyze_only() 仅做分析（供 daily_run 复用）

v3 变化：数据源由 config/settings.json 驱动（多 connector 平级互补）；
AI 层由 settings["llm"] 驱动（provider 优先级 shell>ollama>openai）。
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

from . import analyze
from . import report as report_mod
from . import ai as ai_mod
from . import config as config_mod
from . import connectors
from . import miner


def analyze_only(repo: str = "", domain_name: str = None, settings: dict = None) -> dict:
    """只读分析，返回所有中间产物（不写文件）。"""
    settings = settings or config_mod.load_settings()
    domain_name = domain_name or settings.get("domain", "default")

    # --repo 覆盖 git 数据源路径
    if repo:
        settings["sources"]["git"]["repo"] = os.path.abspath(repo)
        settings["sources"]["git"]["enabled"] = True

    domain = config_mod.load_domain(domain_name)

    # 多数据源收集（git / jira / linear / confluence / googledoc 平级互补）
    workitems, source_reports = connectors.collect_from_config(settings)
    if not workitems:
        raise SystemExit("没有任何数据源返回数据：请检查 config/settings.json 的 sources 配置，"
                         "或传入 --repo 指向一个 git 仓库。")

    code_items = [w for w in workitems if w.category == "code_repo"]
    git_repo = settings["sources"]["git"].get("repo", "")
    meta = miner.repo_meta(git_repo) if git_repo and os.path.isdir(f"{git_repo}/.git") else {}
    meta["domain"] = domain.name
    meta["sources"] = [{"name": r.name, "category": r.category, "count": r.count, "note": r.note}
                       for r in source_reports]
    meta["sources_used"] = sorted({w.category for w in workitems})

    # git 指标仅在 code_repo 项上计算
    modules = analyze.group_by_module(code_items, domain)
    roadmap = analyze.build_roadmap(code_items)
    risks = analyze.analyze_risk(code_items, modules, domain)
    sources_used = meta["sources_used"]
    metrics = analyze.compute_metrics(code_items, modules, domain, sources_used)
    metrics["cross_source"] = analyze.analyze_cross_source(workitems, domain)

    return {
        "repo": git_repo, "meta": meta,
        "workitems": workitems, "commits": code_items,  # commits 保持向后兼容
        "modules": modules, "roadmap": roadmap,
        "risks": risks, "metrics": metrics, "domain": domain,
        "settings": settings, "source_reports": source_reports,
    }


def run(repo: str, out_dir: str, use_ai: bool = True, fmt: str = "both",
        domain_name: str = None, settings: dict = None) -> dict:
    settings = settings or config_mod.load_settings()
    print(f"[1/5] 采集数据源（按 settings.json）")
    d = analyze_only(repo, domain_name, settings)
    sr = d["meta"]["sources"]
    print("       -> " + "; ".join(f"{s['name']}={s['count']}" for s in sr)
          + f" ｜ 领域={d['domain'].name}")

    ai_result = None
    llm_cfg = settings.get("llm")
    if use_ai:
        print("[4/5] 调用 AI 层（按 llm 配置选择 provider，不可用则降级）")
        ai_result = ai_mod.run_ai(d["metrics"], d["modules"], d["risks"], llm_cfg)
    else:
        print("[4/5] 跳过 AI 层（--no-ai）")
        ai_result = ai_mod._fallback(d["metrics"], d["risks"], "已通过 --no-ai 跳过。")

    print("[5/5] 渲染报告")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    written = {}
    if fmt in ("md", "both"):
        md = report_mod.build_markdown(d["repo"], d["meta"], d["commits"], d["modules"],
                                       d["roadmap"], d["risks"], d["metrics"], ai_result)
        p = out / f"PM报告-{stamp}.md"
        p.write_text(md, encoding="utf-8")
        written["md"] = str(p)
    if fmt in ("html", "both"):
        htm = report_mod.build_html(d["repo"], d["meta"], d["commits"], d["modules"],
                                    d["roadmap"], d["risks"], d["metrics"], ai_result)
        p = out / f"PM报告-{stamp}.html"
        p.write_text(htm, encoding="utf-8")
        written["html"] = str(p)

    print("完成。输出：")
    for k, v in written.items():
        print(f"  - {k}: {v}")
    return written


def main():
    ap = argparse.ArgumentParser(description="git-pm-harness：多源 AI 项目管理报告")
    ap.add_argument("--repo", default=None, help="git 仓库路径（覆盖 settings 中 git.repo）")
    ap.add_argument("--out", default=None, help="输出目录，默认 <repo>/../pm-report")
    ap.add_argument("--domain", default=None, help="领域词典名（config/domains/<name>.json）")
    ap.add_argument("--settings", default=None, help="配置路径，默认 config/settings.json")
    ap.add_argument("--no-ai", action="store_true", help="跳过 AI 层（仅规则分析）")
    ap.add_argument("--fmt", choices=["md", "html", "both"], default="both")
    args = ap.parse_args()
    settings = config_mod.load_settings(args.settings)
    repo = args.repo or settings["sources"]["git"].get("repo") or os.getcwd()
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(repo)), "pm-report")
    run(repo, out, use_ai=not args.no_ai, fmt=args.fmt,
        domain_name=args.domain, settings=settings)


if __name__ == "__main__":
    main()
