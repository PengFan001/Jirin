"""ADB tool wrapper for device interaction.

Provides functions to interact with Android devices via ADB
for log collection and device state inspection.
Phase 2 feature - basic structure for future implementation.
"""

from __future__ import annotations

import subprocess
from typing import Any


class ADBTool:
    """Wrapper for ADB commands.

    Provides methods to:
    - Collect logs (logcat, bugreport, tombstones)
    - Check device state
    - Pull files from device
    """

    def __init__(self, device_serial: str | None = None) -> None:
        self._device = device_serial
        self._adb_cmd = "adb"

    def _run(self, args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
        """Run an ADB command.

        Args:
            args: Command arguments.
            timeout: Command timeout in seconds.

        Returns:
            Command result.
        """
        cmd = [self._adb_cmd]
        if self._device:
            cmd.extend(["-s", self._device])
        cmd.extend(args)

        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def get_logcat(self, filter_spec: str = "", timeout: int = 10) -> str:
        """Get logcat output.

        Args:
            filter_spec: Logcat filter (e.g., "AndroidRuntime:E *:S").
            timeout: Timeout in seconds.

        Returns:
            Logcat output.
        """
        args = ["logcat", "-d"]
        if filter_spec:
            args.extend(filter_spec.split())
        result = self._run(args, timeout=timeout)
        return result.stdout

    def get_tombstone(self, index: int = 0) -> str:
        """Get a tombstone file from device.

        Args:
            index: Tombstone index (0-9).

        Returns:
            Tombstone content.
        """
        result = self._run(["shell", f"cat /data/tombstones/tombstone_{index:02d}"])
        return result.stdout

    def get_anr_traces(self) -> str:
        """Get ANR traces file.

        Returns:
            Traces content.
        """
        result = self._run(["shell", "cat /data/anr/traces.txt"])
        return result.stdout

    def get_device_info(self) -> dict[str, str]:
        """Get basic device information.

        Returns:
            Device info dictionary.
        """
        info = {}
        props = [
            ("model", "ro.product.model"),
            ("android_version", "ro.build.version.release"),
            ("sdk_version", "ro.build.version.sdk"),
            ("build_fingerprint", "ro.build.fingerprint"),
            ("abi", "ro.product.cpu.abi"),
        ]
        for key, prop in props:
            result = self._run(["shell", "getprop", prop])
            info[key] = result.stdout.strip()

        return info

    def list_devices(self) -> list[str]:
        """List connected devices.

        Returns:
            List of device serial numbers.
        """
        result = self._run(["devices"])
        devices = []
        for line in result.stdout.strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices
