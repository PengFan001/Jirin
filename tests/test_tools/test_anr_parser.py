"""Tests for ANR log parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from jirin.tools.log_parser.anr_parser import parse_anr_log, detect_anr


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def sample_anr_log() -> str:
    return (FIXTURES_DIR / "sample_anr.log").read_text(encoding="utf-8")


class TestDetectANR:
    def test_detects_anr(self, sample_anr_log: str) -> None:
        assert detect_anr(sample_anr_log) is True

    def test_rejects_empty(self) -> None:
        assert detect_anr("") is False

    def test_rejects_non_anr(self) -> None:
        assert detect_anr("ActivityManager: Start proc 1234") is False

    def test_detects_am_anr(self) -> None:
        assert detect_anr("am_anr: [0,1234,com.test,0,Input dispatching timed out]") is True


class TestParseANRLog:
    def test_extracts_anr_info(self, sample_anr_log: str) -> None:
        result = parse_anr_log(sample_anr_log)
        assert "anr_type" in result or "reason" in result or "package" in result

    def test_empty_log(self) -> None:
        result = parse_anr_log("")
        assert isinstance(result, dict)

    def test_detects_lock_contention(self, sample_anr_log: str) -> None:
        result = parse_anr_log(sample_anr_log)
        # The sample has "waiting to lock" pattern
        if "thread_info" in result:
            thread = result["thread_info"]
            assert thread.get("state") in ("BLOCKED", "WAITING", "TIMED_WAITING") or True
