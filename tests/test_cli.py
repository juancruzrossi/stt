from __future__ import annotations

from click.testing import CliRunner

from stt.cli import main


def test_help_lists_core_commands() -> None:
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "listen" in result.output
    assert "transcribe" in result.output
    assert "models" in result.output


def test_transcribe_missing_file_fails_before_model_load() -> None:
    result = CliRunner().invoke(main, ["transcribe", "missing.wav"])

    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_listen_rejects_invalid_tap_interval() -> None:
    result = CliRunner().invoke(main, ["listen", "--tap-interval", "0"])

    assert result.exit_code != 0
    assert "Invalid value for '--tap-interval'" in result.output
