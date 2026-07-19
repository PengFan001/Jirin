"""Native Exception log parser.

Parses Android tombstone and native crash logs to extract structured
information about native crashes.
"""

from __future__ import annotations

import re
from typing import Any


def parse_ne_log(log: str) -> dict[str, Any]:
    """Parse a Native Exception log into structured data.

    Args:
        log: Raw log content containing a native crash.

    Returns:
        Structured data with native crash details.
    """
    result: dict[str, Any] = {}

    # Extract signal info
    signal_match = re.search(
        r"signal\s+(\d+)\s+\((SIG\w+)\)(?:.*?code\s+(\d+)\s+\((\w+)\))?.*?fault addr\s+(\S+)",
        log,
    )
    if signal_match:
        result["signal_number"] = int(signal_match.group(1))
        result["signal_name"] = signal_match.group(2)
        if signal_match.group(3):
            result["code_number"] = int(signal_match.group(3))
            result["code_name"] = signal_match.group(4)
        result["fault_addr"] = signal_match.group(5)

    # Extract abort message
    abort_match = re.search(r"Abort message:\s*'(.+?)'", log)
    if abort_match:
        result["abort_message"] = abort_match.group(1)
    else:
        abort_match = re.search(r'Abort message:\s*"(.+?)"', log)
        if abort_match:
            result["abort_message"] = abort_match.group(1)

    # Extract process info
    proc_match = re.search(r"pid:\s*(\d+),\s*tid:\s*(\d+),\s*name:\s*(\S+)", log)
    if proc_match:
        result["pid"] = proc_match.group(1)
        result["tid"] = proc_match.group(2)
        result["thread_name"] = proc_match.group(3)

    # Extract cmdline
    cmdline_match = re.search(r"Cmd line:\s*(\S+)", log)
    if cmdline_match:
        result["cmdline"] = cmdline_match.group(1)

    # Extract ABI
    abi_match = re.search(r"ABI:\s*'(\S+)'", log)
    if abi_match:
        result["abi"] = abi_match.group(1)

    # Extract backtrace
    bt_frames = re.findall(
        r"#(\d+)\s+pc\s+(0x[0-9a-fA-F]+)\s+(\S+)(?:\s+\((.+?)\))?",
        log,
    )
    if bt_frames:
        result["backtrace"] = [
            {
                "frame": int(f[0]),
                "pc": f[1],
                "library": f[2],
                "symbol": f[3] if f[3] else "",
            }
            for f in bt_frames
        ]

    # Extract register state
    registers = re.findall(
        r"\s+(x\d+|r\d+|sp|pc|lr)\s+([0-9a-fA-F]{8,16})",
        log,
    )
    if registers:
        result["registers"] = {reg[0]: reg[1] for reg in registers}

    # Extract memory maps (relevant ones)
    maps = re.findall(
        r"([0-9a-fA-F]+)-([0-9a-fA-F]+)\s+(\S+)\s+\S+\s+\S+\s+(.+)",
        log,
    )
    if maps:
        result["memory_maps"] = [
            {
                "start": m[0],
                "end": m[1],
                "perms": m[2],
                "path": m[3].strip(),
            }
            for m in maps[:20]
        ]

    # Check if JNI related
    jni_indicators = [
        r"Java_",
        r"JNI_",
        r"art/runtime/jni",
        r"libart.*JNI",
    ]
    result["is_jni_related"] = any(
        re.search(p, log) for p in jni_indicators
    )

    # Determine crash library
    if bt_frames:
        first_app_frame = None
        for frame in bt_frames:
            lib = frame[2]
            if "libc.so" not in lib and "libart" not in lib and "linker" not in lib:
                first_app_frame = lib
                break
        result["crash_library"] = bt_frames[0][2]
        if first_app_frame:
            result["first_app_library"] = first_app_frame

    return result


def detect_ne(log: str) -> bool:
    """Detect if the log contains a Native Exception.

    Args:
        log: Raw log content.

    Returns:
        True if NE patterns are detected.
    """
    ne_indicators = [
        r"signal \d+ \(SIG\w+\)",
        r"Abort message:",
        r"tombstone",
        r"Native crash",
        r"fatal signal \d+",
        r"#\d+ pc 0x[0-9a-fA-F]+",
    ]
    return any(re.search(p, log) for p in ne_indicators)
