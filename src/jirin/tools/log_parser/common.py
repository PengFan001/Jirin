"""Common log parsing utilities.

Shared functions for parsing Android log files across different crash types.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def read_log_file(file_path: str | Path) -> str:
    """Read a log file and return its content.

    Args:
        file_path: Path to the log file.

    Returns:
        Log file content as string.

    Raises:
        FileNotFoundError: If file doesn't exist.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def extract_timestamp(line: str) -> str | None:
    """Extract timestamp from a logcat line.

    Args:
        line: Log line in logcat format.

    Returns:
        Timestamp string or None.
    """
    match = re.match(r"(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)", line)
    if match:
        return match.group(1)
    return None


def extract_pid_tid(line: str) -> tuple[str | None, str | None]:
    """Extract PID and TID from a logcat line.

    Args:
        line: Log line in logcat format.

    Returns:
        Tuple of (pid, tid) or (None, None).
    """
    match = re.search(r"(\d+)\s+(\d+)\s+[VDIWEF]", line)
    if match:
        return match.group(1), match.group(2)
    return None, None


def extract_tag(line: str) -> str | None:
    """Extract log tag from a logcat line.

    Args:
        line: Log line in logcat format.

    Returns:
        Tag string or None.
    """
    match = re.search(r"[VDIWEF]\s+(\S+)\s*:", line)
    if match:
        return match.group(1)
    return None


def split_log_sections(log: str) -> list[str]:
    """Split a log into sections separated by blank lines.

    Args:
        log: Full log content.

    Returns:
        List of log sections.
    """
    return [section.strip() for section in re.split(r"\n\s*\n", log) if section.strip()]


def find_process_name(log: str) -> str | None:
    """Find the process name from log content.

    Args:
        log: Log content.

    Returns:
        Process name or None.
    """
    match = re.search(r"Process:\s*(\S+),\s*PID:\s*\d+", log)
    if match:
        return match.group(1)
    return None


def filter_logcat_by_pid(log: str, pid: str) -> str:
    """Filter logcat content to only include lines from a specific PID.

    Args:
        log: Full logcat content.
        pid: Process ID to filter for.

    Returns:
        Filtered log content.
    """
    lines = log.split("\n")
    filtered = []
    for line in lines:
        if re.search(rf"\b{pid}\b", line):
            filtered.append(line)
    return "\n".join(filtered)
