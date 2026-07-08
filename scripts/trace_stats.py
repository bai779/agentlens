#!/usr/bin/env python3
"""
AgentLens — Trace 统计分析

读取 AgentLens JSONL trace 文件，输出统计报告。

用法:
    python3 trace_stats.py <trace.jsonl>
    python3 trace_stats.py <trace.jsonl> --json    # JSON 格式输出
"""

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime


def parse_timestamp(ts: str) -> datetime:
    """Parse ISO 8601 timestamp, return datetime."""
    # Handle 'Z' suffix
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)


def analyze(filepath: str) -> dict:
    events = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    if not events:
        return {"error": "empty trace"}

    # --- Basic counts ---
    type_counts = Counter(e["type"] for e in events)

    tool_start_events = [e for e in events if e["type"] == "tool.start"]
    tool_end_events   = [e for e in events if e["type"] == "tool.end"]
    tool_error_events = [e for e in events if e["type"] == "tool.error"]
    tool_names = Counter(
        e.get("data", {}).get("tool_name", "unknown")
        for e in events if e["type"] in ("tool.start", "tool.end", "tool.error")
    )
    tool_success = sum(
        1 for e in tool_end_events
        if e.get("data", {}).get("status") != "failure"
    )
    tool_failures = len(tool_error_events) + sum(
        1 for e in tool_end_events
        if e.get("data", {}).get("status") == "failure"
    )
    total_tool_calls = tool_success + tool_failures

    # --- Timing ---
    timestamps = []
    for e in events:
        try:
            timestamps.append(parse_timestamp(e["timestamp"]))
        except (ValueError, KeyError):
            pass

    if timestamps:
        total_duration_s = (max(timestamps) - min(timestamps)).total_seconds()
    else:
        total_duration_s = 0

    # Sum tool durations
    tool_duration_ms = sum(
        e.get("data", {}).get("tool_duration_ms", 0) or 0
        for e in tool_end_events
    )

    # --- Token usage ---
    token_events = [e for e in events if e["type"] == "token.usage"]
    total_input = 0
    total_output = 0
    total_cache_hit = 0
    total_cache_miss = 0
    total_cost = 0.0
    for e in token_events:
        d = e.get("data", {})
        total_input += d.get("input_tokens", 0) or 0
        total_output += d.get("output_tokens", 0) or 0
        total_cache_hit += d.get("cache_hit_tokens", 0) or 0
        total_cache_miss += d.get("cache_miss_tokens", 0) or 0
        total_cost += d.get("cost_usd", 0) or 0

    cache_total = total_cache_hit + total_cache_miss
    cache_hit_rate = (total_cache_hit / cache_total * 100) if cache_total > 0 else 0

    # --- Sub-agents ---
    subagent_spawns = len([e for e in events if e["type"] == "subagent.spawn"])
    subagent_dones   = len([e for e in events if e["type"] == "subagent.done"])
    subagent_errors  = len([e for e in events if e["type"] == "subagent.error"])

    # --- File operations ---
    file_reads = sum(
        1 for e in events
        if e.get("data", {}).get("file_action") == "read"
    )
    file_writes = sum(
        1 for e in events
        if e.get("data", {}).get("file_action") in ("write", "edit")
        or e["type"] == "edit.apply"
    )

    # --- Reasoning ---
    reasoning_tokens = sum(
        e.get("data", {}).get("reasoning_tokens", 0) or 0
        for e in events if e["type"] == "reasoning.end"
    )

    # --- Turns ---
    turn_count = len([e for e in events if e["type"] == "turn.start"])

    # --- Build result ---
    return {
        "total_events": len(events),
        "total_duration_s": round(total_duration_s, 2),
        "tool_duration_ms": tool_duration_ms,
        "turns": turn_count,
        "tool_calls": total_tool_calls,
        "tool_success": tool_success,
        "tool_failures": tool_failures,
        "tool_failure_rate": round(tool_failures / total_tool_calls * 100, 1) if total_tool_calls else 0,
        "tool_names": dict(tool_names.most_common(10)),
        "subagents": {"spawned": subagent_spawns, "done": subagent_dones, "errors": subagent_errors},
        "file_ops": {"reads": file_reads, "writes": file_writes},
        "tokens": {
            "input": total_input,
            "output": total_output,
            "reasoning": reasoning_tokens,
            "total": total_input + total_output + reasoning_tokens,
            "cache_hit": total_cache_hit,
            "cache_miss": total_cache_miss,
            "cache_hit_rate": round(cache_hit_rate, 1),
        },
        "cost_usd": round(total_cost, 6),
        "event_types": dict(type_counts),
    }


def format_report(stats: dict) -> str:
    if "error" in stats:
        return f"Error: {stats['error']}"

    lines = []
    lines.append("=" * 60)
    lines.append("  AgentLens — Trace 统计报告")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  事件总数:     {stats['total_events']:>8d}")
    lines.append(f"  会话轮次:     {stats['turns']:>8d}")
    lines.append(f"  总耗时:       {stats['total_duration_s']:>7.1f}s")
    lines.append(f"  工具耗时:     {stats['tool_duration_ms']:>7.0f}ms")
    lines.append("")
    lines.append("  ── 工具调用 ──")
    lines.append(f"  总调用次数:   {stats['tool_calls']:>8d}")
    lines.append(f"  成功:         {stats['tool_success']:>8d}")
    lines.append(f"  失败:         {stats['tool_failures']:>8d}  ({stats['tool_failure_rate']}%)")
    lines.append("")
    lines.append("  工具分布:")
    for name, count in stats["tool_names"].items():
        bar = "█" * min(count, 30)
        lines.append(f"    {name:<30s} {count:>4d}  {bar}")
    lines.append("")
    lines.append("  ── 子 Agent ──")
    lines.append(f"  启动:         {stats['subagents']['spawned']:>8d}")
    lines.append(f"  完成:         {stats['subagents']['done']:>8d}")
    lines.append(f"  失败:         {stats['subagents']['errors']:>8d}")
    lines.append("")
    lines.append("  ── 文件操作 ──")
    lines.append(f"  读取:         {stats['file_ops']['reads']:>8d}")
    lines.append(f"  写入:         {stats['file_ops']['writes']:>8d}")
    lines.append("")
    lines.append("  ── Token 消耗 ──")
    t = stats["tokens"]
    lines.append(f"  输入 Token:   {t['input']:>8,}")
    lines.append(f"  输出 Token:   {t['output']:>8,}")
    lines.append(f"  推理 Token:   {t['reasoning']:>8,}")
    lines.append(f"  总 Token:     {t['total']:>8,}")
    lines.append(f"  缓存命中率:   {t['cache_hit_rate']:>7.1f}%")
    lines.append(f"  估算成本:     ${stats['cost_usd']:.4f}")
    lines.append("")
    lines.append("  ── 事件类型分布 ──")
    for etype, count in sorted(stats["event_types"].items()):
        lines.append(f"    {etype:<25s} {count:>4d}")
    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: trace_stats.py <trace.jsonl> [--json]", file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]
    output_json = "--json" in sys.argv

    try:
        stats = analyze(filepath)
    except FileNotFoundError:
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {filepath}: {e}", file=sys.stderr)
        sys.exit(1)

    if output_json:
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    else:
        print(format_report(stats))
