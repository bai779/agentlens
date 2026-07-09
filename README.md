# AgentLens

> 🧿 本地优先的 AI Agent 可观测性与调试工具

加载此 skill 后，Agent 获得三层诊断能力：运行时实时自省 → 运行后深度复盘 → 跨会话自适应改进。

---

## 安装

```bash
git clone https://github.com/bai779/agentlens.git
cp -r agentlens ~/.deepseek/skills/   # CodeWhale
cp -r agentlens ~/.claude/skills/     # Claude Code
```

## 使用

对 Agent 说："用 agentlens 记录这次分析"  
或直接命令行：

```bash
python3 scripts/trace_stats.py examples/sample_trace.jsonl
python3 scripts/trace_check.py examples/sample_trace.jsonl
```

---

## 功能

- **Trace Schema** — 20 种事件类型，框架无关
- **统计分析** — token、耗时、成本、工具分布
- **异常检测** — 7 种检测器（循环、错误率、缓存效率、搜索迷路等）
- **终端可视化** — 时间瀑布图 + 柱状图 + 仪表盘，终端原生 ANSI 渲染
- **格式转换** — 原始日志 → JSONL

## 项目结构

```
agentlens/
├── SKILL.md                    # 自我诊断专家系统
├── assets/schema.json          # Trace Schema v1.0
├── scripts/
│   ├── trace_stats.py          # 统计
│   ├── trace_check.py          # 异常检测
│   ├── trace_convert.py        # 格式转换
│   └── trace_viz.py            # 终端可视化
├── examples/sample_trace.jsonl  # 示例数据
└── LICENSE                     # MIT
```

---

## License

MIT
