#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Two layouts, the same two tickets, one merge each.

Layout HUB:  app.py holds a hand-written list of panels. Adding a panel means
             editing app.py — so two tickets edit the same lines.
Layout SEAM: app.py scans the panels package. Adding a panel means adding a
             file — so two tickets edit nothing in common.

Both layouts get the same treatment: branch ticket-a, branch ticket-b, each adds
its panel, then merge both into main. The merge result is the whole point.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

HUB_APP = '''\
from panels.chat import chat
from panels.graph import graph

PANELS = [chat, graph]


def render():
    for panel in PANELS:
        print(panel())
'''

SEAM_APP = '''\
import importlib
import pkgutil

import panels


def render():
    for module in discover():
        print(module.panel())


def discover():
    """The list app.py used to hold by hand, read off the directory instead."""
    found = [importlib.import_module(f"panels.{m.name}") for m in pkgutil.iter_modules(panels.__path__)]
    return sorted(found, key=lambda m: m.ORDER)
'''


def main() -> None:
    for layout in ("hub", "seam"):
        repo = Path(tempfile.mkdtemp(prefix=f"seam-demo-{layout}-"))
        build_base(repo, layout)
        for ticket, panel in (("ticket-a", "quiz"), ("ticket-b", "review")):
            add_panel_on_branch(repo, layout, ticket, panel)

        print(f"\n{'=' * 64}\nLAYOUT: {layout}\n{'=' * 64}")
        print(show_ticket_diff(repo, "ticket-a"))
        for ticket in ("ticket-a", "ticket-b"):
            print(f"  merge {ticket:9} -> {merge(repo, ticket)}")
        print(f"\n  app.py after both merges says:\n{run_app(repo)}")
        shutil.rmtree(repo)


def build_base(repo: Path, layout: str) -> None:
    """A repo whose app already renders two panels, laid out one way or the other."""
    (repo / "panels").mkdir(parents=True)
    (repo / "panels" / "__init__.py").touch()
    for name, order in (("chat", 10), ("graph", 20)):
        write_panel(repo, layout, name, order)
    (repo / "app.py").write_text(HUB_APP if layout == "hub" else SEAM_APP)

    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base app with two panels")


def add_panel_on_branch(repo: Path, layout: str, ticket: str, panel: str) -> None:
    """What one ticket has to touch to get its panel on screen."""
    git(repo, "checkout", "-q", "-b", ticket, "main")
    write_panel(repo, layout, panel, order=30)
    if layout == "hub":
        app = (repo / "app.py").read_text()
        app = app.replace("PANELS = [", f"PANELS = [{panel}, ")
        app = f"from panels.{panel} import {panel}\n" + app
        (repo / "app.py").write_text(app)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", f"{ticket}: add the {panel} panel")
    git(repo, "checkout", "-q", "main")


def write_panel(repo: Path, layout: str, name: str, order: int) -> None:
    body = f'def {name}():\n    return "  [{name} panel]"\n'
    if layout == "seam":
        # The panel declares itself, so nothing central has to declare it.
        body = f'ORDER = {order}\n\n\n' + body.replace(f"def {name}()", "def panel()")
    (repo / "panels" / f"{name}.py").write_text(body)


def merge(repo: Path, ticket: str) -> str:
    done = git(repo, "merge", "--no-edit", ticket, check=False)
    if done.returncode == 0:
        return "clean"
    conflicted = git(repo, "diff", "--name-only", "--diff-filter=U").stdout.split()
    git(repo, "merge", "--abort", check=False)
    return f"CONFLICT in {', '.join(conflicted)}"


def show_ticket_diff(repo: Path, ticket: str) -> str:
    stat = git(repo, "diff", "--stat", f"main...{ticket}").stdout.rstrip()
    return f"  what one ticket touches:\n{stat}\n"


def run_app(repo: Path) -> str:
    script = "import app; app.render()"
    return subprocess.run(["python3", "-c", script], cwd=repo, capture_output=True, text=True).stdout.rstrip()


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["git", "-c", "user.email=demo@example.com", "-c", "user.name=demo", "-C", str(repo), *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


if __name__ == "__main__":
    main()
