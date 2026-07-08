---
name: agentlens
description: AI Agent 可观测性与调试工具。当你需要记录 agent 运行过程、分析 trace、检测异常行为（循环、幻觉、过度搜索）时使用。适用于 CodeWhale、Claude Code、Cursor 等任何 AI agent。
metadata:
  short-description: Agent 可观测性：trace 记录、分析、异常检测
---

# AgentLens

本地优先的 AI Agent 可观测性与调试工具。定义了一套通用的 Agent Trace Schema，
让任何 AI agent 都能记录运行过程、事后分析、检测异常。

## 触发条件

当用户说以下任意内容时加载此 skill：
- "记录/分析 这次运行"
- "看看刚才有什么问题"
- "agentlens"
- "trace 分析"
- "为什么这么慢/这么贵"

## 工作流程

### 第一步：记录 Trace（采集阶段）

当用户要求记录时，agent 应在运行过程中将每一步操作输出为符合 schema 的 JSONL 事件。

事件类型及何时记录：

| 时机 | 事件类型 | data 关键字段 |
|------|---------|-------------|
| 用户发来消息 | `user.message` | user_content |
| 新一轮开始 | `turn.start` | message |
| 工具调用开始 | `tool.start` | tool_name, tool_input |
| 工具调用结束 | `tool.end` | tool_name, tool_output_size, tool_duration_ms, status |
| 工具调用失败 | `tool.error` | tool_name, error_message, status: "failure" |
| 启动子 agent | `subagent.spawn` | subagent_name, subagent_prompt |
| 子 agent 返回 | `subagent.done` | subagent_name, subagent_result |
| 子 agent 失败 | `subagent.error` | subagent_name, error_message |
| 内部推理 | `reasoning.delta` | reasoning_content (truncated), reasoning_tokens |
| Token 消耗快照 | `token.usage` | input_tokens, output_tokens, cache_hit_tokens, cache_miss_tokens, cost_usd |
| 文件读取 | `tool.*` + file_path, file_action: "read" | — |
| 文件修改 | `edit.apply`   | file_path, file_action: "write/edit" |
| 一轮结束 | `turn.end`     | message, tool_duration_ms (总耗时) |
| 异常/错误 | `error`        | error_code, error_message |

**记录规则：**
- 每个事件一行 JSON，写入同一个 `.jsonl` 文件
- `event_id` 用递增序号即可（如 `evt-001`），timestamp 用 ISO 8601
- `parent_event_id` 指向父事件（如 tool.start 指向 turn.start）
- 工具输出超过 500 字符时截断，记录 `tool_output_size` 原始大小
- token 相关数据从运行时元数据中获取；如果拿不到，标注 `"unavailable"` 并跳过

### 第二步：分析 Trace（诊断阶段）

运行结束后，调用 scripts/ 中的工具进行分析：

```bash
# 基础统计
python3 scripts/trace_stats.py <trace.jsonl>

# 异常检测
python3 scripts/trace_check.py <trace.jsonl>

# 从原始日志转换（如果 trace 不是标准格式）
python3 scripts/trace_convert.py <raw.log> --format <source> > trace.jsonl
```

### 第三步：呈现报告

读取脚本输出，结合 agent 自身的语义理解，生成人类可读的报告。报告应包含：
1. **概览**：事件总数、工具调用次数、失败次数、总耗时、token 消耗
2. **异常**：检测到的问题列表，每个问题附证据和严重程度
3. **建议**：针对每个异常给出改进建议

## 报告模板

```markdown
# 📊 AgentLens 运行报告

## 概览
- 事件总数: {total} | 工具调用: {tool_calls} | 失败: {failures} ({rate}%)
- 总耗时: {duration}s | Token 消耗: {tokens}（输入 {input_tk} + 输出 {output_tk}）
- 缓存命中率: {cache_rate}% | 估算成本: ${cost}

## ⚠️ 异常检测 ({anomaly_count} 个问题)
{for each anomaly:}
- **[{severity}]** {description}
  证据: {evidence}
  建议: {suggestion}

## 💡 改进建议
{汇总建议}
```

## Schema 参考

完整 schema 定义见 `assets/schema.json`。编写时参考它来确保事件格式正确。
