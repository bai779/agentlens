#!/usr/bin/env python3
"""
AgentLens — 终端可视化

读取 AgentLens JSONL trace 文件，在终端中渲染：
- 时间瀑布图（每轮工具调用时间线）
- 工具调用分布柱状图
- Token / 成本仪表盘

用法:
    python3 trace_viz.py <trace.jsonl>
    python3 trace_viz.py <trace.jsonl> --no-color   # 纯文本，无颜色
"""

import json
import sys
import os
from collections import Counter, defaultdict
from datetime import datetime

# ── ANSI 颜色 ──────────────────────────────────────────────
def _use_color():
    return sys.stdout.isatty() and "--no-color" not in sys.argv

G = "\033[32m" if _use_color() else ""   # 绿色 成功
R = "\033[31m" if _use_color() else ""   # 红色 失败
Y = "\033[33m" if _use_color() else ""   # 黄色 警告
C = "\033[36m" if _use_color() else ""   # 青色 框架
M = "\033[35m" if _use_color() else ""   # 紫色 高亮
B = "\033[1m"  if _use_color() else ""   # 粗体
D = "\033[90m" if _use_color() else ""   # 灰色
X = "\033[0m"  if _use_color() else ""   # 重置

SUCCESS = f"{G}✓{X}"
FAILURE = f"{R}✗{X}"
LOOP    = f"{Y}⟳{X}"


def parse_ts(ts: str) -> datetime:
    ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)


def load(filepath: str) -> list[dict]:
    with open(filepath) as f:
        return [json.loads(line) for line in f if line.strip()]


# ── 数据结构构建 ──────────────────────────────────────────

def build_turns(events: list[dict]) -> list[dict]:
    """按 turn 组织事件，提取时间线和工具调用。"""
    turns = []
    current = None

    for e in events:
        if e["type"] == "turn.start":
            current = {
                "turn_id": e.get("turn_id", "?"),
                "message": e.get("data", {}).get("message", "")[:60],
                "start_ts": parse_ts(e["timestamp"]),
                "end_ts": None,
                "duration_s": 0,
                "tools": [],
            }
        elif e["type"] == "turn.end" and current:
            current["end_ts"] = parse_ts(e["timestamp"])
            current["duration_s"] = (
                current["end_ts"] - current["start_ts"]
            ).total_seconds()
            current["duration_ms"] = e.get("data", {}).get("tool_duration_ms", 0) or 0
            turns.append(current)
            current = None
        elif e["type"] in ("tool.start", "tool.end", "tool.error") and current:
            if e["type"] == "tool.start":
                current["tools"].append({
                    "name": e.get("data", {}).get("tool_name", "?"),
                    "status": "running",
                    "duration_ms": 0,
                    "event_id": e["event_id"],
                    "start_ts": parse_ts(e["timestamp"]),
                })
            elif e["type"] in ("tool.end", "tool.error") and current["tools"]:
                last = current["tools"][-1]
                if last["status"] == "running":
                    last["status"] = "success" if e["type"] == "tool.end" else "failure"
                    last["duration_ms"] = e.get("data", {}).get("tool_duration_ms", 0) or 0
                    last["error"] = e.get("data", {}).get("error_message", "")

    return turns


# ── 渲染 ───────────────────────────────────────────────────

def bar(width: int, max_width: int = 40, char: str = "█") -> str:
    """比例柱状条。"""
    if max_width <= 0:
        return ""
    w = max(1, int(width / max(1, max_width) * 40))
    return char * min(w, 40)


def header(text: str):
    print(f"\n{C}┌─ {B}{text}{X}{C} {'─' * (76 - len(text))}{X}")


def footer():
    print(f"{C}└{'─' * 78}{X}\n")


# ── 主渲染函数 ─────────────────────────────────────────────

def render(events: list[dict]):
    turns = build_turns(events)

    # ── 全局统计 ──
    tool_errors = [e for e in events if e["type"] == "tool.error"]
    tool_ends   = [e for e in events if e["type"] == "tool.end"]
    all_tool_events = [
        e for e in events
        if e["type"] in ("tool.start", "tool.end", "tool.error")
    ]
    tool_name_counts = Counter(
        e.get("data", {}).get("tool_name", "?")
        for e in all_tool_events
    )

    total_input = sum(
        e.get("data", {}).get("input_tokens", 0) or 0
        for e in events if e["type"] == "token.usage"
    )
    total_output = sum(
        e.get("data", {}).get("output_tokens", 0) or 0
        for e in events if e["type"] == "token.usage"
    )
    total_hit = sum(
        e.get("data", {}).get("cache_hit_tokens", 0) or 0
        for e in events if e["type"] == "token.usage"
    )
    total_miss = sum(
        e.get("data", {}).get("cache_miss_tokens", 0) or 0
        for e in events if e["type"] == "token.usage"
    )
    total_cost = sum(
        e.get("data", {}).get("cost_usd", 0) or 0
        for e in events if e["type"] == "token.usage"
    )
    cache_total = total_hit + total_miss
    cache_rate = (total_hit / cache_total * 100) if cache_total > 0 else 0

    errors = len(tool_errors)
    successes = len(tool_ends)
    total = errors + successes
    error_rate = (errors / total * 100) if total > 0 else 0

    # ── 标题 ──
    session_id = events[0].get("session_id", "?")
    agent = events[0].get("agent_id", "?")
    print(f"\n{C}╔{'═' * 78}╗{X}")
    print(f"{C}║{X} {B}🧿 AgentLens 可视化 — {session_id}{X}" + " " * (48 - len(session_id)) + f"{D}agent: {agent}{X} {C}║{X}")
    print(f"{C}╚{'═' * 78}╝{X}")

    # ═══════════════════════════════════════════════════
    # 1. 时间瀑布图
    # ═══════════════════════════════════════════════════
    header("时间瀑布图")

    max_dur = max((t["duration_s"] for t in turns), default=1)
    bar_width = 50

    for t in turns:
        dur = t["duration_s"]
        w = max(2, int(dur / max(1, max_dur) * bar_width))
        bar_str = "█" * min(w, bar_width)
        bg_str  = "░" * max(0, bar_width - w)

        # 颜色标记：高耗时红色，中等黄色
        if dur > 60:
            color = R
        elif dur > 15:
            color = Y
        else:
            color = ""

        label = f"Turn {t['turn_id'][-2:]:>2s}"
        print(f"  {B}{label}{X}  {color}{bar_str}{bg_str}{X}  {dur:>5.1f}s  {D}{t['message'][:40]}{X}")

        # 嵌套工具调用详情
        for tool in t["tools"]:
            icon = SUCCESS if tool["status"] == "success" else (LOOP if tool["status"] == "failure" else "…")
            name = tool["name"][:18]
            ms = tool["duration_ms"]
            dur_s = ms / 1000
            w2 = max(1, int(dur_s / max(1, max_dur) * bar_width))
            sub_bar = "─" * min(w2, bar_width)
            status_color = G if tool["status"] == "success" else R
            print(f"       {status_color}├{X} {icon} {name:<18s} {D}{sub_bar} {dur_s:>5.1f}s{X}")

    footer()

    # ═══════════════════════════════════════════════════
    # 2. 工具调用分布
    # ═══════════════════════════════════════════════════
    header("工具调用分布")

    max_count = max(tool_name_counts.values(), default=1)
    for name, count in tool_name_counts.most_common():
        b = bar(count, max_count, "█")
        print(f"  {M}{name:<20s}{X} {G}{b}{X} {count}")

    footer()

    # ═══════════════════════════════════════════════════
    # 3. 仪表盘
    # ═══════════════════════════════════════════════════
    header("仪表盘")

    # Token
    total_tokens = total_input + total_output
    in_bar = bar(total_input, max(total_tokens, 1), "█")
    out_bar = bar(total_output, max(total_tokens, 1), "▓")
    print(f"  Token       输入: {B}{total_input:>6,}{X} {G}{in_bar}{X}")
    print(f"              输出: {B}{total_output:>6,}{X} {M}{out_bar}{X}")
    print(f"              总计: {B}{total_tokens:>6,}{X}")
    print(f"              成本: {Y}${total_cost:.4f}{X}")

    # Cache
    cache_color = G if cache_rate >= 70 else (Y if cache_rate >= 40 else R)
    print(f"  Cache       命中率: {cache_color}{cache_rate:.1f}%{X}  (hit:{total_hit:,} miss:{total_miss:,})")

    # Error rate
    err_color = R if error_rate >= 30 else (Y if error_rate >= 10 else G)
    print(f"  错误率      {err_color}{error_rate:.1f}%{X}  ({errors}失败 / {total}总调用)")

    # Session stats
    timestamps = []
    for e in events:
        try:
            timestamps.append(parse_ts(e["timestamp"]))
        except (ValueError, KeyError):
            pass
    if timestamps:
        total_dur = (max(timestamps) - min(timestamps)).total_seconds()
        print(f"  会话时长    {total_dur:.0f}s  ({len(turns)} 轮)")

    # Sub-agents
    sub_spawn = len([e for e in events if e["type"] == "subagent.spawn"])
    sub_done  = len([e for e in events if e["type"] == "subagent.done"])
    sub_err   = len([e for e in events if e["type"] == "subagent.error"])
    if sub_spawn > 0:
        print(f"  子Agent     {sub_spawn}启动 {sub_done}完成 {sub_err}失败")

    # File ops
    reads  = sum(1 for e in events if e.get("data", {}).get("file_action") == "read")
    writes = sum(1 for e in events if e.get("data", {}).get("file_action") in ("write", "edit"))
    print(f"  文件操作    {reads}读取 {writes}写入")

    footer()

    # ═══════════════════════════════════════════════════
    # 4. 循环/异常高亮
    # ═══════════════════════════════════════════════════
    # 检测连续失败的工具调用
    tool_seq = []
    for e in events:
        if e["type"] in ("tool.end", "tool.error"):
            name = e.get("data", {}).get("tool_name", "?")
            status = "success" if e["type"] == "tool.end" else "failure"
            tool_seq.append((name, status, e["event_id"]))

    # 找连续失败 ≥3 的序列
    fail_runs = []
    current_run = []
    for name, status, eid in tool_seq:
        if status == "failure":
            current_run.append((name, eid))
        else:
            if len(current_run) >= 3:
                fail_runs.append(current_run)
            current_run = []
    if len(current_run) >= 3:
        fail_runs.append(current_run)

    if fail_runs:
        header(f"{R}⚠ 连续失败序列{X}")
        for run in fail_runs:
            name = run[0][0]
            count = len(run)
            print(f"  {R}⟳{X} {name} 连续失败 {R}{count}{X} 次 — 疑似陷入循环")
            for n, eid in run:
                print(f"     {D}{eid}{X}")
        footer()


# ── 入口 ───────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: trace_viz.py <trace.jsonl> [--no-color]", file=sys.stderr)
        sys.exit(1)

    try:
        events = load(sys.argv[1])
    except FileNotFoundError:
        print(f"Error: file not found: {sys.argv[1]}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if not events:
        print("Error: empty trace", file=sys.stderr)
        sys.exit(1)

    render(events)
