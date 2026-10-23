"""The show conventions (`/mx:show`), read from git: `make check` runs it.

Two readings, one `path: message` line per violation, exit 1 when there is any:

- Every directory git tracks under `agent/show/` belongs to live work: a ticket of its name in
  `agent/tickets/`, a local branch `<name>` or `ticket/<name>` in either repo, or a ticket that
  cites it by path (`agent/show/<name>`), the way a ticket cut from an architecture review cites the
  review's page. A retired ticket's show directory leaves with it (`tracker retire`).
- No render is tracked beside its source: no PNG under `agent/show/` or `docs/figures/`. The copy a
  document reads (`mx/assets/`) is tracked; the one beside the source is rendered on demand.

A checkout without its agent repo, or a host without git, skips what it cannot read and says so.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT = ROOT / "agent"


def main() -> int:
    if shutil.which("git") is None:
        print("show conventions: skipped, no git on this host")
        return 0
    findings = [f"{p}: a render tracked beside its source" for p in git(ROOT, "ls-files", "docs/figures/*.png")]
    if (AGENT / ".git").exists():
        findings += [f"agent/{p}: a render tracked beside its source" for p in git(AGENT, "ls-files", "show/**/*.png")]
        findings += [f"agent/show/{name}/: no ticket or branch of its name, and no ticket cites it"
                     for name in orphans()]
    else:
        print("show conventions: skipped the readings of agent/show/, no agent repo at agent/")
    for finding in findings:
        print(finding)
    return 1 if findings else 0


def orphans() -> list[str]:
    shows = sorted({p.split("/")[1] for p in git(AGENT, "ls-files", "show/") if p.count("/") >= 2})
    tickets = {p.stem: p.read_text() for p in (AGENT / "tickets").glob("*.md")}
    branches = {branch for repo in (ROOT, AGENT)
                for branch in git(repo, "for-each-ref", "--format=%(refname:lstrip=2)", "refs/heads")}
    return [name for name in shows
            if name not in tickets
            and not {name, f"ticket/{name}"} & branches
            and not any(re.search(rf"show/{re.escape(name)}(?![\w-])", text) for text in tickets.values())]


def git(repo: Path, *args: str) -> list[str]:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
    return done.stdout.splitlines()


if __name__ == "__main__":
    sys.exit(main())
