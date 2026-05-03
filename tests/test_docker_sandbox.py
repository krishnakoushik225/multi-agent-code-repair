from __future__ import annotations

from tools.docker_sandbox import parse_exit_codes


def test_parse_exit_codes() -> None:
    stdout = "line\nTEST_EXIT=0\nLINT_EXIT=1\nTYPE_EXIT=2\n"
    codes = parse_exit_codes(stdout)
    assert codes["TEST_EXIT"] == 0
    assert codes["LINT_EXIT"] == 1
    assert codes["TYPE_EXIT"] == 2
