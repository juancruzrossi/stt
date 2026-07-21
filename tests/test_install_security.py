from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_unix_installer_has_no_remote_execution_or_self_update() -> None:
    installer = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "curl" not in installer
    assert "git pull" not in installer
    assert "sudo" not in installer
    assert "chmod -R" not in installer
    assert "UV_PYTHON_DOWNLOADS=never" in installer
    assert "python -m stt.install_model" in installer


def test_launchers_use_the_installed_environment_without_uv() -> None:
    unix_launcher = (ROOT / "stt").read_text(encoding="utf-8")
    windows_launcher = (ROOT / "stt.cmd").read_text(encoding="utf-8")

    assert "uv run" not in unix_launcher
    assert "uv run" not in windows_launcher
    assert "HF_HUB_OFFLINE=1" in unix_launcher
    assert "HF_HUB_OFFLINE=1" in windows_launcher
