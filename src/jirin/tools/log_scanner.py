"""Multi-platform log directory scanner and structure learner.

Supports Qualcomm, MTK (MediaTek), and SPRD (Spreadtrum) log directory structures.
Can learn new directory structures and remember them for future use.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LogFileMapping:
    """Maps a logical log type to a physical file path."""

    log_type: str  # e.g., "main_log", "tombstone", "anr_trace"
    file_path: Path
    priority: int = 0  # Higher = more important
    description: str = ""


@dataclass
class PlatformLogStructure:
    """Describes the log directory structure of a platform."""

    platform_name: str  # e.g., "qualcomm", "mtk", "sprd"
    fingerprint: str  # Hash of directory structure
    log_files: list[LogFileMapping] = field(default_factory=list)
    adb_commands: dict[str, str] = field(default_factory=dict)  # log_type -> adb command
    notes: str = ""


# Default known platform structures
KNOWN_PLATFORMS: dict[str, dict[str, Any]] = {
    "qualcomm": {
        "indicators": ["logcat_all.txt", "tombstones", "ramdump", "QPST"],
        "log_files": {
            "main_log": ["logcat_all.txt", "logcat.txt", "logcat_main.txt"],
            "system_log": ["logcat_system.txt"],
            "radio_log": ["logcat_radio.txt"],
            "event_log": ["logcat_events.txt"],
            "tombstone": ["tombstones/tombstone_*", "tombstone_*"],
            "anr_trace": ["anr traces.txt", "traces.txt", "ANR/*.txt"],
            "kernel_log": ["kmsg.txt", "kernel_log.txt", "dmesg.txt"],
            "bugreport": ["bugreport*.txt", "bugreport*.zip"],
            "dumpstate": ["dumpstate*.txt", "dumpstate*.zip"],
        },
        "adb_commands": {
            "main_log": "adb logcat -d > logcat_all.txt",
            "system_log": "adb logcat -d -b system > logcat_system.txt",
            "radio_log": "adb logcat -d -b radio > logcat_radio.txt",
            "event_log": "adb logcat -d -b events > logcat_events.txt",
            "tombstone": "adb pull /data/tombstones/",
            "anr_trace": "adb pull /data/anr/",
            "kernel_log": "adb shell cat /proc/kmsg > kmsg.txt",
            "bugreport": "adb bugreport ./",
        },
    },
    "mtk": {
        "indicators": ["mdlog", "MobileLog", "APLog", "mtklog"],
        "log_files": {
            "main_log": ["MobileLog/logcat.log", "MobileLog/*.log", "logcat.txt"],
            "system_log": ["MobileLog/system.log", "logcat_system.txt"],
            "radio_log": ["mdlog/*.log", "MobileLog/radio.log"],
            "event_log": ["MobileLog/event.log", "logcat_events.txt"],
            "tombstone": ["MobileLog/tombstones/*", "tombstones/tombstone_*"],
            "anr_trace": ["MobileLog/ANR/*", "anr traces.txt"],
            "kernel_log": ["MobileLog/kernel.log", "kmsg.txt"],
            "bugreport": ["bugreport*.txt", "bugreport*.zip"],
            "dumpstate": ["APLog/dumpstate*", "dumpstate*.txt"],
        },
        "adb_commands": {
            "main_log": "adb pull /sdcard/mtklog/MobileLog/",
            "radio_log": "adb pull /sdcard/mtklog/mdlog/",
            "tombstone": "adb pull /data/tombstones/",
            "anr_trace": "adb pull /data/anr/",
            "kernel_log": "adb shell cat /proc/kmsg > kmsg.txt",
            "bugreport": "adb bugreport ./",
        },
    },
    "sprd": {
        "indicators": ["sprdlog", "Spreadtrum", "log_sprd", "modem_log"],
        "log_files": {
            "main_log": ["logcat.txt", "sprdlog/logcat.txt", "log_sprd/logcat.txt"],
            "system_log": ["logcat_system.txt", "sprdlog/system.log"],
            "radio_log": ["modem_log/*.log", "sprdlog/radio.log"],
            "event_log": ["logcat_events.txt"],
            "tombstone": ["tombstones/tombstone_*", "sprdlog/tombstones/*"],
            "anr_trace": ["anr traces.txt", "sprdlog/anr/*"],
            "kernel_log": ["kmsg.txt", "sprdlog/kmsg.txt"],
            "bugreport": ["bugreport*.txt", "bugreport*.zip"],
            "dumpstate": ["dumpstate*.txt"],
        },
        "adb_commands": {
            "main_log": "adb logcat -d > logcat.txt",
            "tombstone": "adb pull /data/tombstones/",
            "anr_trace": "adb pull /data/anr/",
            "kernel_log": "adb shell cat /proc/kmsg > kmsg.txt",
            "bugreport": "adb bugreport ./",
        },
    },
}


class LogDirectoryScanner:
    """Scans log directories and identifies platform structure.

    Can:
    - Identify the platform (Qualcomm/MTK/SPRD) from directory structure
    - Map logical log types to physical file paths
    - Learn new directory structures and persist them
    - Suggest ADB commands for missing log files
    """

    MEMORY_FILE = ".jirin/log_structure_memory.json"

    def __init__(self, memory_path: str | Path | None = None) -> None:
        self._memory_path = Path(memory_path) if memory_path else Path(self.MEMORY_FILE)
        self._learned_structures: dict[str, dict] = {}
        self._load_memory()

    def scan_directory(self, log_dir: Path) -> PlatformLogStructure | None:
        """Scan a log directory and identify its structure.

        Args:
            log_dir: Path to the log directory.

        Returns:
            PlatformLogStructure if recognized, None otherwise.
        """
        if not log_dir.exists():
            logger.error("Log directory does not exist: %s", log_dir)
            return None

        # Compute directory fingerprint
        fingerprint = self._compute_fingerprint(log_dir)

        # Check learned structures first
        for name, structure in self._learned_structures.items():
            if structure.get("fingerprint") == fingerprint:
                logger.info("Matched learned structure: %s", name)
                return self._build_structure(name, structure, log_dir)

        # Check known platforms
        for platform_name, platform_def in KNOWN_PLATFORMS.items():
            if self._matches_platform(log_dir, platform_def):
                logger.info("Matched known platform: %s", platform_name)
                return self._build_known_structure(platform_name, platform_def, log_dir)

        # Unknown structure - try to learn it
        logger.warning("Unknown log directory structure: %s", log_dir)
        return self._build_generic_structure(log_dir, fingerprint)

    def scan_batch(self, log_dirs: list[Path]) -> list[tuple[Path, PlatformLogStructure | None]]:
        """Scan multiple log directories.

        Args:
            log_dirs: List of log directory paths.

        Returns:
            List of (path, structure) tuples.
        """
        results = []
        for log_dir in log_dirs:
            structure = self.scan_directory(log_dir)
            results.append((log_dir, structure))
        return results

    def get_missing_files(
        self, structure: PlatformLogStructure, log_dir: Path
    ) -> list[tuple[str, str]]:
        """Get list of missing log files with ADB commands to obtain them.

        Args:
            structure: The identified platform structure.
            log_dir: The log directory to check.

        Returns:
            List of (log_type, adb_command) for missing files.
        """
        missing = []
        existing_files = set()

        # Collect all existing files
        for f in log_dir.rglob("*"):
            if f.is_file():
                existing_files.add(f.name.lower())

        # Check which log types are missing
        for mapping in structure.log_files:
            if mapping.file_path.exists():
                continue
            # Check if any variant exists
            found = False
            for f in log_dir.rglob("*"):
                if f.is_file() and mapping.file_path.name.lower() in f.name.lower():
                    found = True
                    break
            if not found:
                adb_cmd = structure.adb_commands.get(mapping.log_type, "")
                if adb_cmd:
                    missing.append((mapping.log_type, adb_cmd))

        return missing

    def learn_structure(self, name: str, log_dir: Path) -> None:
        """Learn and persist a new directory structure.

        Args:
            name: Name to associate with this structure.
            log_dir: The log directory to learn from.
        """
        fingerprint = self._compute_fingerprint(log_dir)
        file_list = []
        for f in log_dir.rglob("*"):
            if f.is_file():
                rel_path = str(f.relative_to(log_dir))
                file_list.append(rel_path)

        self._learned_structures[name] = {
            "fingerprint": fingerprint,
            "files": file_list[:200],  # Limit to 200 files
            "directory": str(log_dir),
            "learned_at": str(Path(log_dir).name),
        }
        self._save_memory()
        logger.info("Learned new structure: %s (%d files)", name, len(file_list))

    def _compute_fingerprint(self, log_dir: Path) -> str:
        """Compute a hash fingerprint of the directory structure."""
        parts = []
        for item in sorted(log_dir.iterdir()):
            if item.is_dir():
                parts.append(f"D:{item.name}")
            elif item.is_file():
                parts.append(f"F:{item.name}")

        content = "|".join(parts)
        return hashlib.md5(content.encode()).hexdigest()

    def _matches_platform(self, log_dir: Path, platform_def: dict) -> bool:
        """Check if a directory matches a known platform structure."""
        indicators = platform_def.get("indicators", [])
        dir_names = set()
        file_names = set()

        for item in log_dir.rglob("*"):
            if item.is_dir():
                dir_names.add(item.name.lower())
            elif item.is_file():
                file_names.add(item.name.lower())

        all_names = dir_names | file_names
        match_count = sum(1 for ind in indicators if ind.lower() in all_names)
        return match_count >= max(1, len(indicators) // 2)

    def _build_known_structure(
        self, platform_name: str, platform_def: dict, log_dir: Path
    ) -> PlatformLogStructure:
        """Build a PlatformLogStructure from a known platform definition."""
        log_files = []
        for log_type, patterns in platform_def.get("log_files", {}).items():
            for pattern in patterns:
                matches = list(log_dir.glob(pattern))
                if not matches:
                    matches = list(log_dir.rglob(pattern))
                for match in matches[:1]:  # Take first match
                    log_files.append(LogFileMapping(
                        log_type=log_type,
                        file_path=match,
                        priority=0,
                        description=f"{platform_name} {log_type}",
                    ))
                    break

        return PlatformLogStructure(
            platform_name=platform_name,
            fingerprint=self._compute_fingerprint(log_dir),
            log_files=log_files,
            adb_commands=platform_def.get("adb_commands", {}),
        )

    def _build_structure(
        self, name: str, structure: dict, log_dir: Path
    ) -> PlatformLogStructure:
        """Build structure from learned data."""
        log_files = []
        for rel_path in structure.get("files", []):
            full_path = log_dir / rel_path
            if full_path.is_file():
                log_files.append(LogFileMapping(
                    log_type="unknown",
                    file_path=full_path,
                    description=f"Learned: {name}",
                ))

        return PlatformLogStructure(
            platform_name=name,
            fingerprint=structure.get("fingerprint", ""),
            log_files=log_files,
        )

    def _build_generic_structure(
        self, log_dir: Path, fingerprint: str
    ) -> PlatformLogStructure:
        """Build a generic structure for unknown directories."""
        log_files = []
        # Try to find common log files
        common_patterns = [
            ("main_log", ["logcat*.txt", "*.log"]),
            ("tombstone", ["tombstone*", "tombstones/*"]),
            ("anr_trace", ["*anr*", "*traces*"]),
            ("kernel_log", ["kmsg*", "dmesg*", "kernel*"]),
        ]

        for log_type, patterns in common_patterns:
            for pattern in patterns:
                matches = list(log_dir.rglob(pattern))
                for match in matches[:2]:
                    if match.is_file():
                        log_files.append(LogFileMapping(
                            log_type=log_type,
                            file_path=match,
                            description="Generic detection",
                        ))

        return PlatformLogStructure(
            platform_name="unknown",
            fingerprint=fingerprint,
            log_files=log_files,
            notes="Unknown platform structure. Use learn_structure() to teach Jirin.",
        )

    def _load_memory(self) -> None:
        """Load learned structures from disk."""
        if self._memory_path.exists():
            try:
                self._learned_structures = json.loads(
                    self._memory_path.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load structure memory: %s", e)
                self._learned_structures = {}

    def _save_memory(self) -> None:
        """Persist learned structures to disk."""
        self._memory_path.parent.mkdir(parents=True, exist_ok=True)
        self._memory_path.write_text(
            json.dumps(self._learned_structures, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
