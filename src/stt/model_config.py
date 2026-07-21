from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path


MODEL_NAME = "small"
MODEL_REPO = "Systran/faster-whisper-small"
MODEL_REVISION = "536b0662742c02347bc0e980a01041f333bce120"
MODEL_FILE_HASHES = {
    "config.json": "b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828",
    "model.bin": "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671",
    "tokenizer.json": "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab",
    "vocabulary.txt": "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913",
}


def configured_model(model: str) -> str:
    if model != MODEL_NAME or not (configured_path := os.environ.get("STT_MODEL_PATH")):
        return model

    path = Path(configured_path).expanduser()
    if not path.is_dir() or any(
        not (path / filename).is_file() for filename in MODEL_FILE_HASHES
    ):
        raise FileNotFoundError(
            f"Pinned STT model was not found at {path}. Run install.sh again."
        )
    return str(path)


def verify_model(path: Path) -> None:
    for filename, expected_hash in MODEL_FILE_HASHES.items():
        model_file = path / filename
        digest = hashlib.sha256()
        with model_file.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        if not hmac.compare_digest(digest.hexdigest(), expected_hash):
            raise ValueError(f"Model integrity check failed: {filename}")
