from __future__ import annotations

import re


def sanity_check_unified_diff(unified_diff: str) -> list[str]:
    """
    Deterministic checks for common LLM unified-diff failures before git apply.
    Returns a list of problem descriptions (empty if OK).
    """
    errors: list[str] = []
    if not unified_diff or not unified_diff.strip():
        return ["unified_diff is empty"]

    lower = unified_diff.lower()
    if "diff --git a/tests/" in lower or "diff --git b/tests/" in lower:
        errors.append(
            "Patch modifies tests/ via unified_diff. Put all new tests in tests_written only; "
            "do not edit tests/ in unified_diff.",
        )

    for line in unified_diff.splitlines():
        if line.startswith(("+++ ", "--- ")):
            continue
        if not line.startswith("+") or line.startswith("++"):
            continue
        body = line[1:]
        if body.lstrip().startswith("#"):
            continue
        if re.search(r"\bassert\b.*/\*|\*/", body):
            continue
        if re.search(r"\bassert\b.*==\s*$", body):
            errors.append(f"Incomplete assert (ends with ==): {body[:120]}")
        if re.search(r"\(\s*,", body):
            errors.append(f"Empty first argument in call '(,': {body[:120]}")
        if re.search(r"=\s*$", body) and not body.strip().startswith("#"):
            if "==" not in body and "!=" not in body and "<=" not in body and ">=" not in body:
                errors.append(f"Incomplete assignment (ends with =): {body[:120]}")

    return list(dict.fromkeys(errors))
