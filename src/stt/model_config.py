from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path

MODEL_NAME = "base"
MODEL_REPO = "Systran/faster-whisper-base"
MODEL_REVISION = "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66"
MODEL_FILE_HASHES = {
    "config.json": "56a6d8110d311f19c8f0471e562832c7527f146b567275bfca59fcf7c184da9a",
    "model.bin": "d01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9",
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
