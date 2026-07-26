from pathlib import Path

TERMS_PATH = Path.home() / ".config" / "stt" / "terms.txt"


def load_terms(path: Path = TERMS_PATH) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []

    return [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]


def save_terms(terms: list[str], path: Path = TERMS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(
        "".join(f"{term}\n" for term in terms),
        encoding="utf-8",
    )
    path.chmod(0o600)


def load_hotwords(path: Path = TERMS_PATH) -> str | None:
    return ", ".join(load_terms(path)) or None
