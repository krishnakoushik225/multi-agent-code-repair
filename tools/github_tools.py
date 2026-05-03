from __future__ import annotations

import base64
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

from github import Github
from github.GithubException import GithubException
from github.Repository import Repository


def _client() -> Github:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set")
    return Github(token)


def _commit_for_ref(repo: Repository, git_ref: str | None) -> str:
    """Resolve a commit SHA for API calls (branch tip or explicit SHA)."""
    if git_ref:
        return repo.get_commit(git_ref).sha
    return repo.get_commit(repo.get_branch(repo.default_branch).commit.sha).sha


def get_repo_tree(
    repo_owner: str,
    repo_name: str,
    max_paths: int = 800,
    *,
    git_ref: str | None = None,
) -> list[str]:
    """Return a bounded list of repository file paths at the given commit (or default branch tip)."""
    g = _client()
    repo = g.get_repo(f"{repo_owner}/{repo_name}")
    commit_sha = _commit_for_ref(repo, git_ref)
    commit = repo.get_commit(commit_sha)
    tree = repo.get_git_tree(commit.commit.tree.sha, recursive=True).tree

    paths: list[str] = []
    for item in tree:
        if item.type != "blob" or not item.path:
            continue
        paths.append(item.path)
        if len(paths) >= max_paths:
            break

    return sorted(paths)


def get_file_content(
    repo_owner: str,
    repo_name: str,
    file_path: str,
    *,
    git_ref: str | None = None,
) -> str | None:
    """Fetch a single file's text at a commit SHA or branch name (default: default branch)."""
    g = _client()
    repo = g.get_repo(f"{repo_owner}/{repo_name}")
    ref = git_ref if git_ref else repo.default_branch

    try:
        content_file = repo.get_contents(file_path, ref=ref)
    except GithubException:
        return None
    except Exception:
        return None

    if isinstance(content_file, list):
        return None
    if content_file.content is None:
        return None

    try:
        return base64.b64decode(content_file.content).decode("utf-8", errors="replace")
    except Exception:
        return None


def _sanitize_code_search_query(query: str, max_len: int = 120) -> str:
    """
    GitHub code search is brittle with raw issue text.
    Keep only lightweight searchable text.
    """
    cleaned = re.sub(r"\s+", " ", query)
    cleaned = re.sub(r"[^A-Za-z0-9_\-./ ]+", " ", cleaned)
    cleaned = " ".join(cleaned.split())
    return cleaned[:max_len].strip()


def search_code_in_repo(repo_owner: str, repo_name: str, query: str, limit: int = 20) -> list[str]:
    """
    GitHub code search scoped to a repository; returns matching file paths.

    Requires a token allowed to use the Code Search API (classic PAT: ``repo`` or
    ``public_repo`` for public repos). Fine-grained tokens may return 404 if search
    is not permitted — research continues without these hits.
    """
    g = _client()

    cleaned = _sanitize_code_search_query(query)
    if not cleaned:
        return []

    q = f"{cleaned} repo:{repo_owner}/{repo_name}"
    paths: list[str] = []

    try:
        results = g.search_code(q)

        # PyGithub search is lazy; errors often occur during iteration, not creation.
        for i, res in enumerate(results):
            if i >= limit:
                break
            path = getattr(res, "path", None)
            if path:
                paths.append(path)

    except GithubException as e:
        print(
            "GitHub code search failed:",
            f"status={getattr(e, 'status', None)}",
            f"data={getattr(e, 'data', None)}",
        )
        return []
    except Exception as e:
        print(f"GitHub code search failed: {e}")
        return []

    return list(dict.fromkeys(paths))


def _authenticated_clone_url(repo_owner: str, repo_name: str, token: str) -> str:
    safe = quote(token, safe="")
    return f"https://x-access-token:{safe}@github.com/{repo_owner}/{repo_name}.git"


def _run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
        env=env,
        timeout=timeout,
    )


def apply_diff_to_branch(
    repo: Repository,
    branch_name: str,
    file_path: str,
    unified_diff: str,
) -> None:
    """
    Compatibility shim: the PR workflow applies the full unified diff once via git.
    Per-file application from the API alone is brittle; prefer `git_push_patch_branch`.
    """
    _ = (repo, branch_name, file_path, unified_diff)


def git_push_patch_branch(
    repo_owner: str,
    repo_name: str,
    default_branch: str,
    branch_name: str,
    unified_diff: str,
    commit_message: str,
    *,
    base_commit_sha: str | None = None,
) -> None:
    """Clone repo, create branch, apply unified diff, commit, and push."""
    token = os.environ["GITHUB_TOKEN"]
    clone_url = _authenticated_clone_url(repo_owner, repo_name, token)
    clone_timeout = int(os.environ.get("SANDBOX_CLONE_TIMEOUT", "300"))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"

        p = _run(
            ["git", "clone", "--quiet", clone_url, str(root)],
            cwd=Path(tmp),
            timeout=clone_timeout,
        )
        if p.returncode != 0:
            raise RuntimeError(f"git clone failed: {p.stderr}")

        checkout_target = base_commit_sha or default_branch
        co = _run(
            ["git", "-C", str(root), "checkout", "--quiet", checkout_target],
            cwd=Path(tmp),
            timeout=60,
        )
        if co.returncode != 0:
            raise RuntimeError(f"git checkout {checkout_target} failed: {co.stderr}")

        b = _run(["git", "-C", str(root), "checkout", "-b", branch_name], cwd=Path(tmp))
        if b.returncode != 0:
            raise RuntimeError(f"git checkout -b failed: {b.stderr}")

        patch_path = root / "fix.patch"
        patch_path.write_text(unified_diff, encoding="utf-8")

        a = _run(
            ["git", "-C", str(root), "apply", "--whitespace=nowarn", "--recount", str(patch_path)],
            cwd=Path(tmp),
        )
        if a.returncode != 0:
            raise RuntimeError(f"git apply failed: {a.stderr}")

        st = _run(["git", "-C", str(root), "status", "--porcelain"], cwd=Path(tmp))
        if not st.stdout.strip():
            raise RuntimeError("git apply produced no changes")

        _run(["git", "-C", str(root), "add", "-A"], cwd=Path(tmp))

        git_env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "multi-agent-code-repair",
            "GIT_AUTHOR_EMAIL": "multi-agent-code-repair@users.noreply.github.com",
            "GIT_COMMITTER_NAME": "multi-agent-code-repair",
            "GIT_COMMITTER_EMAIL": "multi-agent-code-repair@users.noreply.github.com",
        }

        commit = _run(
            ["git", "-C", str(root), "commit", "-m", commit_message],
            cwd=Path(tmp),
            env=git_env,
        )
        if commit.returncode != 0:
            raise RuntimeError(f"git commit failed: {commit.stderr}")

        push = _run(["git", "-C", str(root), "push", "origin", branch_name], cwd=Path(tmp))
        if push.returncode != 0:
            raise RuntimeError(f"git push failed: {push.stderr}")


def delete_git_ref_if_exists(repo: Repository, ref: str) -> None:
    try:
        git_ref = repo.get_git_ref(ref.replace("refs/", ""))
        git_ref.delete()
    except Exception:
        return


def ensure_branch_name(issue_number: int) -> str:
    return f"auto-fix/issue-{issue_number}"


def slugify(s: str, max_len: int = 40) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:max_len] or "fix").rstrip("-")


def iter_diff_paths(unified_diff: str) -> Iterable[str]:
    for line in unified_diff.splitlines():
        if line.startswith("+++ b/"):
            yield line.removeprefix("+++ b/").split("\t", 1)[0].strip()