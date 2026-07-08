# AgentLens

> 🧿 第一个让 AI Agent 拥有自我诊断能力的 skill

**不只是记录 agent 做了什么——而是让 agent 在运行中自我感知、运行后深度复盘、跨会话持续改进。**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-green.svg)](https://www.python.org/)

---

## 为什么选择 AgentLens？

市面上已有 LangFuse（30K⭐）、Arize Phoenix（10K⭐）等 LLM 可观测性工具，但它们都在做同一件事：**外部监控**。AgentLens 走了完全不同的路。

### 五个核心差异化

**① Skill 原生集成 — Agent 自我诊断，而非外部监控**

```
LangFuse 等:   Agent → SDK → HTTP → Server → Dashboard（外部观察者）
AgentLens:     拷贝文件夹 → Agent 自己诊断自己（内置专家系统）
```

不部署服务、不装 SDK、不配网络。Agent 加载 skill 后**自动获得自我诊断能力**——运行中实时自省、运行后深度复盘、跨会话自我改进。

**② 通用 Trace Schema — 框架无关的标准协议**

20 种事件类型（`assets/schema.json`），不绑定任何框架。CodeWhale、Claude Code、Cursor、LangChain、自研 Agent——只要吐出这个格式，就能用全套工具。这是 Agent 领域的 OpenTelemetry 标准雏形。

**③ 三层诊断体系 — 不止记录，更会思考**

| 层级 | 能力 | 时机 |
|------|------|------|
| 实时自省 | 每 5 步自检，发现循环/迷路立即纠正 | 运行中 |
| 深度复盘 | 脚本定量分析 + Agent 语义解读 | 运行后 |
| 自适应学习 | 记住问题模式，下次主动规避 | 跨会话 |

**④ 零依赖、零配置、拷贝即用**

只需要 Python 3.8+（系统自带），不需要 Docker、数据库、Node.js。安装就是 `cp`，卸载就是 `rm`。

**⑤ 本地优先、隐私友好**

所有 trace 数据存本地，不上传任何服务器。适合企业内网、敏感项目、离线环境。

---

## 一句话区分

| 其他工具（LangFuse 等） | AgentLens |
|------------------------|-----------|
| "Agent 调了 3 次 API，花了 $0.02" | "Agent 在第 3 步陷入循环——实时自省发现、当场纠正、事后复盘给出根因" |
| 飞行记录仪（事后看黑匣子） | 副驾驶（边开边提醒）+ 检修工（到站后诊断） |

---

## 快速开始

```bash
# 安装（拷贝即用）
git clone https://github.com/bai779/agentlens.git
cp -r agentlens ~/.deepseek/skills/   # 作为 CodeWhale skill

# 命令行直接使用
python3 scripts/trace_stats.py examples/sample_trace.jsonl
python3 scripts/trace_check.py examples/sample_trace.jsonl
```

作为 skill 使用时，对 Agent 说：

> "用 agentlens 记录这次运行"
> "看看刚才有什么问题"
> "为什么这次这么慢？"

Agent 会自动启用三层诊断能力。

---

## 功能

- **自我诊断 Skill**（`SKILL.md`）— Agent 加载后获得实时自省 + 复盘 + 自适应能力
- **通用 Trace Schema**（`assets/schema.json`）— 20 种事件类型，框架无关
- **统计分析**（`trace_stats.py`）— token、耗时、成本、工具分布、缓存效率
- **异常检测**（`trace_check.py`）— 7 种检测器自动发现：
  - 🔴 工具调用循环（同一工具连续失败 ≥3 次）
  - 🟡 单轮过度调用（≥10 次，效率低下）
  - 🟡 搜索死循环（连续空结果）
  - 🟢 冗余文件读取（读了但从未引用）
  - 🔴 子 Agent 高失败率（≥50%）
  - 🟡 前缀缓存命中率低（<40%）
  - 🔴 工具调用高错误率（≥30%）
- **格式转换**（`trace_convert.py`）— CodeWhale / 通用日志 → 标准 JSONL

---

## 项目结构

```
agentlens/
├── SKILL.md                    # Agent 自我诊断专家系统指令
├── assets/
│   └── schema.json             # Agent Trace Schema v1.0（20 种事件）
├── scripts/
│   ├── trace_stats.py          # 统计分析（纯 Python）
│   ├── trace_check.py          # 异常检测（7 种检测器）
│   └── trace_convert.py        # 日志 → JSONL 格式转换
├── examples/
│   └── sample_trace.jsonl      # 示例 trace（42 事件 × 2 轮）
├── README.md
└── LICENSE
```

---

## 诊断报告示例

运行 `python3 scripts/trace_check.py examples/sample_trace.jsonl` 后的输出：

```
============================================================
  AgentLens — 异常检测报告
============================================================

  1. 🟡 [MEDIUM] low_cache_hit
     前缀缓存命中率仅 31% — 上下文编排可能有问题
     证据: {"hit_tokens": 3900, "miss_tokens": 8500}
     建议: 避免在轮次之间重排早期上下文。使用 compact 保持前缀稳定。

  2. 🟡 [MEDIUM] high_error_rate
     工具调用错误率 30%（3/10）
     证据: {"errors": 3, "total": 10}
     建议: 排查高频失败的工具。可能是权限、参数或网络问题。

============================================================
```

---

## 设计哲学

- **Agent 内建能力 > 外部监控系统** — 最好的诊断来自 Agent 自身
- **本地优先 > 云端中心化** — 隐私、速度、离线可用
- **技能 > 服务** — skill 文件的可移植性远超微服务
- **诊断 > 展示** — 告诉用户"有什么问题、为什么、怎么改"，而不只是展示数据

---

## Roadmap

- [x] Trace Schema v1.0
- [x] 统计分析 + 7 种异常检测器
- [x] Skill 自我诊断专家系统
- [ ] TUI 交互式仪表盘（Rust + Ratatui）
- [ ] 确定性回放引擎（逐帧重放 + 断点）
- [ ] 行为断言 DSL（"不应在未读文件 A 前修改文件 B"）
- [ ] gRPC 实时采集器
- [ ] 多 Agent 协作 trace 合并与分析

---

## License

MIT © 2026
