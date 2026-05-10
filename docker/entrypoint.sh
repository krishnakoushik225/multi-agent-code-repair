#!/bin/bash
set +e

cd /workspace

if [ -f requirements.txt ]; then
    pip install -r requirements.txt -q
elif [ -f pyproject.toml ]; then
    # PEP 517 isolation tries to download build-system deps; use host image + no isolation.
    pip install -e . -q --no-build-isolation
fi

# test_echo_via_pager is deselected: it fails in Docker due to a capfd/subprocess
# file-descriptor conflict that is a known upstream issue in click's test suite
# (unrelated to any generated fix). See: tests/test_utils.py::test_echo_via_pager
pytest tests/ -q \
  --deselect tests/test_utils.py::test_echo_via_pager \
  2>&1
TEST_EXIT=$?

# Format first so LLM-written tests (e.g. long assert strings) satisfy line length.
ruff format . 2>&1

# Respect [tool.ruff] (e.g. src = ["src"]) instead of linting the whole tree.
ruff check 2>&1
LINT_EXIT=$?

# Respect [tool.mypy] files= (e.g. src + tests/typing only); avoid `mypy .` on all tests.
mypy 2>&1
TYPE_EXIT=$?

echo "TEST_EXIT=$TEST_EXIT"
echo "LINT_EXIT=$LINT_EXIT"
echo "TYPE_EXIT=$TYPE_EXIT"

exit 0
