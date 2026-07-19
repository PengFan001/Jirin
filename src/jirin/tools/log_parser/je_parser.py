"""Java Exception log parser.

Parses Android crash logs to extract structured information about
Java exceptions and fatal errors.
"""

from __future__ import annotations

import re
from typing import Any


def parse_je_log(log: str) -> dict[str, Any]:
    """Parse a Java Exception log into structured data.

    Args:
        log: Raw log content containing a Java crash.

    Returns:
        Structured data with exception details.
    """
    result: dict[str, Any] = {}

    # Extract FATAL EXCEPTION block
    fatal_match = re.search(
        r"FATAL EXCEPTION.*?\n(.*?)(?=\n\n[A-Z]|\Z)",
        log,
        re.DOTALL,
    )
    if fatal_match:
        result["fatal_block"] = fatal_match.group(0)

    # Extract process info
    proc_match = re.search(r"Process:\s*(\S+),\s*PID:\s*(\d+)", log)
    if proc_match:
        result["process"] = proc_match.group(1)
        result["pid"] = proc_match.group(2)

    # Extract exception class and message
    exc_match = re.search(
        r"((?:java|android|kotlin)\.[\w.]+(?:Exception|Error))\s*:\s*(.*)",
        log,
    )
    if exc_match:
        result["exception_class"] = exc_match.group(1)
        result["exception_message"] = exc_match.group(2).strip()

    # Extract full stack trace
    stack_frames = re.findall(
        r"\s*at\s+([\w.$]+)\(([\w.]+:\d+)\)", log
    )
    if stack_frames:
        result["stack_trace"] = [
            {"method": frame[0], "location": frame[1]}
            for frame in stack_frames
        ]

    # Extract Caused by chain
    caused_by = re.findall(
        r"Caused by:\s+([\w.]+(?:Exception|Error))(?:\s*:\s*(.*))?",
        log,
    )
    if caused_by:
        result["caused_by"] = [
            {"class": cb[0], "message": cb[1].strip() if cb[1] else ""}
            for cb in caused_by
        ]

    # Extract "more" info (truncated frames)
    more_matches = re.findall(r"\.\.\.\s*(\d+)\s*more", log)
    if more_matches:
        result["truncated_frames"] = [int(m) for m in more_matches]

    # Identify if app code is in the stack
    app_frames = [
        f for f in stack_frames
        if not f[0].startswith(("java.", "android.", "dalvik.", "com.android."))
    ]
    result["has_app_frames"] = len(app_frames) > 0
    if app_frames:
        result["first_app_frame"] = {
            "method": app_frames[0][0],
            "location": app_frames[0][1],
        }

    return result


def detect_je(log: str) -> bool:
    """Detect if the log contains a Java Exception.

    Args:
        log: Raw log content.

    Returns:
        True if JE patterns are detected.
    """
    je_indicators = [
        r"FATAL EXCEPTION",
        r"java\.lang\.\w+Exception",
        r"java\.lang\.\w+Error",
        r"android\.util\.AndroidRuntimeException",
    ]
    return any(re.search(p, log) for p in je_indicators)
