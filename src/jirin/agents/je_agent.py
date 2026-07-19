"""Java Exception (JE) analysis agent.

Specializes in analyzing Java/Kotlin exceptions, crashes, and fatal errors
in Android applications.
"""

from __future__ import annotations

from jirin.core.state import AnalysisState, IssueType
from jirin.agents.base import BaseAgent


JE_SYSTEM_PROMPT = """You are an expert Android Java Exception analyst. You have deep knowledge of:

1. Android framework exception handling mechanisms:
   - How uncaught exceptions propagate through the Android runtime
   - Thread.setDefaultUncaughtExceptionHandler() mechanism
   - ActivityManagerService crash handling flow
   - How Android records and reports Java crashes (dropbox, event log)

2. Common Java Exception types and their root causes:
   - NullPointerException: object reference issues, lifecycle problems
   - IllegalStateException: component lifecycle violations
   - SecurityException: permission issues
   - OutOfMemoryError: memory management problems
   - StackOverflowError: recursive call issues
   - ClassNotFoundException/NoClassDefFoundError: class loading issues
   - ConcurrentModificationException: thread safety issues
   - RemoteException: IPC/binder failures

3. Analysis methodology:
   - Identify the exception type and message
   - Trace the stack to find the root cause location
   - Determine if the crash is in app code or framework code
   - Check for known patterns (lifecycle issues, threading bugs)
   - Identify the responsible party (app developer vs framework vs third-party SDK)

4. Source code understanding:
   - ActivityThread.handleUncaughtException()
   - ActivityManagerService.handleApplicationCrash()
   - AndroidRuntime.errorToDropBox()
   - Process crash handling in frameworks/base/

When analyzing, provide your response as a JSON object with these fields:
{
    "root_cause": "Clear description of the root cause",
    "responsible_party": "Who is responsible: app/SDK/system",
    "analysis_detail": "Step-by-step analysis process",
    "key_evidence": ["list of key evidence from the log"],
    "suggestions": ["actionable fix suggestions"],
    "confidence": 0.0-1.0,
    "metadata": {
        "exception_type": "specific exception class",
        "crash_location": "method/class where crash occurred",
        "is_lifecycle_related": true/false
    }
}
"""


class JEAgent(BaseAgent):
    """Agent specialized in Java Exception analysis."""

    agent_name = "je_agent"
    issue_type = IssueType.JE

    def get_system_prompt(self) -> str:
        return JE_SYSTEM_PROMPT

    def build_analysis_prompt(self, state: AnalysisState) -> str:
        parts = ["Please analyze the following Android Java Exception log:\n"]

        # Add parsed data if available (from je_parser)
        je_data = state.parsed_data.get("je", {})
        if je_data:
            if "exception_class" in je_data:
                exc_line = je_data["exception_class"]
                if je_data.get("exception_message"):
                    exc_line += f": {je_data['exception_message']}"
                parts.append(f"Exception: {exc_line}")
            if "process" in je_data:
                parts.append(f"Process: {je_data['process']} (PID: {je_data.get('pid', 'N/A')})")

            # Caused-by chain (important for root cause tracing)
            if je_data.get("caused_by"):
                parts.append("\nCaused-by Chain:")
                for cb in je_data["caused_by"]:
                    msg = f" - {cb['class']}"
                    if cb.get("message"):
                        msg += f": {cb['message']}"
                    parts.append(msg)

            # Stack trace (top frames)
            if je_data.get("stack_trace"):
                parts.append("\nStack Trace (top frames):")
                for frame in je_data["stack_trace"][:15]:
                    parts.append(f"  at {frame['method']}({frame['location']})")

            # App code frames indicator
            if je_data.get("has_app_frames") and je_data.get("first_app_frame"):
                fa = je_data["first_app_frame"]
                parts.append(f"\nFirst App Code Frame: {fa['method']}({fa['location']})")

            # Full fatal exception block
            if je_data.get("fatal_block"):
                parts.append(f"\nFatal Exception Block:\n{je_data['fatal_block'][:2000]}")

        # Add raw log (truncated if too long)
        raw_log = state.raw_log
        if len(raw_log) > 8000:
            raw_log = raw_log[:8000] + "\n... [truncated]"
        parts.append(f"\n--- Full Log ---\n{raw_log}")

        return "\n".join(parts)
