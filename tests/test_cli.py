from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

import stt.cli as cli
from stt import audio
from stt.cache import ModelCacheEntry
from stt.cli import main, print_verbose_text


def test_help_lists_core_commands() -> None:
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "listen" in result.output
    assert "doctor" in result.output
    assert "transcribe" in result.output
    assert "models" in result.output


def test_transcribe_missing_file_fails_before_model_load() -> None:
    result = CliRunner().invoke(main, ["transcribe", "missing.wav"])

    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_transcribe_help_explains_input_formats() -> None:
    result = CliRunner().invoke(main, ["transcribe", "--help"])

    assert result.exit_code == 0
    assert "Transcribe a local audio/video file to text." in result.output


def test_listen_rejects_invalid_tap_interval() -> None:
    result = CliRunner().invoke(main, ["listen", "--tap-interval", "0"])

    assert result.exit_code != 0
    assert "Invalid value for '--tap-interval'" in result.output


def test_listen_help_includes_verbose_option() -> None:
    result = CliRunner().invoke(main, ["listen", "--help"])

    assert result.exit_code == 0
    assert "--verbose" in result.output


def test_print_verbose_text_separates_entries(capsys: pytest.CaptureFixture[str]) -> None:
    print_verbose_text("hello")

    assert capsys.readouterr().out == "----\nhello\n"


def test_doctor_reports_ready(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()
    monkeypatch.setattr(
        cli,
        "faster_whisper_cache_entries",
        lambda: [
            ModelCacheEntry(
                repo_id="Systran/faster-whisper-small",
                path=model_path,
                size_bytes=128,
            )
        ],
    )
    monkeypatch.setattr(cli.shutil, "which", lambda command: f"/bin/{command}")
    monkeypatch.setattr(
        audio,
        "probe_microphone",
        lambda: audio.MicrophoneProbe(ok=True, device="Built-in Microphone"),
    )

    result = CliRunner().invoke(main, ["doctor"])

    assert result.exit_code == 0
    assert "STT Doctor" in result.output
    assert "OK: stt is ready." in result.output
