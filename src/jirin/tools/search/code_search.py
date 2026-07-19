"""Code search utility for Android source code.

Provides functions to search Android source code for relevant patterns.
Two-tier architecture:
- Tier 1 (built-in knowledge): Pre-built framework path mappings and call chains
  that work without local AOSP source.
- Tier 2 (local source): Optional local AOSP source tree for deep search.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


# Comprehensive AOSP framework component path mapping
FRAMEWORK_PATHS: dict[str, str] = {
    # AMS / Activity management
    "ActivityManagerService": "frameworks/base/services/core/java/com/android/server/am/ActivityManagerService.java",
    "ActivityThread": "frameworks/base/core/java/android/app/ActivityThread.java",
    "ActiveServices": "frameworks/base/services/core/java/com/android/server/am/ActiveServices.java",
    "BroadcastQueue": "frameworks/base/services/core/java/com/android/server/am/BroadcastQueue.java",
    "ProcessList": "frameworks/base/services/core/java/com/android/server/am/ProcessList.java",
    "OomAdjuster": "frameworks/base/services/core/java/com/android/server/am/OomAdjuster.java",
    # Activity/Window management
    "ActivityTaskManagerService": "frameworks/base/services/core/java/com/android/server/wm/ActivityTaskManagerService.java",
    "WindowManagerService": "frameworks/base/services/core/java/com/android/server/wm/WindowManagerService.java",
    "RootWindowContainer": "frameworks/base/services/core/java/com/android/server/wm/RootWindowContainer.java",
    # Input system
    "InputDispatcher": "frameworks/native/services/inputflinger/dispatcher/InputDispatcher.cpp",
    "InputMethodManagerService": "frameworks/base/services/core/java/com/android/server/inputmethod/InputMethodManagerService.java",
    "InputManagerService": "frameworks/base/services/core/java/com/android/server/input/InputManagerService.java",
    # Native crash handling
    "debuggerd": "system/core/debuggerd/",
    "signal_catcher": "art/runtime/signal_catcher.cc",
    "jni_internal": "art/runtime/jni/jni_internal.cc",
    "art_crash": "art/runtime/runtime.cc",
    # System server
    "SystemServer": "frameworks/base/services/java/com/android/server/SystemServer.java",
    "Watchdog": "frameworks/base/services/core/java/com/android/server/Watchdog.java",
    # Content providers
    "ContentResolver": "frameworks/base/core/java/android/content/ContentResolver.java",
    "ContentProvider": "frameworks/base/core/java/android/content/ContentProvider.java",
    # Binder / IPC
    "Binder": "frameworks/base/core/java/android/os/Binder.java",
    "BinderProxy": "frameworks/base/core/java/android/os/BinderProxy.java",
    # Memory management
    "LowMemoryKiller": "frameworks/base/services/core/java/com/android/server/am/LowmemKiller.java",
    "ActivityManagerGlobal": "frameworks/base/core/java/android/app/ActivityManagerGlobal.java",
    # SharedPreferences
    "SharedPreferencesImpl": "frameworks/base/core/java/android/app/SharedPreferencesImpl.java",
    "QueuedWork": "frameworks/base/core/java/android/app/QueuedWork.java",
    # Class loading
    "PathClassLoader": "libcore/dalvik/src/main/java/dalvik/system/PathClassLoader.java",
    "DexClassLoader": "libcore/dalvik/src/main/java/dalvik/system/DexClassLoader.java",
}


# Call chain knowledge for common issue types
CALL_CHAINS: dict[str, list[dict[str, str]]] = {
    "je_crash_flow": [
        {"component": "App Code", "action": "Throws uncaught exception"},
        {"component": "ActivityThread", "action": "handleUncaughtException()"},
        {"component": "ActivityManagerService", "action": "handleApplicationCrash()"},
        {"component": "ActivityManagerService", "action": "errorToDropBox()"},
        {"component": "Process", "action": "Process dies, restart if needed"},
    ],
    "anr_input_timeout": [
        {"component": "InputDispatcher", "action": "Dispatches input event to app"},
        {"component": "InputMethodManagerService", "action": "Monitors dispatch timeout (5s)"},
        {"component": "ActivityManagerService", "action": "Detects ANR condition"},
        {"component": "ActivityManagerService", "action": "Collects traces, sends ANR"},
    ],
    "anr_service_timeout": [
        {"component": "ActiveServices", "action": "Starts/binds service"},
        {"component": "ActiveServices", "action": "Monitors service timeout (20s fg, 200s bg)"},
        {"component": "ActivityManagerService", "action": "Service timeout -> ANR"},
    ],
    "anr_broadcast_timeout": [
        {"component": "BroadcastQueue", "action": "Delivers broadcast to receiver"},
        {"component": "BroadcastQueue", "action": "Monitors receiver timeout (10s fg, 60s bg)"},
        {"component": "ActivityManagerService", "action": "Broadcast timeout -> ANR"},
    ],
    "ne_crash_flow": [
        {"component": "App/Native Code", "action": "Invalid memory access / signal"},
        {"component": "Kernel", "action": "Delivers signal (SIGSEGV/SIGABRT/etc)"},
        {"component": "debuggerd", "action": "Catches signal, dumps tombstone"},
        {"component": "signal_catcher", "action": "ART signal handler"},
        {"component": "ActivityManagerService", "action": "Native crash -> process death"},
    ],
}


# Issue type -> relevant components mapping
ISSUE_COMPONENT_MAP: dict[str, list[str]] = {
    "je": [
        "ActivityManagerService", "ActivityThread", "Binder",
        "PathClassLoader", "DexClassLoader", "SharedPreferencesImpl",
    ],
    "anr": [
        "ActivityManagerService", "InputDispatcher", "ActiveServices",
        "BroadcastQueue", "QueuedWork", "SharedPreferencesImpl",
        "ContentResolver", "WindowManagerService",
    ],
    "ne": [
        "debuggerd", "signal_catcher", "jni_internal", "art_crash",
        "ActivityManagerService",
    ],
}


class CodeSearch:
    """Search Android source code for relevant patterns.

    Two-tier architecture:
    - Tier 1: Built-in knowledge (framework paths, call chains) - always available
    - Tier 2: Local AOSP source search - requires configured source directory
    """

    def __init__(self, source_dir: str | Path | None = None) -> None:
        self._source_dir = Path(source_dir) if source_dir else None

    @property
    def has_local_source(self) -> bool:
        """Whether a local AOSP source directory is configured and exists."""
        return self._source_dir is not None and self._source_dir.exists()

    def search_class(self, class_name: str) -> list[dict[str, Any]]:
        """Search for a class definition in AOSP source.

        Args:
            class_name: Fully qualified class name.

        Returns:
            List of matching file locations.
        """
        results: list[dict[str, Any]] = []

        # Check built-in knowledge first
        simple_name = class_name.split(".")[-1]
        if simple_name in FRAMEWORK_PATHS:
            results.append({
                "file": FRAMEWORK_PATHS[simple_name],
                "class": class_name,
                "source": "built-in",
            })

        # If local source available, do actual file search
        if self.has_local_source:
            parts = class_name.split(".")
            file_name = f"{parts[-1]}.java"
            for match in self._source_dir.rglob(file_name):
                rel_path = str(match.relative_to(self._source_dir))
                # Avoid duplicates
                if not any(r["file"] == rel_path for r in results):
                    results.append({
                        "file": rel_path,
                        "class": class_name,
                        "source": "local",
                    })

        return results

    def search_method(
        self, method_name: str, class_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Search for a method definition in AOSP source.

        Args:
            method_name: Method name to search for.
            class_name: Optional class name to narrow search.

        Returns:
            List of matching locations.
        """
        results: list[dict[str, Any]] = []

        if not self.has_local_source:
            # Without local source, return path hint if class is known
            if class_name and class_name.split(".")[-1] in FRAMEWORK_PATHS:
                simple = class_name.split(".")[-1]
                results.append({
                    "file": FRAMEWORK_PATHS[simple],
                    "method": method_name,
                    "hint": f"Search for '{method_name}' in {FRAMEWORK_PATHS[simple]}",
                    "source": "built-in",
                })
            return results

        # Local source search: find file then grep for method
        if class_name:
            parts = class_name.split(".")
            file_name = f"{parts[-1]}.java"
            search_files = list(self._source_dir.rglob(file_name))
        else:
            search_files = []

        for source_file in search_files[:5]:
            try:
                content = source_file.read_text(encoding="utf-8", errors="replace")
                pattern = rf"(?:public|private|protected)?\s*\w+\s+{re.escape(method_name)}\s*\("
                for i, line in enumerate(content.split("\n"), 1):
                    if re.search(pattern, line):
                        rel_path = str(source_file.relative_to(self._source_dir))
                        results.append({
                            "file": rel_path,
                            "method": method_name,
                            "line": i,
                            "snippet": line.strip()[:120],
                            "source": "local",
                        })
                        if len(results) >= 10:
                            break
            except OSError:
                continue

        return results

    def get_framework_path(self, component: str) -> str | None:
        """Get the AOSP framework path for a component.

        Args:
            component: Component name (e.g., 'ActivityManagerService').

        Returns:
            Relative path in AOSP source tree, or None.
        """
        return FRAMEWORK_PATHS.get(component)

    def get_component_call_chain(
        self, flow_name: str
    ) -> list[dict[str, str]]:
        """Get the call chain for a known issue flow.

        Args:
            flow_name: Flow identifier (e.g., 'je_crash_flow', 'anr_input_timeout').

        Returns:
            List of steps in the call chain.
        """
        return CALL_CHAINS.get(flow_name, [])

    def get_relevant_call_chains(
        self, issue_type: str
    ) -> dict[str, list[dict[str, str]]]:
        """Get all relevant call chains for an issue type.

        Args:
            issue_type: Issue type ('je', 'anr', 'ne').

        Returns:
            Dictionary of flow_name -> call chain steps.
        """
        prefix = f"{issue_type}_"
        return {
            name: chain
            for name, chain in CALL_CHAINS.items()
            if name.startswith(prefix)
        }

    def search_by_issue_type(
        self,
        issue_type: str,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for relevant AOSP source paths based on issue type and context.

        This is the main entry point for agents to get source code context.

        Args:
            issue_type: Issue type ('je', 'anr', 'ne').
            context: Optional parsed data context (exception class, signal name, etc).

        Returns:
            List of relevant source paths and call chains.
        """
        results: list[dict[str, Any]] = []
        context = context or {}

        # Get relevant components for this issue type
        relevant_components = ISSUE_COMPONENT_MAP.get(issue_type, [])

        # Add framework paths for relevant components
        for component in relevant_components:
            if component in FRAMEWORK_PATHS:
                results.append({
                    "type": "framework_path",
                    "component": component,
                    "path": FRAMEWORK_PATHS[component],
                })

        # If context provides specific class names, search for them
        if issue_type == "je":
            exc_class = context.get("exception_class", "")
            if exc_class:
                simple = exc_class.split(".")[-1]
                if simple in FRAMEWORK_PATHS:
                    results.append({
                        "type": "exception_source",
                        "component": simple,
                        "path": FRAMEWORK_PATHS[simple],
                    })

        elif issue_type == "anr":
            anr_type = context.get("anr_type", "")
            chain_map = {
                "input_timeout": "anr_input_timeout",
                "service_timeout": "anr_service_timeout",
                "broadcast_timeout": "anr_broadcast_timeout",
            }
            if anr_type in chain_map:
                chain = self.get_component_call_chain(chain_map[anr_type])
                if chain:
                    results.append({
                        "type": "call_chain",
                        "flow": chain_map[anr_type],
                        "steps": chain,
                    })

        elif issue_type == "ne":
            if context.get("is_jni_related"):
                jni_components = ["jni_internal", "signal_catcher"]
                for comp in jni_components:
                    if comp in FRAMEWORK_PATHS:
                        results.append({
                            "type": "jni_source",
                            "component": comp,
                            "path": FRAMEWORK_PATHS[comp],
                        })

        # Add general call chain for this issue type
        default_chains = {
            "je": "je_crash_flow",
            "ne": "ne_crash_flow",
        }
        if issue_type in default_chains:
            chain = self.get_component_call_chain(default_chains[issue_type])
            if chain:
                results.append({
                    "type": "call_chain",
                    "flow": default_chains[issue_type],
                    "steps": chain,
                })

        return results

    def format_source_context(
        self,
        issue_type: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Format source code context as a readable string for agent prompts.

        Args:
            issue_type: Issue type.
            context: Parsed data context.

        Returns:
            Formatted string with relevant source paths and call chains.
        """
        results = self.search_by_issue_type(issue_type, context)
        if not results:
            return ""

        lines: list[str] = []
        paths_seen: set[str] = set()
        chains_seen: set[str] = set()

        for r in results:
            if r["type"] in ("framework_path", "exception_source", "jni_source"):
                path = r["path"]
                if path not in paths_seen:
                    paths_seen.add(path)
                    comp = r["component"]
                    lines.append(f"- {comp}: `{path}`")
            elif r["type"] == "call_chain":
                flow = r["flow"]
                if flow not in chains_seen:
                    chains_seen.add(flow)
                    lines.append(f"\nCall Chain ({flow}):")
                    for i, step in enumerate(r["steps"], 1):
                        lines.append(
                            f"  {i}. [{step['component']}] {step['action']}"
                        )

        return "\n".join(lines) if lines else ""
