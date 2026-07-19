"""Case classifier for root cause categorization.

Classifies analysis cases into categories for pattern recognition
and knowledge organization.
"""

from __future__ import annotations

from typing import Any


# Pre-defined root cause categories
ROOT_CAUSE_CATEGORIES = {
    "je": {
        "null_pointer": "NullPointerException and related null reference issues",
        "lifecycle": "Component lifecycle violations",
        "memory": "OutOfMemoryError and memory management issues",
        "permission": "SecurityException and permission issues",
        "concurrency": "Thread safety and concurrent access issues",
        "class_loading": "ClassNotFoundException and class loading failures",
        "ipc": "RemoteException and Binder/IPC failures",
        "state": "IllegalStateException and state management issues",
        "io": "I/O related exceptions",
        "other": "Other Java exceptions",
    },
    "anr": {
        "main_thread_io": "Main thread blocked by I/O operations",
        "main_thread_db": "Main thread blocked by database operations",
        "lock_contention": "Lock contention and deadlock",
        "binder_timeout": "Binder call timeout",
        "system_overload": "System CPU/memory overload",
        "sp_apply": "SharedPreferences.apply() blocking",
        "class_loading": "Class loading delay",
        "service_timeout": "Service execution timeout",
        "broadcast_timeout": "BroadcastReceiver execution timeout",
        "other": "Other ANR causes",
    },
    "ne": {
        "null_deref": "Null pointer dereference in native code",
        "use_after_free": "Use after free memory access",
        "buffer_overflow": "Buffer overflow",
        "double_free": "Double free memory corruption",
        "jni_error": "JNI API misuse",
        "art_internal": "ART runtime internal crash",
        "driver": "GPU/driver related crash",
        "signal_abort": "Explicit abort (SIGABRT)",
        "alignment": "Memory alignment issues",
        "other": "Other native crash causes",
    },
}


class Classifier:
    """Classifies analysis cases into root cause categories.

    Uses keyword matching and LLM-assisted classification to
    categorize root causes for pattern recognition.
    """

    def classify(self, learnings: dict[str, Any]) -> str:
        """Classify a case's root cause into a category.

        Args:
            learnings: Extracted learnings from reflection.

        Returns:
            Category identifier string.
        """
        issue_type = learnings.get("issue_type", "")
        root_cause = learnings.get("root_cause_pattern", "").lower()
        root_cause = f"{root_cause} {learnings.get('root_cause', '')}".lower()

        categories = ROOT_CAUSE_CATEGORIES.get(issue_type, {})
        if not categories:
            return "unknown"

        # Keyword matching
        for category, description in categories.items():
            if category == "other":
                continue
            keywords = self._get_category_keywords(issue_type, category)
            if any(kw in root_cause for kw in keywords):
                return category

        return "other"

    def _get_category_keywords(self, issue_type: str, category: str) -> list[str]:
        """Get keywords for a specific category.

        Args:
            issue_type: Issue type (je/anr/ne).
            category: Category name.

        Returns:
            List of keywords to match.
        """
        keyword_map = {
            ("je", "null_pointer"): ["null", "nullpointer", "npe", "空指针"],
            ("je", "lifecycle"): ["lifecycle", "destroy", "finish", "生命周期"],
            ("je", "memory"): ["oom", "outofmemory", "memory", "内存"],
            ("je", "permission"): ["security", "permission", "权限"],
            ("je", "concurrency"): ["concurrent", "thread", "sync", "race", "线程"],
            ("je", "class_loading"): ["classnotfound", "noclassdef", "classload", "类加载"],
            ("je", "ipc"): ["remote", "binder", "ipc", "transact"],
            ("je", "state"): ["illegalstate", "state", "状态"],
            ("je", "io"): ["ioexception", "file", "disk", "网络", "network"],
            ("anr", "main_thread_io"): ["i/o", "io", "file", "disk", "network", "网络"],
            ("anr", "main_thread_db"): ["database", "sqlite", "db", "数据库"],
            ("anr", "lock_contention"): ["lock", "deadlock", "blocked", "synchronized", "锁"],
            ("anr", "binder_timeout"): ["binder", "transact", "ipc"],
            ("anr", "system_overload"): ["cpu", "load", "memory", "system", "系统"],
            ("anr", "sp_apply"): ["sharedpreferences", "apply", "commit", "queuedwork"],
            ("anr", "class_loading"): ["classload", "dex", "class loading", "类加载"],
            ("anr", "service_timeout"): ["service", "servicetimeout"],
            ("anr", "broadcast_timeout"): ["broadcast", "broadcasttimeout", "receiver"],
            ("ne", "null_deref"): ["null", "0x0", "segv_maperr", "空指针"],
            ("ne", "use_after_free"): ["use-after-free", "freed", "dangling", "已释放"],
            ("ne", "buffer_overflow"): ["overflow", "buffer", "stack", "溢出"],
            ("ne", "double_free"): ["double-free", "double free", "heap corruption"],
            ("ne", "jni_error"): ["jni", "java_", "jni_internal"],
            ("ne", "art_internal"): ["art", "runtime", "gc", "jit"],
            ("ne", "driver"): ["gpu", "driver", "egl", "gl", "codec"],
            ("ne", "signal_abort"): ["abort", "sigabrt", "abort message"],
            ("ne", "alignment"): ["alignment", "bus", "sigbus", "对齐"],
        }
        return keyword_map.get((issue_type, category), [])
