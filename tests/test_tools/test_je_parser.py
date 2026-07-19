"""Tests for Java Exception log parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from jirin.tools.log_parser.je_parser import parse_je_log, detect_je


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def sample_je_log() -> str:
    """Load sample JE log."""
    return (FIXTURES_DIR / "sample_je.log").read_text(encoding="utf-8")


@pytest.fixture
def empty_log() -> str:
    return ""


@pytest.fixture
def non_je_log() -> str:
    return "01-15 10:30:00.000 1234 1234 I ActivityManager: Start proc 1234:com.example.app"


class TestDetectJE:
    """Tests for detect_je function."""

    def test_detects_fatal_exception(self, sample_je_log: str) -> None:
        assert detect_je(sample_je_log) is True

    def test_rejects_empty(self, empty_log: str) -> None:
        assert detect_je(empty_log) is False

    def test_rejects_non_je(self, non_je_log: str) -> None:
        assert detect_je(non_je_log) is False

    def test_detects_java_lang_error(self) -> None:
        log = "java.lang.OutOfMemoryError: Failed to allocate"
        assert detect_je(log) is True


class TestParseJELog:
    """Tests for parse_je_log function."""

    def test_extracts_process_info(self, sample_je_log: str) -> None:
        result = parse_je_log(sample_je_log)
        assert result["process"] == "com.example.app"
        assert result["pid"] == "1234"

    def test_extracts_exception_class(self, sample_je_log: str) -> None:
        result = parse_je_log(sample_je_log)
        assert result["exception_class"] == "java.lang.NullPointerException"

    def test_extracts_exception_message(self, sample_je_log: str) -> None:
        result = parse_je_log(sample_je_log)
        assert "TextView.setText" in result["exception_message"]

    def test_extracts_stack_trace(self, sample_je_log: str) -> None:
        result = parse_je_log(sample_je_log)
        assert "stack_trace" in result
        assert len(result["stack_trace"]) > 0
        # First frame should be in app code
        assert result["stack_trace"][0]["method"] == "com.example.app.MainActivity.updateUI"

    def test_identifies_app_frames(self, sample_je_log: str) -> None:
        result = parse_je_log(sample_je_log)
        assert result["has_app_frames"] is True
        assert result["first_app_frame"]["method"] == "com.example.app.MainActivity.updateUI"

    def test_empty_log_returns_empty_dict(self, empty_log: str) -> None:
        result = parse_je_log(empty_log)
        assert "exception_class" not in result
        assert "stack_trace" not in result

    def test_caused_by_chain(self) -> None:
        log = """FATAL EXCEPTION: main
Process: com.test, PID: 100
java.lang.RuntimeException: Unable to start activity
Caused by: java.lang.IllegalStateException: Already destroyed
Caused by: java.lang.NullPointerException: null reference"""
        result = parse_je_log(log)
        assert "caused_by" in result
        assert len(result["caused_by"]) == 2
        assert result["caused_by"][0]["class"] == "java.lang.IllegalStateException"
        assert result["caused_by"][1]["class"] == "java.lang.NullPointerException"
