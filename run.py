"""run.py — 一键对默认工程跑出全量 PM 报告。

用法：
    python run.py                  # 默认指向 settings.json 的 git.repo + default 词典，输出到 ./output
    python run.py --no-ai          # 仅规则分析
    python run.py --repo <path> --domain default   # 分析其他仓库/通用词典
    python run.py --settings config/sources.demo.json  # 用含多数据源的演示配置
"""
from __future__ import annotations

import argparse
import os

from pm_harness import cli
from pm_harness import config as config_mod

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=None, help="git 仓库路径（覆盖 settings.git.repo）")
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--domain", default=None)
    ap.add_argument("--settings", default=None, help="配置路径，默认 config/settings.json")
    ap.add_argument("--no-ai", action="store_true")
    ap.add_argument("--fmt", choices=["md", "html", "both"], default="both")
    args = ap.parse_args()
    settings = config_mod.load_settings(args.settings)
    repo = args.repo or settings["sources"]["git"].get("repo")
    if not repo:
        ap.error("缺少 --repo，且 settings.json 未配置 git.repo；请传入目标仓库路径。")
    cli.run(repo, args.out, use_ai=not args.no_ai, fmt=args.fmt,
            domain_name=args.domain, settings=settings)


if __name__ == "__main__":
    main()
