"""ANR log parser.

Parses Android ANR logs and traces to extract structured information
about Application Not Responding issues.
"""

from __future__ import annotations

import re
from typing import Any


def parse_anr_log(log: str) -> dict[str, Any]:
    """Parse an ANR log into structured data.

    Args:
        log: Raw log content containing ANR information.

    Returns:
        Structured data with ANR details.
    """
    result: dict[str, Any] = {}

    # Extract ANR process
    anr_match = re.search(r"ANR in (\S+)", log)
    if anr_match:
        result["process"] = anr_match.group(1)

    # Extract ANR reason
    reason_match = re.search(r"Reason:\s*(.+?)(?:\n|$)", log)
    if reason_match:
        result["reason"] = reason_match.group(1).strip()

    # Extract Subject
    subject_match = re.search(r"Subject:\s*(.+?)(?:\n|$)", log)
    if subject_match:
        result["subject"] = subject_match.group(1).strip()

    # Extract ANR type from reason
    reason = result.get("reason", "")
    if "input" in reason.lower():
        result["anr_type"] = "input_timeout"
    elif "service" in reason.lower():
        result["anr_type"] = "service_timeout"
    elif "broadcast" in reason.lower():
        result["anr_type"] = "broadcast_timeout"
    elif "provider" in reason.lower():
        result["anr_type"] = "provider_timeout"

    # Extract CPU load
    load_match = re.search(r"LOAD:\s*([\d.]+)", log)
    if load_match:
        result["cpu_load"] = load_match.group(1)

    # Extract CPU usage per process
    cpu_usages = re.findall(
        r"([\d.]+)%\s*(\d+)/(\S+):\s*(.+)",
        log,
    )
    if cpu_usages:
        result["cpu_usage"] = [
            {
                "total": float(u[0]),
                "pid": u[1],
                "process": u[2],
                "detail": u[3],
            }
            for u in cpu_usages[:10]
        ]

    # Extract main thread info from traces
    main_thread = re.search(
        r'"main"\s+.*?(?=\n"[^"]*"|\Z)',
        log,
        re.DOTALL,
    )
    if main_thread:
        thread_text = main_thread.group(0)
        result["main_thread"] = _parse_thread_info(thread_text)

    # Extract lock information
    locks = re.findall(
        r"- waiting to lock.*?(\w+).*?held by.*?(\S+)",
        log,
    )
    if locks:
        result["lock_contention"] = [
            {"lock": lock[0], "held_by": lock[1]}
            for lock in locks
        ]

    # Extract memory info
    mem_match = re.search(r"MemInfo:.*?(?=\n\n|\Z)", log, re.DOTALL)
    if mem_match:
        result["memory_info"] = mem_match.group(0)[:500]

    return result


def _parse_thread_info(thread_text: str) -> dict[str, Any]:
    """Parse thread information from traces.

    Args:
        thread_text: Thread dump text block.

    Returns:
        Parsed thread state information.
    """
    info: dict[str, Any] = {}

    # Extract thread state
    state_match = re.search(
        r"java\.lang\.Thread\.State:\s*(\S+)", thread_text
    )
    if state_match:
        info["state"] = state_match.group(1)

    # Extract stack trace
    frames = re.findall(r"at ([\w.$]+)\(([\w.]+:\d+)\)", thread_text)
    if frames:
        info["stack_trace"] = [
            {"method": f[0], "location": f[1]} for f in frames
        ]

    # Check for native methods
    native_frames = re.findall(r"at ([\w.$]+)\(Native Method\)", thread_text)
    if native_frames:
        info["native_calls"] = native_frames

    # Check for blocked state
    blocked_match = re.search(
        r"blocked on.*?(\w+)", thread_text
    )
    if blocked_match:
        info["blocked_on"] = blocked_match.group(1)

    # Check for waiting state
    waiting_match = re.search(
        r"waiting to lock.*?(\w+)", thread_text
    )
    if waiting_match:
        info["waiting_for_lock"] = waiting_match.group(1)

    return info


def detect_anr(log: str) -> bool:
    """Detect if the log contains ANR information.

    Args:
        log: Raw log content.

    Returns:
        True if ANR patterns are detected.
    """
    anr_indicators = [
        r"ANR in",
        r"Subject: ANR",
        r"am_anr",
        r"Input dispatching timed out",
        r"executing service.*ANR",
    ]
    return any(re.search(p, log) for p in anr_indicators)
