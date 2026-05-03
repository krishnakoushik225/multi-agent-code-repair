from __future__ import annotations

from tools.patch_sanity import sanity_check_unified_diff


def test_sanity_empty_diff() -> None:
    assert sanity_check_unified_diff("") == ["unified_diff is empty"]


def test_sanity_rejects_tests_path() -> None:
    diff = """diff --git a/tests/test_foo.py b/tests/test_foo.py
--- a/tests/test_foo.py
+++ b/tests/test_foo.py
@@ -1,1 +1,2 @@
 a
+b
"""
    errs = sanity_check_unified_diff(diff)
    assert any("tests/" in e for e in errs)


def test_sanity_rejects_incomplete_assert() -> None:
    diff = """diff --git a/src/x.py b/src/x.py
--- a/src/x.py
+++ b/src/x.py
@@ -1,1 +1,2 @@
 a
+assert x ==
"""
    assert any("Incomplete assert" in e for e in sanity_check_unified_diff(diff))


def test_sanity_rejects_empty_call_arg() -> None:
    diff = """diff --git a/src/x.py b/src/x.py
--- a/src/x.py
+++ b/src/x.py
@@ -1,1 +1,2 @@
 a
+foo(, b)
"""
    assert any("Empty first argument" in e for e in sanity_check_unified_diff(diff))


def test_sanity_ok_minimal() -> None:
    diff = """diff --git a/src/x.py b/src/x.py
--- a/src/x.py
+++ b/src/x.py
@@ -1,2 +1,3 @@
 line1
 line2
+line3
"""
    assert sanity_check_unified_diff(diff) == []
