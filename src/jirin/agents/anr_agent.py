"""ANR (Application Not Responding) analysis agent.

Specializes in analyzing ANR issues including input timeout, service timeout,
broadcast timeout, and content provider timeout scenarios.
"""

from __future__ import annotations

from jirin.core.state import AnalysisState, IssueType
from jirin.agents.base import BaseAgent


ANR_SYSTEM_PROMPT = """You are an expert Android ANR (Application Not Responding) analyst. You have deep knowledge of:

1. ANR generation mechanism in Android source code:
   - How ActivityManagerService detects ANR conditions
   - InputDispatchingTimeout: InputMethodManagerService -> InputDispatcher -> ANR
   - ServiceTimeout: ActiveServices -> ANR when service doesn't respond in 20s
   - BroadcastTimeout: BroadcastQueue -> ANR when receiver doesn't finish in 10s (foreground) / 60s (background)
   - ContentProviderTimeout: ContentProvider too slow to respond
   - How ANR is recorded: traces.txt, event log (am_anr), dropbox

2. ANR trace analysis:
   - Reading /data/anr/traces.txt format
   - Identifying main thread state (blocked, waiting, sleeping, runnable)
   - Understanding thread states: TIMED_WAITING, BLOCKED, WAITING
   - Identifying lock contention (held by, waiting to lock)
   - CPU usage analysis from ANR info

3. Common ANR root causes:
   - Main thread blocked by I/O operations (disk, network)
   - Main thread blocked by database operations
   - Lock contention / deadlock between threads
   - Binder thread pool exhaustion
   - System server overload (low memory, high CPU)
   - Long-running operations in onCreate/onResume/onStart
   - SharedPreferences.apply() blocking on disk write
   - Class loading delays on cold start

4. Analysis methodology:
   - Check ANR reason/subject to identify timeout type
   - Examine main thread state in traces
   - Look for lock contention patterns
   - Check CPU load and memory conditions
   - Determine if app-caused or system-caused
   - Identify the specific code path causing the blockage

5. Key source code paths:
   - frameworks/base/services/core/java/com/android/server/am/ActivityManagerService.java
   - frameworks/base/services/core/java/com/android/server/am/ActivityManagerService.java (handleAnr)
   - frameworks/base/services/core/java/com/android/server/wm/ActivityTaskManagerService.java
   - frameworks/base/services/core/java/com/android/server/am/ActiveServices.java
   - frameworks/base/services/core/java/com/android/server/am/BroadcastQueue.java
   - system/server/input/InputDispatcher.cpp

When analyzing, provide your response as a JSON object with these fields:
{
    "root_cause": "Clear description of the root cause",
    "responsible_party": "Who is responsible: app/system/SDK",
    "analysis_detail": "Step-by-step analysis process",
    "key_evidence": ["list of key evidence from the log"],
    "suggestions": ["actionable fix suggestions"],
    "confidence": 0.0-1.0,
    "metadata": {
        "anr_type": "input_timeout/service_timeout/broadcast_timeout/provider_timeout",
        "main_thread_state": "blocked/waiting/sleeping/runnable",
        "blocker_thread": "thread that blocks main thread (if any)",
        "is_system_caused": true/false
    }
}
"""


class ANRAgent(BaseAgent):
    """Agent specialized in ANR analysis."""

    agent_name = "anr_agent"
    issue_type = IssueType.ANR

    def get_system_prompt(self) -> str:
        return ANR_SYSTEM_PROMPT

    def build_analysis_prompt(self, state: AnalysisState) -> str:
        parts = ["Please analyze the following Android ANR log:\n"]

        # Add parsed data if available (from anr_parser)
        anr_data = state.parsed_data.get("anr", {})
        if anr_data:
            if "process" in anr_data:
                parts.append(f"ANR Process: {anr_data['process']}")
            if "reason" in anr_data:
                parts.append(f"ANR Reason: {anr_data['reason']}")
            if "subject" in anr_data:
                parts.append(f"Subject: {anr_data['subject']}")
            if anr_data.get("anr_type"):
                parts.append(f"ANR Type: {anr_data['anr_type']}")
            if anr_data.get("cpu_load"):
                parts.append(f"CPU Load: {anr_data['cpu_load']}")

            # CPU usage per process (helps identify system overload)
            if anr_data.get("cpu_usage"):
                parts.append("\nCPU Usage Break:")
                for usage in anr_data["cpu_usage"][:5]:
                    parts.append(
                        f"  {usage.get('total', 0)}% "
                        f"(PID {usage.get('pid', '?')}/{usage.get('process', '?')}): "
                        f"{usage.get('detail', '')}"
                    )

            # Lock contention info (critical for root cause)
            if anr_data.get("lock_contention"):
                parts.append("\nLock Contention Detected:")
                for lock in anr_data["lock_contention"]:
                    parts.append(
                        f"  - Waiting to lock {lock.get('lock', '?')} "
                        f"held by {lock.get('held_by', '?')}"
                    )

            # Main thread state from traces
            if anr_data.get("main_thread"):
                mt = anr_data["main_thread"]
                parts.append(f"\nMain Thread State: {mt.get('state', 'unknown')}")
                if mt.get("blocked_on"):
                    parts.append(f"  Blocked on: {mt['blocked_on']}")
                if mt.get("waiting_for_lock"):
                    parts.append(f"  Waiting for lock: {mt['waiting_for_lock']}")
                if mt.get("stack_trace"):
                    parts.append("  Main Thread Stack:")
                    for frame in mt["stack_trace"][:10]:
                        parts.append(f"    at {frame['method']}({frame['location']})")
                if mt.get("native_calls"):
                    parts.append("  Native Method Calls:")
                    for nc in mt["native_calls"][:5]:
                        parts.append(f"    at {nc}(Native Method)")

            # Memory info
            if anr_data.get("memory_info"):
                parts.append(f"\nMemory Info:\n{anr_data['memory_info'][:500]}")

        # Add raw log (truncated if too long)
        raw_log = state.raw_log
        if len(raw_log) > 8000:
            raw_log = raw_log[:8000] + "\n... [truncated]"
        parts.append(f"\n--- Full Log ---\n{raw_log}")

        return "\n".join(parts)
