from __future__ import annotations

from tools.code_search import find_related_symbols


def test_find_related_symbols_ranks_overlap() -> None:
    files = {
        "pkg/mod.py": "def handle_click():\n    return 1\n\nclass ClickError(Exception):\n    pass\n"
    }
    symbols = find_related_symbols(files, "click handling error")
    assert "handle_click" in symbols or "ClickError" in symbols
