"""daily_run.py — 持续运行入口：每日生成 PM 日报 + 维护趋势时序。

设计要点：
  - 趋势文件 trends.json / trends.csv 每天追加一条，保证时间序列连续。
  - 阈值触发：仅当「当日有新提交」或「风险数/逃逸比漂移」或 --force 时，
    才生成完整 PM 报告，避免无变化日刷屏。
  - 始终产出一份轻量 DAILY-YYYY-MM-DD.md 摘要（含与上次对比 diff），便于每天快速看。
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, date
from pathlib import Path

from pm_harness import cli
from pm_harness import ai as ai_mod
from pm_harness import report as report_mod
from pm_harness import config as config_mod


def _load_trends(path: str) -> list:
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_trends(path: str, trends: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trends, f, ensure_ascii=False, indent=2)


def _save_csv(path: str, trends: list) -> None:
    header = ["date", "commit_total", "feat", "fix", "escape_ratio", "risk_count", "churn", "velocity"]
    lines = [",".join(header)]
    for t in trends:
        lines.append(",".join(str(t.get(k, "")) for k in header))
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="git-pm-harness 每日运行")
    ap.add_argument("--repo", default=None, help="git 仓库路径（覆盖 settings.git.repo）")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports"))
    ap.add_argument("--domain", default=None)
    ap.add_argument("--settings", default=None, help="配置路径，默认 config/settings.json")
    ap.add_argument("--no-ai", action="store_true")
    ap.add_argument("--fmt", choices=["md", "html", "both"], default="both")
    ap.add_argument("--force", action="store_true", help="强制生成完整报告（忽略阈值）")
    args = ap.parse_args()

    settings = config_mod.load_settings(args.settings)
    repo = args.repo or settings["sources"]["git"].get("repo")
    if not repo:
        ap.error("缺少 --repo，且 settings.json 未配置 git.repo；请传入目标仓库路径。")
    domain = args.domain or settings.get("domain", "default")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    trends_path = out / "trends.json"
    csv_path = out / "trends.csv"

    print(f"[daily] 分析仓库：{repo}（领域={domain}）")
    d = cli.analyze_only(repo, domain, settings)
    m = d["metrics"]["output"]
    ag = d["metrics"]["agile"]
    risks = d["risks"]
    today = date.today().isoformat()

    trends = _load_trends(str(trends_path))
    last = trends[-1] if trends else None
    inp = d["metrics"]["input"]

    new_commits = (last is None) or (m["commit_total"] != last.get("commit_total"))
    drift = (last is None) or (len(risks) != last.get("risk_count"))
    generate = args.force or new_commits or drift

    record = {
        "date": today,
        "commit_total": m["commit_total"],
        "feat": m["feat_count"],
        "fix": m["fix_count"],
        "escape_ratio": inp["escape_ratio_overall"],
        "risk_count": len(risks),
        "risk_ids": [r["id"] for r in risks],
        "churn": m["total_churn"],
        "velocity": ag["velocity_per_active_day"],
        "new": bool(new_commits),
    }
    if trends and trends[-1].get("date") == today:
        trends[-1] = record          # 同日重跑：更新而非重复追加
    else:
        trends.append(record)
    _save_trends(str(trends_path), trends)
    _save_csv(str(csv_path), trends)
    print(f"[daily] 趋势已更新：共 {len(trends)} 条 ｜ 今日新增提交={new_commits} 漂移={drift}")

    # 轻量 DAILY 摘要（始终写）
    diff_lines = []
    if last:
        diff_lines.append(f"- 提交总数：{last.get('commit_total')} → {m['commit_total']}（+{m['commit_total']-last.get('commit_total',0)}）")
        diff_lines.append(f"- 风险数：{last.get('risk_count')} → {len(risks)}")
        diff_lines.append(f"- 逃逸比：{last.get('escape_ratio')} → {inp['escape_ratio_overall']}")
        last_risk_ids = last.get("risk_ids")
        if last_risk_ids is not None:
            new_risk_ids = [r["id"] for r in risks if r["id"] not in last_risk_ids]
            if new_risk_ids:
                diff_lines.append(f"- 新增风险：{', '.join(new_risk_ids)}")
    else:
        diff_lines.append("- 首发基线记录，无历史可对比")
    daily_md = (
        f"# 每日 PM 摘要 {today}\n\n"
        f"- 仓库：`{args.repo}` ｜ 领域：`{d['domain'].name}`\n"
        f"- 跨度：{m['date_span']} ｜ 活跃 {m['active_days']} 天 ｜ 提交 {m['commit_total']}\n"
        f"- Velocity：{ag['velocity_per_active_day']}/天 ｜ Cycle time：{ag['cycle_time_days']}天 ｜ Escaped defects：{ag['escaped_defects']}\n\n"
        f"## 与上次对比\n" + "\n".join(diff_lines) + "\n\n"
        f"## 结论\n"
        f"{'已生成完整 PM 报告（detected change）。' if generate else '无新增提交且指标无漂移，跳过完整报告生成（趋势已记录）。'}\n"
    )
    (out / f"DAILY-{today}.md").write_text(daily_md, encoding="utf-8")
    print(f"[daily] DAILY 摘要：{out / f'DAILY-{today}.md'}")

    if generate:
        ai_result = ai_mod.run_ai(d["metrics"], d["modules"], risks, settings.get("llm")) if not args.no_ai \
            else ai_mod._fallback(d["metrics"], risks, "已通过 --no-ai 跳过。")
        stamp = datetime.now().strftime("%Y%m%d")
        if args.fmt in ("md", "both"):
            p = out / f"PM报告-{stamp}.md"
            p.write_text(report_mod.build_markdown(d["repo"], d["meta"], d["commits"], d["modules"],
                         d["roadmap"], risks, d["metrics"], ai_result), encoding="utf-8")
            print(f"[daily] 完整报告(md)：{p}")
        if args.fmt in ("html", "both"):
            p = out / f"PM报告-{stamp}.html"
            p.write_text(report_mod.build_html(d["repo"], d["meta"], d["commits"], d["modules"],
                         d["roadmap"], risks, d["metrics"], ai_result), encoding="utf-8")
            print(f"[daily] 完整报告(html)：{p}")
    else:
        print("[daily] 跳过完整报告（阈值未触发）。")


if __name__ == "__main__":
    main()
