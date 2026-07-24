from pathlib import Path

TERMS_PATH = Path.home() / ".config" / "stt" / "terms.txt"


def load_hotwords(path: Path = TERMS_PATH) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None

    terms = [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return ", ".join(terms) or None
