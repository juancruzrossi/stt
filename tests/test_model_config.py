from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from stt import model_config, transcriber
from stt.cache import faster_whisper_cache_entries
from stt.model_config import MODEL_NAME, MODEL_REVISION, configured_model, verify_model


def test_model_revision_is_immutable_commit() -> None:
    assert len(MODEL_REVISION) == 40
    assert all(character in "0123456789abcdef" for character in MODEL_REVISION)


def test_configured_model_uses_existing_pinned_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(model_config, "MODEL_FILE_HASHES", {})
    monkeypatch.setenv("STT_MODEL_PATH", str(tmp_path))

    assert configured_model(MODEL_NAME) == str(tmp_path)


def test_configured_model_rejects_missing_pinned_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = tmp_path / "missing"
    monkeypatch.setenv("STT_MODEL_PATH", str(missing))

    with pytest.raises(FileNotFoundError, match="Pinned STT model was not found"):
        configured_model(MODEL_NAME)


def test_cache_does_not_fallback_when_pinned_model_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("STT_MODEL_PATH", str(tmp_path / "missing"))
    monkeypatch.setenv("HF_HOME", str(tmp_path / "huggingface"))
    old_model = tmp_path / "huggingface" / "hub" / "models--old--faster-whisper"
    old_model.mkdir(parents=True)

    assert faster_whisper_cache_entries() == []


def test_load_model_is_offline_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def whisper_model(model: str, **kwargs: object) -> object:
        captured.update(model=model, **kwargs)
        return object()

    monkeypatch.delenv("STT_MODEL_PATH", raising=False)
    monkeypatch.setattr(transcriber, "WhisperModel", whisper_model)

    transcriber.load_model(MODEL_NAME)

    assert captured["model"] == MODEL_NAME
    assert captured["local_files_only"] is True


def test_verify_model_rejects_modified_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model_file = tmp_path / "model.bin"
    model_file.write_bytes(b"expected")
    monkeypatch.setattr(
        model_config,
        "MODEL_FILE_HASHES",
        {"model.bin": hashlib.sha256(b"expected").hexdigest()},
    )
    verify_model(tmp_path)

    model_file.write_bytes(b"modified")

    with pytest.raises(ValueError, match="Model integrity check failed"):
        verify_model(tmp_path)
