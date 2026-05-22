from __future__ import annotations

import tempfile
from pathlib import Path

from tools.docker_sandbox import apply_file_changes


def _write(root: Path, rel: str, content: str) -> Path:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def test_apply_happy_path():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, "src/mod.py", "def foo():\n    return 1\n")
        changes = [
            {"path": "src/mod.py", "search": "return 1", "replace": "return 2", "description": ""}
        ]
        errors = apply_file_changes(root, changes)
        assert errors == []
        assert "return 2" in (root / "src/mod.py").read_text()


def test_apply_file_not_found():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        changes = [{"path": "missing.py", "search": "x", "replace": "y", "description": ""}]
        errors = apply_file_changes(root, changes)
        assert len(errors) == 1
        assert "missing.py" in errors[0]


def test_apply_search_not_found():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, "a.py", "hello world\n")
        changes = [{"path": "a.py", "search": "NOPE", "replace": "nope", "description": ""}]
        errors = apply_file_changes(root, changes)
        assert len(errors) == 1
        assert "Search string not found" in errors[0]


def test_apply_crlf_normalization():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write(root, "b.py", "line1\r\nline2\r\n")
        changes = [
            {"path": "b.py", "search": "line1\nline2\n", "replace": "REPLACED\n", "description": ""}
        ]
        errors = apply_file_changes(root, changes)
        assert errors == []
        assert "REPLACED" in (root / "b.py").read_text()


def test_apply_empty_changes_list():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        errors = apply_file_changes(root, [])
        assert errors == []


def test_apply_multiple_changes_collects_all_errors():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        changes = [
            {"path": "x.py", "search": "a", "replace": "b", "description": ""},
            {"path": "y.py", "search": "c", "replace": "d", "description": ""},
        ]
        errors = apply_file_changes(root, changes)
        assert len(errors) == 2
