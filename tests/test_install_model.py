from __future__ import annotations

from pathlib import Path

import pytest

import stt.install_model as installer
from stt.model_config import MODEL_FILE_HASHES, MODEL_REPO, MODEL_REVISION


def test_install_model_downloads_pinned_files_and_verifies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        installer,
        "snapshot_download",
        lambda **kwargs: calls.append(("download", kwargs)),
    )
    monkeypatch.setattr(
        installer, "verify_model", lambda path: calls.append(("verify", path))
    )
    monkeypatch.setattr(
        installer,
        "load_model",
        lambda path, **_kwargs: calls.append(("load", path)),
    )

    installer.install_model(tmp_path)

    assert calls == [
        (
            "download",
            {
                "repo_id": MODEL_REPO,
                "revision": MODEL_REVISION,
                "local_dir": tmp_path,
                "allow_patterns": list(MODEL_FILE_HASHES),
            },
        ),
        ("verify", tmp_path),
        ("load", str(tmp_path)),
    ]
