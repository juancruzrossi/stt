from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


KNOWN_SIZE_MODELS = {
    "tiny",
    "tiny.en",
    "base",
    "base.en",
    "small",
    "small.en",
    "medium",
    "medium.en",
    "large-v1",
    "large-v2",
    "large-v3",
    "large",
    "distil-large-v3",
    "large-v3-turbo",
    "turbo",
}


@dataclass(frozen=True)
class ModelCacheEntry:
    repo_id: str
    path: Path
    size_bytes: int


def huggingface_home() -> Path:
    if hf_home := os.environ.get("HF_HOME"):
        return Path(hf_home).expanduser()
    if xdg_cache := os.environ.get("XDG_CACHE_HOME"):
        return Path(xdg_cache).expanduser() / "huggingface"
    return Path.home() / ".cache" / "huggingface"


def huggingface_hub_cache() -> Path:
    if hf_hub_cache := os.environ.get("HF_HUB_CACHE"):
        return Path(hf_hub_cache).expanduser()
    return huggingface_home() / "hub"


def model_to_repo_id(model: str) -> str:
    if "/" in model:
        return model
    if model in KNOWN_SIZE_MODELS:
        return f"Systran/faster-whisper-{model}"
    return model


def repo_id_to_cache_dir(repo_id: str) -> Path:
    return huggingface_hub_cache() / f"models--{repo_id.replace('/', '--')}"


def dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_symlink():
            continue
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"


def faster_whisper_cache_entries() -> list[ModelCacheEntry]:
    hub = huggingface_hub_cache()
    if not hub.exists():
        return []

    entries: list[ModelCacheEntry] = []
    for path in sorted(hub.glob("models--*faster-whisper*")):
        if not path.is_dir():
            continue
        repo_id = path.name.removeprefix("models--").replace("--", "/")
        entries.append(
            ModelCacheEntry(repo_id=repo_id, path=path, size_bytes=dir_size(path))
        )
    return entries
