from __future__ import annotations

import pytest
from pydantic import ValidationError

from graph.state import FileChange
from tools.patch_sanity import sanity_check_file_changes


def test_sanity_empty_changes() -> None:
    assert sanity_check_file_changes([]) == ["file_changes list is empty"]


def test_sanity_rejects_tests_path() -> None:
    errs = sanity_check_file_changes(
        [
            {
                "path": "tests/test_foo.py",
                "search": "a",
                "replace": "b",
                "description": "desc",
            }
        ]
    )
    assert any("test files" in e for e in errs)


def test_sanity_rejects_empty_search() -> None:
    errs = sanity_check_file_changes(
        [
            {
                "path": "src/x.py",
                "search": "   ",
                "replace": "b",
                "description": "desc",
            }
        ]
    )
    assert any("search string is empty" in e for e in errs)


def test_sanity_rejects_identical_search_replace() -> None:
    errs = sanity_check_file_changes(
        [
            {
                "path": "src/x.py",
                "search": "a",
                "replace": "a",
                "description": "desc",
            }
        ]
    )
    assert any("identical" in e for e in errs)


def test_sanity_ok_minimal() -> None:
    assert (
        sanity_check_file_changes(
            [
                {
                    "path": "src/x.py",
                    "search": "line1\nline2",
                    "replace": "line1\nline2\nline3",
                    "description": "append line3",
                }
            ]
        )
        == []
    )


def test_sanity_rejects_empty_path() -> None:
    errs = sanity_check_file_changes(
        [{"path": "", "search": "a", "replace": "b", "description": "d"}]
    )
    assert any("path is empty" in e for e in errs)


def test_sanity_rejects_whitespace_path() -> None:
    errs = sanity_check_file_changes(
        [{"path": "   ", "search": "a", "replace": "b", "description": "d"}]
    )
    assert any("path is empty" in e for e in errs)


def test_file_change_validator_rejects_empty_path() -> None:
    with pytest.raises(ValidationError, match="path must not be empty"):
        FileChange(path="", search="x", replace="y", description="d")


def test_file_change_validator_rejects_whitespace_path() -> None:
    with pytest.raises(ValidationError, match="path must not be empty"):
        FileChange(path="   ", search="x", replace="y", description="d")


def test_file_change_validator_accepts_valid_path() -> None:
    fc = FileChange(path="src/click/core.py", search="x", replace="y", description="d")
    assert fc.path == "src/click/core.py"
