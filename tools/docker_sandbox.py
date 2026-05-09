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


def apply_file_changes(repo_root: Path, file_changes: list[dict]) -> list[str]:
    """Apply search-replace changes to files. Returns list of error strings."""
    errors: list[str] = []
    for change in file_changes:
        path = repo_root / change["path"]
        if not path.exists():
            errors.append(f"File not found: {change['path']}")
            continue
        content = path.read_text(encoding="utf-8")
        search = change["search"]
        replace = change["replace"]
        if search not in content:
            # Try normalizing line endings
            search_normalized = search.replace("\r\n", "\n")
            content_normalized = content.replace("\r\n", "\n")
            if search_normalized not in content_normalized:
                errors.append(
                    f"Search string not found in {change['path']}. "
                    f"First 120 chars of search: {search[:120]!r}"
                )
                continue
            content = content_normalized.replace(search_normalized, replace, 1)
        else:
            content = content.replace(search, replace, 1)
        path.write_text(content, encoding="utf-8")
    return errors


def apply_patch_and_run_tests(
    repo_owner: str,
    repo_name: str,
    default_branch: str,
    base_commit_sha: str,
    file_changes: list[dict],
    tests_written: str | None,
) -> dict:
    """
    Clone repo, apply file changes, optionally write tests, run pytest/ruff/mypy in Docker.
    """
    if not file_changes:
        return {
            "test_exit_code": 1,
            "lint_exit_code": 1,
            "type_check_exit_code": 1,
            "stdout": "",
            "stderr": "file_changes list is empty",
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

        apply_errors = apply_file_changes(root, file_changes)
        if apply_errors:
            return {
                "test_exit_code": 1,
                "lint_exit_code": 1,
                "type_check_exit_code": 1,
                "stdout": "",
                "stderr": "\n".join(apply_errors),
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
