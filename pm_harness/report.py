"""report.py — 将分析结果渲染为 Markdown 与自包含 HTML（浅色主题）。

章节按 PMBOK 监控过程组组织：
  一、工作绩效数据（Work Performance Data）  — 原始规模
  二、工作绩效信息（Work Performance Information）— 模块/风险/指标分析
  三、工作绩效报告（Work Performance Reports）— 域覆盖矩阵 + AI 摘要
"""
from __future__ import annotations

import html
from datetime import datetime

from .analyze import ModuleView  # noqa


def _esc(s) -> str:
    return html.escape(str(s))


def build_markdown(repo, meta, commits, modules, roadmap, risks, metrics, ai) -> str:
    o = metrics["output"]
    ag = metrics["agile"]
    L = []
    L.append("# pm-harness · AI 项目管理报告")
    L.append("")
    L.append(f"- 仓库：`{repo}`")
    if meta.get("projectname"):
        L.append(f"- 项目标识：`{meta['projectname']}`")
    if meta.get("domain"):
        L.append(f"- 领域词典：`{meta['domain']}`")
    L.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    L.append(f"- 提交跨度：{o['date_span']}（活跃 {o['active_days']} 天，共 {o['commit_total']} 提交）")
    srcs = meta.get("sources", [])
    src_line = "、".join(f"{s['name']}({s['category']},{s['count']})" for s in srcs) or "无"
    L.append(f"- 已接入数据源（平级互补）：{src_line}")
    L.append("")

    L.append("## 一、工作绩效数据（Output / 原始规模）")
    L.append("")
    L.append(f"- 提交总数：**{o['commit_total']}** ｜ 新增 feat：**{o['feat_count']}** ｜ 修复 fix：**{o['fix_count']}** ｜ 安全：**{o['security_count']}**")
    L.append(f"- 触及模块：**{o['module_count']}** ｜ 代码变动量 Churn：**{o['total_churn']}** 行 ｜ 活跃：**{o['active_days']}** 天（跨度 {o['span_days']} 天）")
    er_all = metrics['input']['escape_ratio_overall']
    L.append(f"- 整体逃逸比 fix/feat：**{er_all if er_all is not None else '-'}** ｜ 回滚：**{metrics['input']['revert_count']}** ｜ 回归信号：**{metrics['input']['regression_signal_count']}**")
    L.append("")

    L.append("## 二、工作绩效信息（分析转化）")
    L.append("")
    L.append("### 2.1 模块矩阵（Epic 视图）")
    L.append("")
    L.append("| 模块 | 提交 | feat | fix | 逃逸比 | Churn(变动量) |")
    L.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for mv in modules.values():
        er = mv.escape_ratio if mv.escape_ratio is not None else "-"
        L.append(f"| {mv.cn} ({mv.en}) | {len(mv.commits)} | {len(mv.feat)} | {len(mv.fix)} | {er} | {mv.churn} |")
    L.append("")
    L.append("> Churn = 增删行数之和（代码变动量），非静态代码规模。逃逸比 = fix/feat，越低越好；`-` 为 feat=0 无意义。")
    L.append("")

    L.append("### 2.2 敏捷度量（Agile signals）")
    L.append("")
    L.append(f"- **Velocity** = feat / 活跃天 = **{ag['velocity_per_active_day']}**（每活跃天交付的新功能数）")
    L.append(f"- **Cycle time** = 平均提交间隔 = **{ag['cycle_time_days']}** 天")
    L.append(f"- **Escaped defects** = 回归信号数 = **{ag['escaped_defects']}**（已漏到需修复的缺陷代理）")
    L.append("")

    L.append("### 2.3 交付路线图（按日期）")
    L.append("")
    for day in roadmap:
        L.append(f"#### {day['date']}")
        for c in day["commits"]:
            L.append(f"- `{c.hash}` **[{c.type}]** {c.subject}")
        L.append("")

    L.append("### 2.4 风险登记")
    L.append("")
    L.append("| ID | 严重度 | 风险 | 证据(hash) | 建议 |")
    L.append("| --- | --- | --- | --- | --- |")
    for r in risks:
        L.append(f"| {r['id']} | {r['severity']} | {_esc(r['title'])} | {_esc(r['evidence'])} | {_esc(r['recommend'])} |")
    L.append("")

    inp = metrics["input"]
    L.append("### 2.5 三层指标框架（Output / Outcome / Input）")
    L.append("")
    L.append("> **用途**：把「做了多少事（Output）」「做成了什么效果（Outcome）」「哪些信号能预测未来风险（Input / 领先指标）」分开看。"
             "避免把团队活跃度误当成项目成效，也能在质量劣化前用领先指标提前干预。")
    L.append("")
    L.append(f"**Output（产出 / 交付量，滞后指标，来自 §一）：** 交付 {o['feat_count']} 项新功能、"
             f"{o['fix_count']} 项修复、{o['security_count']} 项安全加固；触及 {o['module_count']} 个模块；"
             f"代码变动量 {o['total_churn']} 行；活跃 {o['active_days']} 天（{o['date_span']}）。")
    L.append("")
    L.append("**Outcome（业务成果 / 效果，由 Output 推导，均来自真实提交）：**")
    for s in metrics["outcome"]:
        L.append(f"- {s}")
    L.append("")
    esc = inp["escape_ratio_overall"]
    L.append("**Input / 领先指标（Leading indicators，用于预测下期质量）：** "
             f"整体逃逸比 fix/feat = {esc if esc is not None else '-'} ｜ 回滚 {inp['revert_count']} ｜ "
             f"回归信号 {inp['regression_signal_count']}。{inp['read']}")
    L.append("")

    # —— 2.6 跨源监控 ——
    L.append("### 2.6 跨源监控（需求 / 进度 / 需求变更）")
    L.append("")
    cs = metrics.get("cross_source", {})
    if cs.get("pm_total") or cs.get("spec_changes"):
        L.append(f"- 已接入数据源类别：{', '.join(cs.get('sources_used', []))}")
        L.append(f"- 需求总数（PM 工具）：**{cs.get('requirements_total', 0)}** ｜ 状态分布：{cs.get('status_breakdown', {})} ｜ 完成率：**{cs.get('progress_done_ratio')}**")
        chg = cs.get("requirement_changes", [])
        L.append(f"- 需求变更事件：**{len(chg)}** 条" + ("（" + "；".join(f"{c['id']}:{c['status']}" for c in chg[:5]) + "）" if chg else ""))
        spc = cs.get("spec_changes", [])
        L.append(f"- 文档/规格变更：**{len(spc)}** 条" + ("（" + "；".join(f"{c['id']}" for c in spc[:5]) + "）" if spc else ""))
        if cs.get("story_links"):
            L.append(f"- git 提交 ↔ PM 单号 可追溯链接：**{cs['story_links']}** 条")
        L.append("")
        L.append("**模块可追溯矩阵（PM 需求数 × git 提交数）：**")
        L.append("")
        L.append("| 模块 | PM 需求 | git 提交 |")
        L.append("| --- | ---: | ---: |")
        for t in cs.get("traceability", []):
            L.append(f"| {t['module']} | {t['pm_requirements']} | {t['git_commits']} |")
        L.append("")
    else:
        L.append("- 当前仅 git 数据源。需求信息 / 进度 / 需求变更需接入 pm_tool（Jira/Linear）与 doc_tool（Confluence/Google Doc），"
                 "在 `config/settings.json` 的 sources 中启用对应源即可，报告将自动补全以上监控。")
        L.append("")

    # —— 2.7 变更管理（整合管理·实施整体变更控制）——
    L.append("### 2.7 变更管理（整合管理 · 实施整体变更控制）")
    L.append("")
    L.append("> 每次提交 = 一次变更请求；revert = 变更被拒；大提交 = 变更未小步拆分；"
             "关键变更（security）集中于末期 = 变更未受控。全部维度仅依赖 git 提交，不依赖 PM 工具。")
    L.append("")
    ch = metrics.get("change", {})
    if ch.get("findings"):
        L.append("| 维度 | 当前值 | 说明 | 关联风险 |")
        L.append("| --- | --- | --- | --- |")
        for f in ch["findings"]:
            link = f["risk_link"] or "-"
            L.append(f"| {f['label']} | {f['value']} | {_esc(f['note'])} | {link} |")
        L.append("")
    else:
        L.append("- 未采集到 code_repo 工作项，变更管理维度不可计算。")
        L.append("")

    L.append("## 三、工作绩效报告（结论与治理）")
    L.append("")
    L.append("### 3.1 PMBOK 绩效域 × git 数据支撑度")
    L.append("")
    L.append("| 绩效域 | 支撑度 | 依据 |")
    L.append("| --- | --- | --- |")
    for d in metrics["pmbok_domains"]:
        L.append(f"| {d['domain']} | {d['support']} | {_esc(d['basis'])} |")
    L.append("")
    L.append("> 标注「需接 PM 工具」的域在 git 中无原始数据，接入 Jira/Linear 后补全，而非编造。")
    L.append("")

    L.append("### 3.2 英文执行摘要（AI 生成）")
    L.append("")
    L.append(f"> {ai.note}")
    L.append("")
    L.append(ai.exec_summary_en)
    L.append("")
    L.append("**Next-quarter plan:**")
    for p in ai.next_quarter_plan:
        L.append(f"- {p}")
    L.append("")
    return "\n".join(L)


CSS = """
:root{--bg:#F5F2ED;--card:#fff;--ink:#2b2b2b;--muted:#6b6b6b;--line:#e3ddd2;
--red:#c0392b;--amber:#d68910;--green:#1e8449;--blue:#2471a3;--accent:#8e6f4e;}
*{box-sizing:border-box}
body{font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
background:var(--bg);color:var(--ink);margin:0;padding:28px;line-height:1.55}
.wrap{max-width:1000px;margin:0 auto}
h1{font-size:24px;margin:0 0 4px}
h2{font-size:18px;margin:26px 0 10px;border-left:4px solid var(--accent);padding-left:10px}
h3{font-size:15px;margin:18px 0 8px;color:var(--blue)}
.meta{color:var(--muted);font-size:13px;margin-bottom:18px}
.kpis{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;min-width:120px}
.kpi .n{font-size:22px;font-weight:700}
.kpi .l{font-size:12px;color:var(--muted)}
table{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0;background:var(--card)}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
th{background:#efe9df;font-weight:600}
tr:nth-child(even) td{background:#faf7f2}
.sev-高{color:var(--red);font-weight:700}.sev-中{color:var(--amber);font-weight:700}.sev-低{color:var(--green)}
.day{margin:6px 0 14px}
.day h4{font-size:13px;color:var(--blue);margin:10px 0 4px}
.day li{font-size:13px;margin:2px 0}
.hash{font-family:ui-monospace,Menlo,monospace;color:var(--accent);font-size:12px}
.tag{display:inline-block;font-size:11px;padding:1px 6px;border-radius:6px;background:#efe9df;color:#5b4a33;margin-right:4px}
.quote{background:#fbf8f3;border-left:4px solid var(--accent);padding:12px 14px;border-radius:8px;font-size:14px}
.note{font-size:12px;color:var(--muted)}
.badge{font-size:11px;padding:2px 8px;border-radius:20px;background:var(--blue);color:#fff}
.badge.off{background:#999}
"""

SUPPORT_CLASS = {"支撑": "sev-低", "部分": "sev-中", "需接 PM 工具": "sev-高"}


def build_html(repo, meta, commits, modules, roadmap, risks, metrics, ai) -> str:
    o = metrics["output"]
    ag = metrics["agile"]
    cs = metrics.get("cross_source", {})
    srcs = meta.get("sources", [])
    src_line = "、".join(f"{s['name']}({s['category']},{s['count']})" for s in srcs) or "无"
    kpis = [
        (o["commit_total"], "提交总数"),
        (o["feat_count"], "新增 feat"),
        (o["fix_count"], "修复 fix"),
        (o["security_count"], "安全加固"),
        (o["module_count"], "触及模块"),
        (f"{o['total_churn']}", "Churn 变动量"),
        (o["active_days"], "活跃天数"),
        (metrics["input"]["escape_ratio_overall"] if metrics["input"]["escape_ratio_overall"] is not None else "-", "逃逸比 fix/feat"),
        (ag["velocity_per_active_day"], "Velocity/天"),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="n">{v}</div><div class="l">{l}</div></div>'
        for v, l in kpis
    )
    mod_rows = "".join(
        f"<tr><td>{_esc(mv.cn)}<br><span class='note'>{_esc(mv.en)}</span></td>"
        f"<td>{len(mv.commits)}</td><td>{len(mv.feat)}</td><td>{len(mv.fix)}</td>"
        f"<td>{mv.escape_ratio if mv.escape_ratio is not None else '-'}</td><td>{mv.churn}</td></tr>"
        for mv in modules.values()
    )
    agi = (f"<li><b>Velocity</b> = feat / 活跃天 = {ag['velocity_per_active_day']}</li>"
           f"<li><b>Cycle time</b> = 平均提交间隔 = {ag['cycle_time_days']} 天</li>"
           f"<li><b>Escaped defects</b> = 回归信号数 = {ag['escaped_defects']}</li>")
    road = ""
    for day in roadmap:
        items = "".join(
            f'<li><span class="hash">{c.hash}</span> <span class="tag">{c.type}</span>{_esc(c.subject)}</li>'
            for c in day["commits"]
        )
        road += f'<div class="day"><h4>{day["date"]}</h4><ul>{items}</ul></div>'
    risk_rows = "".join(
        f"<tr><td>{r['id']}</td><td class='sev-{r['severity']}'>{r['severity']}</td>"
        f"<td>{_esc(r['title'])}</td><td class='note'>{_esc(r['evidence'])}</td><td>{_esc(r['recommend'])}</td></tr>"
        for r in risks
    )
    outcome = "".join(f"<li>{_esc(s)}</li>" for s in metrics["outcome"])
    dom_rows = "".join(
        f"<tr><td>{_esc(d['domain'])}</td><td class='{SUPPORT_CLASS.get(d['support'],'')}'>{d['support']}</td>"
        f"<td class='note'>{_esc(d['basis'])}</td></tr>"
        for d in metrics["pmbok_domains"]
    )
    plan = "".join(f"<li>{_esc(p)}</li>" for p in ai.next_quarter_plan)
    ai_badge = f'<span class="badge">AI: {_esc(ai.model)}</span>' if ai.available else '<span class="badge off">AI: 模板降级</span>'

    # —— 2.6 跨源监控（需求 / 进度 / 需求变更）——
    if cs.get("pm_total") or cs.get("spec_changes"):
        chg = cs.get("requirement_changes", [])
        spc = cs.get("spec_changes", [])
        trace_rows = "".join(
            f"<tr><td>{_esc(t['module'])}</td><td>{t['pm_requirements']}</td><td>{t['git_commits']}</td></tr>"
            for t in cs.get("traceability", []))
        chg_txt = "; ".join(f"{c['id']}:{c['status']}" for c in chg[:5])
        spc_txt = "; ".join(c["id"] for c in spc[:5])
        status_txt = str(cs.get("status_breakdown", {}))
        link_txt = f"<li>git ↔ PM 单号 可追溯链接：<b>{cs['story_links']}</b> 条</li>" if cs.get("story_links") else ""
        cross_html = f"""<h3>2.6 跨源监控（需求 / 进度 / 需求变更）</h3>
<ul>
<li>已接入数据源类别：{', '.join(cs.get('sources_used', []))}</li>
<li>需求总数（PM 工具）：<b>{cs.get('requirements_total', 0)}</b> ｜ 状态分布：{_esc(status_txt)} ｜ 完成率：<b>{cs.get('progress_done_ratio')}</b></li>
<li>需求变更事件：<b>{len(chg)}</b> 条（{_esc(chg_txt)}）</li>
<li>文档/规格变更：<b>{len(spc)}</b> 条（{_esc(spc_txt)}）</li>
{link_txt}</ul>
<table><thead><tr><th>模块</th><th>PM 需求</th><th>git 提交</th></tr></thead><tbody>{trace_rows}</tbody></table>
<p class="note">需求/进度/变更来自 pm_tool（Jira/Linear）与 doc_tool（Confluence/Google Doc）；未接入时本段为空，不编造。</p>"""
    else:
        cross_html = """<h3>2.6 跨源监控（需求 / 进度 / 需求变更）</h3>
<p class="note">当前仅 git 数据源。需求信息 / 进度 / 需求变更需接入 pm_tool（Jira/Linear）与 doc_tool（Confluence/Google Doc）；在 config/settings.json 的 sources 中启用对应源，报告自动补全以上监控。</p>"""

    # —— 2.7 变更管理（整合管理·实施整体变更控制）——
    ch = metrics.get("change", {})
    if ch.get("findings"):
        rows = "".join(
            f"<tr><td>{_esc(f['label'])}</td><td>{_esc(f['value'])}</td>"
            f"<td class='note'>{_esc(f['note'])}</td><td>{_esc(f['risk_link'] or '-')}</td></tr>"
            for f in ch["findings"])
        change_html = f"""<h3>2.7 变更管理（整合管理 · 实施整体变更控制）</h3>
<p class="note">每次提交 = 一次变更请求；revert = 变更被拒；大提交 = 变更未小步拆分；关键变更（security）集中于末期 = 变更未受控。全部维度仅依赖 git 提交，不依赖 PM 工具。</p>
<table><thead><tr><th>维度</th><th>当前值</th><th>说明</th><th>关联风险</th></tr></thead><tbody>{rows}</tbody></table>"""
    else:
        change_html = """<h3>2.7 变更管理（整合管理 · 实施整体变更控制）</h3>
<p class="note">未采集到 code_repo 工作项，变更管理维度不可计算。</p>"""

    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>pm-harness · PM 报告</title><style>{CSS}</style></head>
<body><div class="wrap">
<h1>pm-harness · AI 项目管理报告</h1>
<div class="meta">自动生成 ｜ 仓库 <code>{_esc(repo)}</code> ｜ 跨度 {o['date_span']} ｜ 已接入数据源（平级互补）：{_esc(src_line)}</div>

<h2>一、工作绩效数据（Work Performance Data）</h2>
<div class="kpis">{kpi_html}</div>

<h2>二、工作绩效信息（Work Performance Information）</h2>
<h3>2.1 模块矩阵（Epic 视图）</h3>
<table><thead><tr><th>模块</th><th>提交</th><th>feat</th><th>fix</th><th>逃逸比</th><th>Churn</th></tr></thead>
<tbody>{mod_rows}</tbody></table>
<p class="note">Churn = 增删行数之和（代码变动量），非静态代码规模。逃逸比 = fix/feat，越低越好；`-` 为 feat=0 无意义。</p>

<h3>2.2 敏捷度量（Agile signals）</h3><ul>{agi}</ul>

<h3>2.3 交付路线图（按日期）</h3>{road}

<h3>2.4 风险登记</h3>
<table><thead><tr><th>ID</th><th>严重度</th><th>风险</th><th>证据(hash)</th><th>建议</th></tr></thead>
<tbody>{risk_rows}</tbody></table>

<h3>2.5 三层指标框架（Output / Outcome / Input）</h3>
<p class="note"><b>用途：</b>把「做了多少事（Output）」「做成了什么效果（Outcome）」「哪些信号能预测未来风险（Input / 领先指标）」分开看。避免把团队活跃度误当成项目成效，也能在质量劣化前用领先指标提前干预。</p>
<p class="note"><b>Output（产出 / 交付量，滞后指标，来自 §一）：</b> 交付 {o['feat_count']} 项新功能、{o['fix_count']} 项修复、{o['security_count']} 项安全加固；触及 {o['module_count']} 个模块；代码变动量 {o['total_churn']} 行；活跃 {o['active_days']} 天（{o['date_span']}）。</p>
<p class="note"><b>Outcome（业务成果 / 效果，由 Output 推导，均来自真实提交）：</b></p><ul>{outcome}</ul>
<p class="note"><b>Input / 领先指标（Leading indicators，用于预测下期质量）：</b> 整体逃逸比 fix/feat = {metrics['input']['escape_ratio_overall'] if metrics['input']['escape_ratio_overall'] is not None else '-'} ｜ 回滚 {metrics['input']['revert_count']} ｜ 回归信号 {metrics['input']['regression_signal_count']}。{_esc(metrics['input']['read'])}</p>

{cross_html}
{change_html}

<h2>三、工作绩效报告（Work Performance Reports）</h2>
<h3>3.1 PMBOK 绩效域 × git 数据支撑度</h3>
<table><thead><tr><th>绩效域</th><th>支撑度</th><th>依据</th></tr></thead><tbody>{dom_rows}</tbody></table>
<p class="note">标注「需接 PM 工具」的域在 git 中无原始数据，接入 Jira/Linear 后补全，而非编造。</p>

<h3>3.2 英文执行摘要（AI 生成） {ai_badge}</h3>
<p class="note">{_esc(ai.note)}</p>
<div class="quote">{_esc(ai.exec_summary_en)}</div>
<p><b>Next-quarter plan:</b></p><ul>{plan}</ul>

<p class="note">本报告由 pm-harness 基于真实 git 历史生成，所有结论可溯源到提交 hash。启动本地 Ollama（:11434）可获得 LLM 合成的英文摘要。</p>
</div></body></html>"""
