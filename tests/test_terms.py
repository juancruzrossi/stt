from pathlib import Path

from stt.terms import load_hotwords


def test_load_hotwords_ignores_blank_lines_and_comments(tmp_path: Path) -> None:
    terms_path = tmp_path / "terms.txt"
    terms_path.write_text(
        "# Custom terms\n\nProductName\nProject Atlas\n",
        encoding="utf-8",
    )

    assert load_hotwords(terms_path) == "ProductName, Project Atlas"
    assert load_hotwords(tmp_path / "missing.txt") is None
