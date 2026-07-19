"""Tests for Native Exception log parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from jirin.tools.log_parser.ne_parser import parse_ne_log, detect_ne


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def sample_ne_log() -> str:
    return (FIXTURES_DIR / "sample_ne.log").read_text(encoding="utf-8")


class TestDetectNE:
    def test_detects_signal(self, sample_ne_log: str) -> None:
        assert detect_ne(sample_ne_log) is True

    def test_rejects_empty(self) -> None:
        assert detect_ne("") is False

    def test_rejects_non_ne(self) -> None:
        assert detect_ne("ActivityManager: Start proc 1234") is False

    def test_detects_sigabrt(self) -> None:
        assert detect_ne("signal 6 (SIGABRT), code 1") is True


class TestParseNELog:
    def test_extracts_signal_info(self, sample_ne_log: str) -> None:
        result = parse_ne_log(sample_ne_log)
        assert "signal" in result
        assert result["signal"]["number"] == 11
        assert result["signal"]["name"] == "SIGSEGV"

    def test_extracts_fault_addr(self, sample_ne_log: str) -> None:
        result = parse_ne_log(sample_ne_log)
        assert result["signal"]["fault_addr"] == "0x0000000000000000"

    def test_extracts_backtrace(self, sample_ne_log: str) -> None:
        result = parse_ne_log(sample_ne_log)
        assert "backtrace" in result
        assert len(result["backtrace"]) > 0

    def test_extracts_process_info(self, sample_ne_log: str) -> None:
        result = parse_ne_log(sample_ne_log)
        assert result.get("process") == "com.example.app" or result.get("cmdline") == "com.example.app"

    def test_extracts_abi(self, sample_ne_log: str) -> None:
        result = parse_ne_log(sample_ne_log)
        assert result.get("abi") == "arm64"

    def test_empty_log(self) -> None:
        result = parse_ne_log("")
        assert isinstance(result, dict)
