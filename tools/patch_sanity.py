from __future__ import annotations


def sanity_check_file_changes(file_changes: list[dict]) -> list[str]:
    errors: list[str] = []
    if not file_changes:
        return ["file_changes list is empty"]
    for i, fc in enumerate(file_changes):
        path = fc.get("path", "")
        if not path.strip():
            errors.append(f"Change {i}: path is empty or whitespace")
        if not fc.get("search", "").strip():
            errors.append(f"Change {i}: search string is empty")
        if fc.get("search") == fc.get("replace"):
            errors.append(f"Change {i}: search and replace are identical — no change would be made")
        if "tests/" in path and path.endswith(".py"):
            errors.append(
                f"Change {i}: do not modify test files in file_changes — use tests_written instead"
            )
    return errors
