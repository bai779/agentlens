#!/usr/bin/env python3
"""
AgentLens — Trace 异常检测

读取 AgentLens JSONL trace 文件，检测常见异常模式。

用法:
    python3 trace_check.py <trace.jsonl>
    python3 trace_check.py <trace.jsonl> --json    # JSON 格式输出
"""

import json
import sys
from collections import defaultdict
from typing import Any


def detect_anomalies(events: list[dict]) -> list[dict]:
    """Run all anomaly detectors, return list of findings."""
    findings = []

    # Build lookup structures
    events_by_type = defaultdict(list)
    for e in events:
        events_by_type[e["type"]].append(e)

    # --- Detector 1: Tool call loops ---
    # Same tool name called 3+ times in a row with failure status
    tool_events = [e for e in events if e["type"] in ("tool.end", "tool.error")]
    tool_name_runs = []  # [(tool_name, count, events)]
    for e in tool_events:
        name = e.get("data", {}).get("tool_name", "unknown")
        if tool_name_runs and tool_name_runs[-1][0] == name:
            tool_name_runs[-1] = (name, tool_name_runs[-1][1] + 1, tool_name_runs[-1][2] + [e])
        else:
            tool_name_runs.append((name, 1, [e]))

    for name, count, evts in tool_name_runs:
        if count >= 3:
            failures = sum(
                1 for ev in evts
                if ev.get("data", {}).get("status") == "failure" or ev["type"] == "tool.error"
            )
            if failures >= count * 0.5:  # at least 50% failures
                findings.append({
                    "detector": "tool_loop",
                    "severity": "high" if count >= 5 else "medium",
                    "message": f"工具 '{name}' 连续调用 {count} 次，其中 {failures} 次失败 — 疑似陷入循环",
                    "evidence": {
                        "tool_name": name,
                        "repeat_count": count,
                        "failure_count": failures,
                        "event_ids": [ev["event_id"] for ev in evts],
                    },
                    "suggestion": f"检查为何 '{name}' 反复失败。考虑切换策略、提前终止或向用户求助。"
                })

    # --- Detector 2: Excessive tool calls in a single turn ---
    tool_calls_per_turn = defaultdict(int)
    for e in events:
        if e["type"] in ("tool.start",):
            tid = e.get("turn_id") or e.get("parent_event_id") or "unknown"
            tool_calls_per_turn[tid] += 1

    for tid, count in tool_calls_per_turn.items():
        if count >= 10:
            findings.append({
                "detector": "excessive_tool_calls",
                "severity": "medium" if count < 20 else "high",
                "message": f"单轮内工具调用 {count} 次 — 可能效率低下或搜索迷路",
                "evidence": {"turn_id": tid, "tool_call_count": count},
                "suggestion": "考虑限制搜索范围、合并操作，或将子任务委托给子 agent。"
            })

    # --- Detector 3: Consecutive identical failed searches ---
    # Detect grep/search with empty results repeated
    search_patterns = []
    for e in events:
        if e["type"] in ("tool.end", "tool.error"):
            name = e.get("data", {}).get("tool_name", "")
            if name in ("grep_files", "file_search", "web_search"):
                inp = str(e.get("data", {}).get("tool_input", ""))
                status = e.get("data", {}).get("status", "unknown")
                search_patterns.append({"name": name, "input": inp, "status": status})

    for i in range(len(search_patterns) - 2):
        a, b, c = search_patterns[i], search_patterns[i+1], search_patterns[i+2]
        if a["name"] == b["name"] == c["name"]:
            # Check if all failed or returned empty
            all_bad = all(s["status"] in ("failure", "empty") for s in (a, b, c))
            if all_bad:
                findings.append({
                    "detector": "search_loop",
                    "severity": "medium",
                    "message": f"搜索操作 '{a['name']}' 连续 3 次失败/空结果 — 可能搜索策略有问题",
                    "evidence": {
                        "tool": a["name"],
                        "attempts": 3,
                    },
                    "suggestion": "缩小搜索范围、检查拼写、换用不同搜索工具，或向用户确认搜索目标。"
                })
                break  # only report first such chain

    # --- Detector 4: File read without subsequent use ---
    file_reads = [e for e in events if e.get("data", {}).get("file_action") == "read"
                  or (e["type"] == "tool.end" and e.get("data", {}).get("tool_name") == "read_file")]
    file_writes_or_edits = {
        e.get("data", {}).get("file_path", "")
        for e in events
        if e.get("data", {}).get("file_action") in ("write", "edit") or e["type"] == "edit.apply"
    }

    # Check if any read file was never written to (heuristic, not definitive)
    read_but_unused = 0
    for e in file_reads:
        fp = e.get("data", {}).get("file_path", "")
        if fp and fp not in file_writes_or_edits:
            read_but_unused += 1

    if read_but_unused >= 3:
        findings.append({
            "detector": "unused_reads",
            "severity": "low",
            "message": f"读取了 {read_but_unused} 个文件但未做任何修改 — 可能有冗余读取",
            "evidence": {"unused_read_count": read_but_unused, "total_reads": len(file_reads)},
            "suggestion": "检查是否有不必要的文件读取。在读取前确认该文件确实需要。"
        })

    # --- Detector 5: Sub-agent failures ---
    subagent_errors = events_by_type.get("subagent.error", [])
    subagent_spawns = len(events_by_type.get("subagent.spawn", []))
    if subagent_spawns > 0:
        error_rate = len(subagent_errors) / subagent_spawns
        if error_rate >= 0.5:
            findings.append({
                "detector": "subagent_failure",
                "severity": "high",
                "message": f"子 agent 失败率 {error_rate:.0%}（{len(subagent_errors)}/{subagent_spawns}）",
                "evidence": {
                    "spawns": subagent_spawns,
                    "errors": len(subagent_errors),
                    "rate": round(error_rate, 2),
                },
                "suggestion": "检查子 agent 的 prompt 和 task scope 是否合理。考虑降低并发数或简化子任务。"
            })

    # --- Detector 6: Low cache hit rate ---
    token_events = events_by_type.get("token.usage", [])
    if token_events:
        total_hit = sum(e.get("data", {}).get("cache_hit_tokens", 0) or 0 for e in token_events)
        total_miss = sum(e.get("data", {}).get("cache_miss_tokens", 0) or 0 for e in token_events)
        cache_total = total_hit + total_miss
        if cache_total > 0:
            hit_rate = total_hit / cache_total
            if hit_rate < 0.4:
                findings.append({
                    "detector": "low_cache_hit",
                    "severity": "medium",
                    "message": f"前缀缓存命中率仅 {hit_rate:.0%} — 上下文编排可能有问题",
                    "evidence": {
                        "hit_tokens": total_hit,
                        "miss_tokens": total_miss,
                        "hit_rate": round(hit_rate, 2),
                    },
                    "suggestion": "避免在轮次之间重排/重写早期上下文。使用 compact 保持前缀稳定。"
                })

    # --- Detector 7: High error rate ---
    tool_errors = len(events_by_type.get("tool.error", []))
    tool_ends = len(events_by_type.get("tool.end", []))
    total = tool_errors + tool_ends
    if total > 0:
        err_rate = tool_errors / total
        if err_rate >= 0.3:
            findings.append({
                "detector": "high_error_rate",
                "severity": "high" if err_rate >= 0.5 else "medium",
                "message": f"工具调用错误率 {err_rate:.0%}（{tool_errors}/{total}）",
                "evidence": {
                    "errors": tool_errors,
                    "total": total,
                    "rate": round(err_rate, 2),
                },
                "suggestion": "排查高频失败的工具。可能是权限问题、参数错误或网络不可达。"
            })

    return findings


def format_report(findings: list[dict]) -> str:
    if not findings:
        return "✅ 未检测到异常。Agent 运行正常。"

    lines = []
    lines.append("=" * 60)
    lines.append("  AgentLens — 异常检测报告")
    lines.append("=" * 60)
    lines.append("")

    severities = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    for i, f in enumerate(findings, 1):
        sev_icon = severities.get(f["severity"], "⚪")
        lines.append(f"  {i}. {sev_icon} [{f['severity'].upper()}] {f['detector']}")
        lines.append(f"     {f['message']}")
        if f.get("evidence"):
            lines.append(f"     证据: {json.dumps(f['evidence'], ensure_ascii=False)}")
        lines.append(f"     建议: {f['suggestion']}")
        lines.append("")

    lines.append("=" * 60)
    lines.append(f"  共检测到 {len(findings)} 个问题")
    lines.append("=" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: trace_check.py <trace.jsonl> [--json]", file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]
    output_json = "--json" in sys.argv

    try:
        with open(filepath) as f:
            events = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {filepath}: {e}", file=sys.stderr)
        sys.exit(1)

    findings = detect_anomalies(events)

    if output_json:
        print(json.dumps(findings, indent=2, ensure_ascii=False))
    else:
        print(format_report(findings))
