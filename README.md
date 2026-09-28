# git-pm-harness

> 一个 **git-native、可插拔多数据源** 的项目管理 harness：把 git 提交历史与可选的
> 项目管理工具（Jira/Linear）、文档工具（Confluence/Google Doc）作为**平级互补事实源**，
> 自动产出融合 **PMBOK 监控过程组** 与 **敏捷度量** 的 AI 项目管理报告。无需 PM 工具即可起步，
> 可每日持续运行，支持配置化 LLM provider。

## 为什么做这个

小团队 / 独立开发者 / 开源项目常常没有专职 PM 工具，但 git 提交历史本身就是一份
「系统记录」——约定式 commit（`feat/fix/security/revert…`）天然携带了范围、质量、风险信号。
当项目接入 Jira/Linear/Confluence 时，这些源与 git **平级互补**，共同回答三件事：
**需求信息、进度、需求变更**。

本 harness 的骨架对应 **PMBOK 监控过程组** 的精确链：

```
多源数据(git + pm + doc)  ──►  工作绩效数据 (Work Performance Data)
          │
       analyze    ──►  工作绩效信息 (Work Performance Information)
          │
       report     ──►  工作绩效报告 (Work Performance Reports)
```

## 核心设计

### 1. 多数据源，分类平级互补（你要求的分类）

| 分类 category | 数据源 source | 监控什么 |
| --- | --- | --- |
| `code_repo` 代码仓库 | `git` | 提交/范围/质量/风险（变动量、逃逸比、回滚） |
| `pm_tool` 项目管理工具 | `jira` / `linear` | **需求信息、进度、需求变更**（Story/Epic 状态流转） |
| `doc_tool` 文档工具 | `confluence` / `googledoc` | 规格/需求文档的**修订**（变更侧信号） |

- 同一项目内通常只用一种 `pm_tool`（Jira **或** Linear 二选一），harness 不强制，合并所有已启用源。
- 每个 connector 只在「配置启用 + 凭证/路径可用」时读取；否则跳过并说明原因，**绝不编造数据**。
- 跨源监控（§2.6）：需求总数、状态分布与完成率、需求变更事件、git↔PM 单号可追溯链接、模块可追溯矩阵。

### 2. LLM provider 抽象（省钱优先级）

`llm.resolve_provider` 按 `priority` 选**第一个可用**的 provider：

```
shell（Claude Code / WorkBuddy harness）  >  ollama（本地，免费）  >  openai（API key，按量计费）
```

- 全部不可用时降级为**模板**（仍基于真实数字），保证报告永远可生成。
- 配置在 `config/settings.json` 的 `llm` 段；`shell` 用 `command`+`args` 调 CLI（如 `claude -p`），
  `openai` 兼容任意 OpenAI 系 API（base_url + key_env）。

## 特性

- **零 PM 工具依赖起步**：只读 `git log`，不写入业务仓库。
- **多数据源可插拔**：git / Jira / Linear / Confluence / Google Doc，分类平级互补。
- **可配置领域词典**：换项目只需换一份 `config/domains/*.json`，不碰代码。
- **三层 + 敏捷指标**：Output / Outcome / Input 框架 + Velocity / Cycle time / Escaped defects。
- **跨源监控**：需求 / 进度 / 需求变更，git↔PM 可追溯矩阵。
- **风险登记**：R1-R5 规则直接产出可溯源（带 hash）的风险清单。
- **PMBOK 域覆盖矩阵**：诚实标注哪些绩效域已支撑、哪些需接 PM 工具补全；接入 pm_tool 后动态升级。
- **每日持续运行**：`daily_run.py` 维护趋势时序，阈值触发完整报告，避免空转刷屏。
- **可选 AI 层**：可配置 provider（shell > ollama > openai），不可达自动降级。

## 安装

仅依赖 **Python 3.10+** 与 **git**，无需第三方包。

```bash
git clone <your-repo> && cd git-pm-harness
python run.py --repo /path/to/your/repo --domain default
```

可选 AI 层（三选一，按省钱优先级自动选）：
```bash
ollama serve && ollama pull qwen2.5:3b     # 本地免费
# 或 export OPENAI_API_KEY=sk-...          # 按量计费（最后才用）
# 或确保 claude / workbuddy CLI 在 PATH     # agentic harness（优先）
```

## 快速开始

```bash
# 一次性全量报告（默认指向 settings.json 的 git.repo + fitness 词典）
python run.py

# 用通用词典分析任意仓库
python run.py --repo /path/to/repo --domain default

# 跳过 AI 层（纯规则，离线可用）
python run.py --no-ai

# 多数据源演示（git + Jira fixture + Confluence fixture，无需真实凭证）
python run.py --settings config/sources.demo.json --out output-demo

# 每日持续运行：写趋势 + 阈值触发完整报告
python daily_run.py --repo /path/to/repo --domain default
```

输出：
- `output/PM报告-YYYYMMDD.{md,html}` —— 一次性全量报告
- `reports/trends.json` + `reports/trends.csv` —— 每日趋势时序
- `reports/DAILY-YYYY-MM-DD.md` —— 轻量日报（含与上次 diff）
- `reports/PM报告-YYYYMMDD.{md,html}` —— 触发阈值时生成的完整报告

## 配置

### 数据源 `config/settings.json`

```json
{
  "domain": "default",
  "sources": {
    "git":        { "enabled": true,  "repo": "/path/to/repo", "category": "code_repo" },
    "jira":       { "enabled": false, "category": "pm_tool",
                    "base_url": "https://x.atlassian.net",
                    "email_env": "JIRA_EMAIL", "token_env": "JIRA_API_TOKEN", "project_key": "FIT" },
    "linear":     { "enabled": false, "category": "pm_tool",
                    "api_key_env": "LINEAR_API_KEY", "team_key": "ENG" },
    "confluence": { "enabled": false, "category": "doc_tool",
                    "base_url": "https://x.atlassian.net", "token_env": "CONFLUENCE_TOKEN" },
    "googledoc":  { "enabled": false, "category": "doc_tool",
                    "creds_env": "GOOGLE_CREDS_JSON", "folder_id": "..." }
  },
  "llm": {
    "priority": ["shell", "ollama", "openai"],
    "shell":   { "engine": "claude", "command": "claude", "args": ["-p"], "model": "claude-code" },
    "ollama":  { "model": "qwen2.5:3b", "base_url": "http://localhost:11434" },
    "openai":  { "model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1", "api_key_env": "OPENAI_API_KEY" }
  }
}
```

- 凭证一律走**环境变量**（`*_env` 字段），不落盘明文。
- 未配置或凭证缺失的源会被**跳过**（报告里列出跳过原因），不会中断。
- `fixture` 字段：指向一份 WorkItem JSON，用于无凭证时的端到端测试与示例（见 `config/fixtures/`）。

### 领域词典 `config/domains/<name>.json`

```json
{
  "name": "my-project",
  "modules": {
    "backend":  {"cn": "后端", "en": "Backend", "keywords": ["api", "server", "db"]},
    "frontend": {"cn": "前端", "en": "Frontend", "keywords": ["ui", "页面", "组件"]}
  },
  "rules": { "security_late_frac": 0.6, "high_escape_ratio": 1.5, "big_commit_files": 8 }
}
```

运行：`python run.py --domain my-project`

## 指标定义（诚实口径）

| 指标 | 含义 | 口径注意 |
| --- | --- | --- |
| **Churn** | 代码变动量 = 增删行数之和 | 不是静态代码规模；高的模块「改得多」，不代表差 |
| **逃逸比** | fix 数 ÷ feat 数 | 每交付 1 功能带出的修复数，越低越好；feat=0 时显示 `-` |
| **Velocity** | feat 数 ÷ 活跃天数 | 每活跃天交付的新功能数（敏捷速率代理） |
| **Cycle time** | 平均提交间隔（天） | 节奏代理，非严格 lead time |
| **Escaped defects** | 提交描述含「回归/regress」的信号数 | 已漏到需修复的缺陷代理，非线上缺陷率 |
| **完成率** | pm_tool 中 done/closed ÷ 总数 | 来自 Jira/Linear 状态流转，git-only 时无此值 |
| **需求变更** | pm_tool 状态为 changed/reopened 或含变更关键词 | 跨源监控（§2.6）的核心信号 |

> ⚠️ 这些都是 **commit/issue-level 代理指标**，适合做跨模块/跨时间趋势对比，**不可冒充业界标准度量**
> （如标准「缺陷逃逸率 = 线上缺陷 / 总缺陷」）。面试或汇报时务必讲清口径。

## PMBOK 绩效域 × 数据支撑度（动态）

| 绩效域 | 仅 git | 接入 pm_tool 后 |
| --- | --- | --- |
| 整合管理 | 支撑 | 支撑 |
| 范围管理 | 部分 | **支撑**（需求/Story 基准） |
| 进度管理 | 部分 | **支撑**（状态流转/关键路径） |
| 成本管理 | 需接 PM 工具 | 仍需 timesheet/ERP |
| 质量管理 | 支撑 | 支撑（+缺陷单） |
| 资源管理 | 弱 | 弱 |
| 沟通管理 | 支撑 | 支撑 |
| 风险管理 | 支撑 | 支撑 |
| 采购管理 | 需接 PM 工具 | 需接 PM 工具 |
| 干系人管理 | 需接 PM 工具 | 需接 PM 工具 |

标注「需接 PM 工具」的域在 git 中无原始数据——接入对应源后补全，**绝不编造**。

## 持续运行 + CI

`.github/workflows/daily.yml` 用 GitHub Actions 每日运行 `daily_run.py` 并把 `reports/` commit 回仓库。
把 workflow 里的 `--repo` 改为你的目标仓库（或用 `settings.json` + secret 配置数据源）。

本地定时（类比 15:10 复盘）：
```bash
# crontab / 任务计划程序
0 15 * * * cd /path/to/git-pm-harness && python daily_run.py --repo /path/to/repo
```

## 项目结构

```
pm-harness/
├── run.py               一键全量报告
├── daily_run.py         每日持续运行（趋势 + 阈值触发）
├── pm_harness/
│   ├── model.py         WorkItem 统一模型
│   ├── miner.py         git 解析（底层）
│   ├── connectors/      多数据源：git/jira/linear/confluence/googledoc + BaseConnector
│   ├── analyze.py       模块归类 / 风险 / PMBOK 矩阵 / 跨源监控 / 指标
│   ├── llm/             LLM provider 抽象（shell/ollama/openai）+ 优先级解析
│   ├── ai.py            提示词构建 + 降级；run_ai 用 llm.resolve_provider
│   ├── report.py        渲染层：PMBOK 三章 + 跨源监控 MD/HTML
│   ├── config.py        领域词典 + settings 加载
│   └── cli.py           编排入口
├── config/settings.json        数据源 + LLM 配置
├── config/domains/      可配置领域词典（default.json / sample.json）
├── config/fixtures/     无凭证测试样例（jira.json / confluence.json）
├── config/sources.demo.json     多数据源演示配置
└── output/              一次性报告（不纳入版本库）
```

## 新增一个数据源

1. 在 `pm_harness/connectors/` 新建 `xxx_connector.py`，继承 `BaseConnector`，实现 `collect()` 返回 `WorkItem` 列表（设好 `category`/`source`/`kind`/`status`）。
2. 在 `connectors/__init__.py` 的 `REGISTRY` 注册。
3. 在 `config/settings.json` 的 `sources` 增加该源的 `enabled`/`category`/凭证字段。
4. analyze/report 无需改动（已消费统一的 `WorkItem`）。

## 路线图

- [x] 多数据源 connector（git / jira / linear / confluence / googledoc）
- [x] LLM provider 抽象（shell > ollama > openai 优先级）
- [ ] Epic → Jira/Linear CSV 反向导出（从复盘升级为规划）
- [ ] 模块依赖图 + 就绪态（status aggregation）
- [ ] 趋势可视化（sparkline / burndown 图）
- [ ] 周报自动投递 Slack / 邮件

## License

MIT © 花大牛 / xuxtc
