# AgentLens

> 🧿 本地优先的 AI Agent 可观测性与调试工具

**不只是记录 agent 做了什么——而是让你能回放、分析、检测异常，像调试普通程序一样调试 AI Agent。**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-green.svg)](https://www.python.org/)

---

## 一句话区分

| 其他工具（LangFuse 等） | AgentLens |
|------------------------|-----------|
| "Agent 调了 3 次 API，花了 $0.02" | "Agent 在第 3 步做了一个错误假设——回放到那一帧，看它为什么走错了" |
| 飞行记录仪（事后看黑匣子） | 调试器 + 诊断引擎 |

---

## 快速开始

```bash
# 安装（拷贝文件夹即可，零依赖）
git clone https://github.com/bai779/agentlens.git
# 或直接作为 CodeWhale / Claude Code skill 使用：
cp -r agentlens ~/.deepseek/skills/

# 分析示例 trace
python3 scripts/trace_stats.py examples/sample_trace.jsonl
python3 scripts/trace_check.py examples/sample_trace.jsonl
```

---

## 功能

- **通用 Trace Schema** — 一套统一的 Agent 事件格式（`assets/schema.json`），跨框架通用
- **统计分析**（`trace_stats.py`）— 工具调用次数、token 消耗、耗时分布、缓存命中率、成本估算
- **异常检测**（`trace_check.py`）— 自动检测 7 类异常：
  - 🔴 工具调用循环（同一工具连续失败）
  - 🟡 单轮过度调用（效率低下/搜索迷路）
  - 🟡 搜索死循环（连续空结果）
  - 🟢 冗余文件读取
  - 🔴 子 Agent 高失败率
  - 🟡 前缀缓存命中率低
  - 🔴 工具调用高错误率
- **格式转换**（`trace_convert.py`）— 从原始 Agent 日志转为标准 JSONL
- **Skill 集成** — 作为 CodeWhale / Claude Code skill 直接使用（`SKILL.md`）

---

## 作为 Agent Skill 使用

将 `agentlens/` 放到对应 skill 目录后，对 Agent 说：

> "用 agentlens 记录这次运行，结束后分析"

Agent 会在运行过程中记录每一步操作，运行结束后自动调用脚本给出报告。

---

## 项目结构

```
agentlens/
├── SKILL.md                    # Agent skill 指令文件
├── assets/
│   └── schema.json             # Agent Trace Schema 定义
├── scripts/
│   ├── trace_stats.py          # 统计分析
│   ├── trace_check.py          # 异常检测（7 种检测器）
│   └── trace_convert.py        # 格式转换
├── examples/
│   └── sample_trace.jsonl      # 示例 trace（42 个事件，2 轮对话）
├── README.md
└── LICENSE
```

---

## Trace Schema 事件类型

| 类型 | 说明 |
|------|------|
| `session.start/end` | 会话生命周期 |
| `turn.start/end` | 对话轮次 |
| `user.message` | 用户输入 |
| `reasoning.delta/end` | 内部推理链 |
| `tool.start/end/error` | 工具调用 |
| `subagent.spawn/done/error` | 子 Agent |
| `token.usage` | Token 消耗快照 |
| `edit.apply` | 文件修改 |
| `error` | 通用异常 |

完整定义见 [`assets/schema.json`](assets/schema.json)。

---

## Roadmap

- [x] Trace Schema v1.0
- [x] 统计分析脚本
- [x] 7 种异常检测器
- [x] 格式转换器
- [ ] TUI 交互式仪表盘（Rust + Ratatui）
- [ ] 确定性回放引擎
- [ ] 断点调试器（注入替代事件）
- [ ] 行为断言 DSL
- [ ] gRPC 实时采集器

---

## License

MIT © 2026
