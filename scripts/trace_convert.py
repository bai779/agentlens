#!/usr/bin/env python3
"""
AgentLens — 原始日志转 Trace 格式转换器

将各种 agent 的原始日志转换为 AgentLens JSONL 格式。

用法:
    python3 trace_convert.py <input.log> --format <source> [--session-id <id>]
    python3 trace_convert.py <input.log> --format auto              # 自动检测

支持的格式:
    - codewhale    CodeWhale 运行日志
    - generic      通用格式（每行: [TIMESTAMP] TYPE: message）
    - auto         自动检测

输入可以是文件路径或 stdin（使用 -）。
"""

import json
import sys
import re
import uuid
from datetime import datetime, timezone


def make_event(event_id: int, ev_type: str, session_id: str, **kw) -> dict:
    """Create a standard trace event."""
    ev = {
        "event_id": f"evt-{event_id:04d}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": ev_type,
        "session_id": session_id,
        "data": {},
    }
    # Merge keyword arguments into data
    for k, v in kw.items():
        if k in ("parent_event_id", "turn_id", "agent_id", "agent_version", "model"):
            ev[k] = v
        elif k == "metadata":
            ev["metadata"] = v
        else:
            ev["data"][k] = v
    return ev


def convert_codewhale(lines: list[str], session_id: str) -> list[dict]:
    """Convert CodeWhale verbose log to trace events."""
    events = []
    eid = 0
    current_turn = None
    turn_eid = 0
    in_tool = False
    current_tool_name = None
    tool_start_eid = 0

    tool_start_pattern = re.compile(r'<invoke name="([^"]+)"')
    tool_end_pattern = re.compile(r'</invoke>')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        eid += 1

        # Detect turns (heuristic: user messages often contain specific markers)
        if "User:" in line or "用户:" in line or line.startswith(">>>"):
            if current_turn:
                turn_eid_tmp = eid
                eid += 1
                events.append(make_event(turn_eid_tmp, "turn.end", session_id,
                                          message="Turn ended", turn_id=current_turn))
            current_turn = f"turn-{uuid.uuid4().hex[:8]}"
            events.append(make_event(eid, "turn.start", session_id,
                                      message=line[:200], turn_id=current_turn))
            continue

        # Detect tool calls
        m = tool_start_pattern.search(line)
        if m:
            tool_name = m.group(1)
            current_tool_name = tool_name
            tool_start_eid = eid
            in_tool = True
            events.append(make_event(eid, "tool.start", session_id,
                                      tool_name=tool_name, turn_id=current_turn))
            continue

        if tool_end_pattern.search(line) and in_tool:
            eid += 1
            events.append(make_event(eid, "tool.end", session_id,
                                      tool_name=current_tool_name,
                                      status="success",
                                      tool_duration_ms=0,
                                      turn_id=current_turn))
            in_tool = False
            current_tool_name = None
            continue

        # Detect errors
        if any(kw in line.lower() for kw in ("error", "failed", "failure", "exception")):
            events.append(make_event(eid, "error", session_id,
                                      error_message=line[:200], turn_id=current_turn))
            continue

        # Generic event for other lines
        events.append(make_event(eid, "metric", session_id,
                                  message=line[:200], turn_id=current_turn))

    # Close last turn
    if current_turn:
        eid += 1
        events.append(make_event(eid, "turn.end", session_id,
                                  message="Session ended", turn_id=current_turn))

    return events


def convert_generic(lines: list[str], session_id: str) -> list[dict]:
    """Convert generic timestamped log to trace events."""
    events = []
    eid = 0

    ts_pattern = re.compile(r'^\[?(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})\]?\s+(.*)')

    for line in lines:
        line = line.strip()
        if not line:
            continue
        eid += 1

        m = ts_pattern.match(line)
        if m:
            ts_str = m.group(1)
            rest = m.group(2)
            ev = make_event(eid, "metric", session_id, message=rest[:200])
            ev["timestamp"] = ts_str.replace(" ", "T") + ("Z" if "T" in ts_str else "")
        else:
            ev = make_event(eid, "metric", session_id, message=line[:200])
        events.append(ev)

    return events


def auto_detect(lines: list[str]) -> str:
    """Auto-detect log format."""
    for line in lines[:20]:
        if '<invoke name="' in line or '<codewhale:' in line:
            return "codewhale"
    return "generic"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert agent logs to AgentLens trace format")
    parser.add_argument("input", help="Input log file (use - for stdin)")
    parser.add_argument("--format", choices=["codewhale", "generic", "auto"],
                        default="auto", help="Source format")
    parser.add_argument("--session-id", default=None,
                        help="Session ID (auto-generated if not provided)")
    args = parser.parse_args()

    # Read input
    if args.input == "-":
        lines = sys.stdin.readlines()
    else:
        with open(args.input) as f:
            lines = f.readlines()

    session_id = args.session_id or f"session-{uuid.uuid4().hex[:12]}"
    fmt = args.format
    if fmt == "auto":
        fmt = auto_detect(lines)

    if fmt == "codewhale":
        events = convert_codewhale(lines, session_id)
    elif fmt == "generic":
        events = convert_generic(lines, session_id)
    else:
        print(f"Unknown format: {fmt}", file=sys.stderr)
        sys.exit(1)

    for ev in events:
        print(json.dumps(ev, ensure_ascii=False))
