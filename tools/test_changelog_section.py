"""The release's changelog section, run as `make release-*` runs it, on a scratch repo whose master
has a release, a direct commit, merges with and without a prose body, and a commit outside mx/."""

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "changelog_section.py"


def test_merges_bring_their_first_paragraph_and_everything_else_its_subject(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q", "-b", "master")
    since = commit(tmp_path, "mx/a", "mx v1.0.0")
    commit(tmp_path, "mx/b", "fix(b): a direct commit", "Its body is the why, and stays out.")
    merge(tmp_path, "described", "mx/c", "feat(c): a branch with a paragraph",
          "What the branch changed,\nwrapped over two lines.\n\nRulings (max): none.\n\nWorkflow-stage: implement")
    merge(tmp_path, "bare", "mx/d", "feat(d): a branch with trailers alone", "Workflow-stage: implement\nCo-Authored-By: someone")
    commit(tmp_path, "docs/e", "docs(e): nothing under mx/")
    commit(tmp_path, "mx/f", "mx v1.0.1")

    out = subprocess.run([str(SCRIPT), since, "1.0.2"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout

    assert out == (
        "## 1.0.2\n\n"
        "- feat(d): a branch with trailers alone\n"
        "- feat(c): a branch with a paragraph\n"
        "  What the branch changed, wrapped over two lines.\n"
        "- fix(b): a direct commit\n\n"
    )


def git(repo: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=True).stdout.strip()


def commit(repo: Path, path: str, subject: str, body: str = "") -> str:
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(subject)
    git(repo, "add", path)
    git(repo, "commit", "-q", "-m", subject, *(["-m", body] if body else []))
    return git(repo, "rev-parse", "HEAD")


def merge(repo: Path, branch: str, path: str, subject: str, body: str) -> None:
    git(repo, "checkout", "-q", "-b", branch)
    commit(repo, path, f"wip on {branch}")
    git(repo, "checkout", "-q", "master")
    git(repo, "merge", "-q", "--no-ff", branch, "-m", subject, "-m", body)
