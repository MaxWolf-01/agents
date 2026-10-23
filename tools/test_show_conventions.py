"""The show conventions check, run as `make check` runs it, on scratch checkouts laid out like this one: a
code repo whose `agent/` is the agent repo."""

import shutil
import subprocess
import sys
from pathlib import Path

CHECK = Path(__file__).resolve().parent / "show_conventions.py"


def test_a_show_directory_of_no_live_work_is_named_and_one_of_live_work_is_not(tmp_path: Path) -> None:
    code, agent = checkout(tmp_path, {
        "agent/tickets/board-papercuts.md": "# Board papercuts\n",
        "agent/tickets/next-record.md": "Cut from `agent/show/architecture-review-2026-10-23/a22.html`.\n",
        "agent/tickets/session-recall.md": "Drawn in `agent/sessions/0a1b2c3d/show/work-containers/index.html`.\n",
        "agent/show/board-papercuts/index.html": "",
        "agent/show/in-flight/report.md": "",
        "agent/show/lifelong-hypervisor/index.html": "",
        "agent/show/architecture-review-2026-10-23/a22.html": "",
        "agent/show/architecture-review-2026-10-14/index.html": "",
        "agent/show/work-containers/index.html": "",
    })
    git(agent, "branch", "ticket/in-flight")
    git(code, "branch", "lifelong-hypervisor")

    assert run(code) == (1, [
        "agent/show/architecture-review-2026-10-14/: no ticket or branch of its name, and no ticket cites it",
        "agent/show/work-containers/: no ticket or branch of its name, and no ticket cites it",
    ])


def test_a_render_tracked_beside_its_source_is_named_and_the_copy_a_document_reads_is_not(tmp_path: Path) -> None:
    code, agent = checkout(tmp_path, {
        "agent/tickets/landing.md": "",
        "agent/show/landing/landing.html": "",
        "agent/show/landing/landing.png": "",
        "docs/figures/landing.html": "",
        "docs/figures/landing.png": "",
        "mx/assets/landing.png": "",
    })
    (code / "docs/figures/landing-light.png").write_text("")

    assert run(code) == (1, [
        "docs/figures/landing.png: a render tracked beside its source",
        "agent/show/landing/landing.png: a render tracked beside its source",
    ])


def test_a_checkout_without_its_agent_repo_skips_the_show_directory_and_still_reads_docs_figures(
        tmp_path: Path) -> None:
    code, agent = checkout(tmp_path, {"agent/show/work-containers/index.html": "", "docs/figures/landing.png": ""})
    shutil.rmtree(agent)

    assert run(code) == (1, [
        "show conventions: skipped the readings of agent/show/, no agent repo at agent/",
        "docs/figures/landing.png: a render tracked beside its source",
    ])


def checkout(root: Path, files: dict[str, str]) -> tuple[Path, Path]:
    code, agent = root / "code", root / "code/agent"
    for path, text in {**files, ".gitignore": "agent/\n", "tools/show_conventions.py": CHECK.read_text()}.items():
        (code / path).parent.mkdir(parents=True, exist_ok=True)
        (code / path).write_text(text)
    agent.mkdir(exist_ok=True)
    for repo in (code, agent):
        git(repo, "init", "-q", "-b", "master")
        git(repo, "add", ".")
        git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "tree")
    return code, agent


def run(code: Path) -> tuple[int, list[str]]:
    done = subprocess.run([sys.executable, code / "tools/show_conventions.py"], capture_output=True, text=True)
    return done.returncode, done.stdout.splitlines()


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
