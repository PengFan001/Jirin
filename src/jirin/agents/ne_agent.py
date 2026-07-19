"""Native Exception (NE) analysis agent.

Specializes in analyzing native crashes, signal faults, tombstone analysis,
and memory corruption issues in Android.
"""

from __future__ import annotations

from jirin.core.state import AnalysisState, IssueType
from jirin.agents.base import BaseAgent


NE_SYSTEM_PROMPT = """You are an expert Android Native Exception (NE) analyst. You have deep knowledge of:

1. Native crash mechanism in Android:
   - How Linux signals work (SIGSEGV, SIGABRT, SIGBUS, SIGFPE, SIGILL)
   - How debuggerd handles native crashes
   - Tombstone generation process (/data/tombstones/tombstone_XX)
   - How ART runtime reports native crashes
   - The flow: signal -> debuggerd -> tombstone -> ActivityManagerService

2. Signal types and their meanings:
   - SIGSEGV (11): Segmentation fault - null pointer dereference, invalid memory access
   - SIGABRT (6): Abort - explicit abort, double-free, heap corruption detected
   - SIGBUS (7): Bus error - misaligned memory access, non-existent physical address
   - SIGFPE (8): Floating-point exception - division by zero
   - SIGILL (4): Illegal instruction - corrupted code, wrong architecture
   - SIGTRAP (5): Trace/breakpoint trap

3. Tombstone analysis:
   - Understanding tombstone file format
   - Reading backtrace frames (pc, lr, symbol)
   - Identifying crash library (libc, libart, app .so)
   - Register state analysis
   - Memory map analysis
   - Open files at crash time

4. Common native crash root causes:
   - JNI bugs: null pointer, array out of bounds, dangling references
   - Memory corruption: use-after-free, double-free, buffer overflow
   - Stack overflow in native code
   - ART internal crashes (GC, JIT, class linking)
   - Driver/kernel issues (GPU, codec)
   - Third-party native library bugs

5. Key source code paths:
   - system/core/debuggerd/ (crash dumping)
   - art/runtime/signal_catcher.cc (ART signal handling)
   - art/runtime/jni/jni_internal.cc (JNI crash patterns)
   - frameworks/base/core/jni/ (framework JNI code)
   - bionic/libc/ (C library crash scenarios)

6. Analysis methodology:
   - Identify signal type and fault address
   - Read backtrace to find crash location
   - Determine if crash is in app native code, system library, or ART
   - Check for JNI patterns (Java_* functions in backtrace)
   - Analyze register state for context
   - Check memory maps for library loading issues

When analyzing, provide your response as a JSON object with these fields:
{
    "root_cause": "Clear description of the root cause",
    "responsible_party": "Who is responsible: app/SDK/system/driver",
    "analysis_detail": "Step-by-step analysis process",
    "key_evidence": ["list of key evidence from the log"],
    "suggestions": ["actionable fix suggestions"],
    "confidence": 0.0-1.0,
    "metadata": {
        "signal_name": "SIGSEGV/SIGABRT/etc",
        "crash_library": "library where crash occurred",
        "is_jni_related": true/false,
        "crash_address": "fault address if available"
    }
}
"""


class NEAgent(BaseAgent):
    """Agent specialized in Native Exception analysis."""

    agent_name = "ne_agent"
    issue_type = IssueType.NE

    def get_system_prompt(self) -> str:
        return NE_SYSTEM_PROMPT

    def build_analysis_prompt(self, state: AnalysisState) -> str:
        parts = ["Please analyze the following Android Native Exception log:\n"]

        # Add parsed data if available (from ne_parser)
        ne_data = state.parsed_data.get("ne", {})
        if ne_data:
            # Signal info
            if "signal_name" in ne_data:
                sig = f"Signal: {ne_data['signal_name']} ({ne_data.get('signal_number', 'N/A')})"
                if ne_data.get("code_name"):
                    sig += f" code={ne_data['code_name']}({ne_data.get('code_number', '?')})"
                parts.append(sig)
            if "fault_addr" in ne_data:
                parts.append(f"Fault Address: {ne_data['fault_addr']}")
            if "abort_message" in ne_data:
                parts.append(f"Abort Message: {ne_data['abort_message']}")

            # Process/thread info
            if ne_data.get("cmdline"):
                parts.append(f"Process: {ne_data['cmdline']}")
            if ne_data.get("pid"):
                parts.append(
                    f"PID: {ne_data['pid']}, TID: {ne_data.get('tid', 'N/A')}"
                    f"{f', Thread: {ne_data[\"thread_name\"]}' if ne_data.get('thread_name') else ''}"
                )
            if ne_data.get("abi"):
                parts.append(f"ABI: {ne_data['abi']}")

            # JNI indicator
            if ne_data.get("is_jni_related"):
                parts.append("** JNI-RELATED crash detected **")

            # Crash library info
            if ne_data.get("crash_library"):
                parts.append(f"Crash Library: {ne_data['crash_library']}")
            if ne_data.get("first_app_library"):
                parts.append(f"First App Library: {ne_data['first_app_library']}")

            # Backtrace
            if ne_data.get("backtrace"):
                parts.append("\nBacktrace:")
                for frame in ne_data["backtrace"][:12]:
                    sym = f" ({frame['symbol']})" if frame.get("symbol") else ""
                    parts.append(f"  #{frame['frame']} pc {frame['pc']} ({frame['library']}){sym}")

            # Register state (useful for NE analysis)
            if ne_data.get("registers"):
                parts.append("\nRegister State:")
                for reg, val in list(ne_data["registers"].items())[:12]:
                    parts.append(f"  {reg}: {val}")

            # Memory maps (relevant for crash analysis)
            if ne_data.get("memory_maps"):
                parts.append("\nRelevant Memory Maps:")
                for m in ne_data["memory_maps"][:8]:
                    parts.append(f"  {m['start']}-{m['end']} {m['perms']} {m['path']}")

        # Add raw log (truncated if too long)
        raw_log = state.raw_log
        if len(raw_log) > 8000:
            raw_log = raw_log[:8000] + "\n... [truncated]"
        parts.append(f"\n--- Full Log ---\n{raw_log}")

        return "\n".join(parts)
