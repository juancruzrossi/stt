from __future__ import annotations

import sys
from pathlib import Path

from huggingface_hub import snapshot_download

from .model_config import MODEL_FILE_HASHES, MODEL_REPO, MODEL_REVISION, verify_model
from .transcriber import load_model


def install_model(path: Path) -> None:
    snapshot_download(
        repo_id=MODEL_REPO,
        revision=MODEL_REVISION,
        local_dir=path,
        allow_patterns=list(MODEL_FILE_HASHES),
    )
    verify_model(path)
    load_model(str(path), device="cpu", compute_type="int8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m stt.install_model MODEL_PATH")
    install_model(Path(sys.argv[1]))
    print(f"Model ready: {MODEL_REPO}@{MODEL_REVISION}")


if __name__ == "__main__":
    main()
