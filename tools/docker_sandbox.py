from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import docker


def parse_exit_codes(stdout: str) -> dict[str, int]:
    codes: dict[str, int] = {}
    for line in stdout.splitlines():
        if "=" in line:
            key, val = line.strip().split("=", 1)
            if key in ("TEST_EXIT", "LINT_EXIT", "TYPE_EXIT"):
                try:
                    codes[key] = int(val)
                except ValueError:
                    continue
    return codes


def _validate_diff(unified_diff: str) -> str | None:
    """
    Return an error string if the diff is obviously malformed, else None.
    Catches the most common LLM failure modes before wasting a git clone.
    """
    if not unified_diff or not unified_diff.strip():
        return "unified_diff is empty"

    lines = unified_diff.splitlines()
    seen_files: dict[str, int] = {}
    for i, line in enumerate(lines, start=1):
        if line.startswith("diff --git "):
            # Extract the b/ path as the canonical file key
            parts = line.split(" ")
            path = parts[-1] if parts[-1].startswith("b/") else line
            if path in seen_files:
                return (
                    f"Corrupt patch: file '{path}' appears in two separate diff headers "
                    f"(lines {seen_files[path]} and {i}). Combine all hunks for the same "
                    "file under a single header."
                )
            seen_files[path] = i

    if not seen_files:
        return "unified_diff contains no 'diff --git' headers — not a valid unified diff"

    return None


def apply_patch_and_run_tests(
    repo_owner: str,
    repo_name: str,
    default_branch: str,
    unified_diff: str,
    tests_written: str | None,
    *,
    base_commit_sha: str | None = None,
) -> dict:
    """
    Clone repo, apply patch, optionally write tests, run pytest/ruff/mypy in Docker.
    """
    diff_error = _validate_diff(unified_diff)
    if diff_error:
        return {
            "test_exit_code": 1,
            "lint_exit_code": 1,
            "type_check_exit_code": 1,
            "stdout": "",
            "stderr": f"Invalid unified_diff: {diff_error}",
        }

    try:
        client = docker.from_env()
    except docker.errors.DockerException as exc:
        return {
            "test_exit_code": 1,
            "lint_exit_code": 1,
            "type_check_exit_code": 1,
            "stdout": "",
            "stderr": f"Docker daemon not available: {exc}",
        }
    image = os.environ.get("SANDBOX_IMAGE", "multi-agent-sandbox:latest")
    clone_timeout = int(os.environ.get("SANDBOX_CLONE_TIMEOUT", "300"))
    checkout_ref = base_commit_sha or default_branch

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "workspace"
        root.mkdir(parents=True, exist_ok=True)
        repo_url = f"https://github.com/{repo_owner}/{repo_name}.git"
        try:
            clone = subprocess.run(
                ["git", "clone", "--quiet", repo_url, str(root)],
                capture_output=True,
                text=True,
                check=False,
                timeout=clone_timeout,
            )
        except subprocess.TimeoutExpired:
            return {
                "test_exit_code": 1,
                "lint_exit_code": 1,
                "type_check_exit_code": 1,
                "stdout": "",
                "stderr": f"git clone timed out after {clone_timeout}s",
            }
        if clone.returncode != 0:
            return {
                "test_exit_code": 1,
                "lint_exit_code": 1,
                "type_check_exit_code": 1,
                "stdout": clone.stdout or "",
                "stderr": clone.stderr or "git clone failed",
            }

        checkout = subprocess.run(
            ["git", "-C", str(root), "checkout", "--quiet", checkout_ref],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if checkout.returncode != 0:
            return {
                "test_exit_code": 1,
                "lint_exit_code": 1,
                "type_check_exit_code": 1,
                "stdout": checkout.stdout or "",
                "stderr": checkout.stderr or f"git checkout {checkout_ref} failed",
            }

        diff_path = root / "fix.patch"
        diff_path.write_text(unified_diff, encoding="utf-8")
        try:
            apply = subprocess.run(
                ["git", "-C", str(root), "apply", "--whitespace=nowarn", "--recount", str(diff_path)],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return {
                "test_exit_code": 1,
                "lint_exit_code": 1,
                "type_check_exit_code": 1,
                "stdout": "",
                "stderr": "git apply timed out after 30s",
            }
        if apply.returncode != 0:
            return {
                "test_exit_code": 1,
                "lint_exit_code": 1,
                "type_check_exit_code": 1,
                "stdout": apply.stdout or "",
                "stderr": apply.stderr or "git apply failed",
            }

        if tests_written:
            test_path = root / "tests" / "test_auto_generated.py"
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.write_text(tests_written, encoding="utf-8")

        network_mode = os.environ.get("SANDBOX_DOCKER_NETWORK", "none")
        try:
            container = client.containers.run(
                image=image,
                command="/bin/bash /entrypoint.sh",
                volumes={str(root): {"bind": "/workspace", "mode": "rw"}},
                working_dir="/workspace",
                detach=True,
                mem_limit="512m",
                cpu_period=100000,
                cpu_quota=50000,
                network_mode=network_mode,
            )
        except docker.errors.ImageNotFound:
            return {
                "test_exit_code": 1,
                "lint_exit_code": 1,
                "type_check_exit_code": 1,
                "stdout": "",
                "stderr": f"Docker image not found: {image}. Build with docker build -t {image} -f docker/Dockerfile.sandbox .",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "test_exit_code": 1,
                "lint_exit_code": 1,
                "type_check_exit_code": 1,
                "stdout": "",
                "stderr": f"docker run failed: {exc}",
            }

        try:
            result = container.wait(timeout=120)
            exit_code = int(result.get("StatusCode", 1))
        except Exception as exc:  # noqa: BLE001
            try:
                container.remove(force=True)
            except Exception:
                pass
            return {
                "test_exit_code": 1,
                "lint_exit_code": 1,
                "type_check_exit_code": 1,
                "stdout": "",
                "stderr": f"container wait failed: {exc}",
            }

        stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
        try:
            container.remove(force=True)
        except Exception:
            pass

        codes = parse_exit_codes(stdout)
        if not codes:
            return {
                "test_exit_code": exit_code,
                "lint_exit_code": exit_code,
                "type_check_exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr or "missing TEST_EXIT/LINT_EXIT/TYPE_EXIT markers in stdout",
            }

        return {
            "test_exit_code": codes.get("TEST_EXIT", 1),
            "lint_exit_code": codes.get("LINT_EXIT", 1),
            "type_check_exit_code": codes.get("TYPE_EXIT", 1),
            "stdout": stdout,
            "stderr": stderr,
        }
