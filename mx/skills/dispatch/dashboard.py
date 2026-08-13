#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.11"
# dependencies = ["tyro", "pyyaml"]
# ///
"""Render the dispatch status dashboard for a feature's ticket DAG.

Reads ticket files (NN-<slug>.md with status/blocked-by frontmatter) from a
feature's tasks directory and writes a self-contained HTML page: the dependency
DAG as a mermaid diagram (ticket number + title, colored by status), a ticket
table, the needs-human queue, and recent commits of the repo's checked-out branch.
The page auto-refreshes every 30s, so one open tab stays current across renders.

Examples:

    uv run dashboard.py agent/tasks/my-feature
    uv run dashboard.py agent/tasks/my-feature --needs-human "ticket 03: design call on retry semantics"
    uv run dashboard.py agent/tasks/my-feature --out /tmp/dash.html --open never
"""

import datetime
import html
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal

import tyro
import yaml

STATUS_SYMBOL = {"done": "✓", "claimed": "⟳", "open": "○", "blocked": "⊘"}


@dataclass
class Args:
    tasks_dir: Annotated[Path, tyro.conf.Positional]
    """Feature tasks directory, e.g. agent/tasks/<feature>."""
    out: Path | None = None
    """Output HTML path. Default: ~/Downloads/dispatch-<feature>.html."""
    repo: Path | None = None
    """Repo for the commit log. Default: three levels above tasks_dir."""
    needs_human: Annotated[list[str], tyro.conf.UseAppendAction] = field(default_factory=list)
    """Needs-human queue entry; repeat the flag for multiple entries."""
    open: Literal["auto", "always", "never"] = "auto"
    """xdg-open the result: auto = only when the output file is new."""


def main(args: Args) -> None:
    feature = args.tasks_dir.name
    out = args.out or Path.home() / "Downloads" / f"dispatch-{feature}.html"
    repo = args.repo or args.tasks_dir.parent.parent.parent
    tickets = load_tickets(args.tasks_dir)
    assert tickets, f"no NN-<slug>.md tickets in {args.tasks_dir}"
    page = render_page(feature, tickets, args.needs_human, git_log(repo))
    existed = out.exists()
    out.write_text(page)
    print(out)
    if args.open == "always" or (args.open == "auto" and not existed):
        subprocess.Popen(["xdg-open", str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@dataclass
class Ticket:
    num: str
    title: str
    status: str  # open | claimed | done, plus derived: blocked
    blocked_by: list[str]


def load_tickets(tasks_dir: Path) -> list[Ticket]:
    tickets = []
    for path in sorted(tasks_dir.glob("[0-9][0-9]-*.md")):
        meta, body = split_frontmatter(path.read_text())
        heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        tickets.append(
            Ticket(
                num=path.name[:2],
                title=heading.group(1).strip() if heading else path.stem[3:].replace("-", " "),
                status=str(meta.get("status", "open")),
                blocked_by=[normalize_num(n) for n in meta.get("blocked-by") or []],
            )
        )
    done = {t.num for t in tickets if t.status == "done"}
    for t in tickets:
        if t.status == "open" and any(b not in done for b in t.blocked_by):
            t.status = "blocked"
    return tickets


def split_frontmatter(text: str) -> tuple[dict, str]:
    match = re.match(r"\A---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not match:
        return {}, text
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


def normalize_num(n: object) -> str:
    # YAML reads `01` as int 1; ticket ids are two-digit strings.
    return f"{int(n):02d}" if isinstance(n, int) else str(n).zfill(2)


def git_log(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "--oneline", "-n", "15"], capture_output=True, text=True
    )
    assert result.returncode == 0, f"git log failed in {repo}: {result.stderr.strip()}"
    return result.stdout


def render_page(feature: str, tickets: list[Ticket], needs_human: list[str], log: str) -> str:
    n_done = sum(t.status == "done" for t in tickets)
    needs_human_section = (
        "<h2>Needs human</h2><ul class='needs-human'>"
        + "".join(f"<li>{html.escape(item)}</li>" for item in needs_human)
        + "</ul>"
        if needs_human
        else ""
    )
    rows = "".join(
        f"<tr><td>{t.num}</td><td>{html.escape(t.title)}</td>"
        f"<td><span class='badge {t.status}'>{STATUS_SYMBOL[t.status]} {t.status}</span></td>"
        f"<td>{', '.join(t.blocked_by) or '—'}</td></tr>"
        for t in tickets
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="30">
<title>dispatch — {html.escape(feature)}</title>
<style>
  body {{ font: 15px/1.5 system-ui, sans-serif; color: #1f2937; max-width: 60rem; margin: 2rem auto; padding: 0 1rem; }}
  h1 {{ font-size: 1.3rem; }} h2 {{ font-size: 1.05rem; margin-top: 2rem; }}
  .meta {{ color: #6b7280; font-size: 0.85rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: 0.35rem 0.75rem 0.35rem 0; border-bottom: 1px solid #e5e7eb; }}
  th {{ color: #6b7280; font-weight: 600; font-size: 0.8rem; }}
  .badge {{ padding: 0.1rem 0.5rem; border-radius: 0.6rem; font-size: 0.8rem; white-space: nowrap; }}
  .badge.done {{ background: #dcfce7; color: #166534; }}
  .badge.claimed {{ background: #fef3c7; color: #92400e; }}
  .badge.open {{ background: #e0f2fe; color: #075985; }}
  .badge.blocked {{ background: #f3f4f6; color: #6b7280; }}
  .needs-human li {{ background: #fef2f2; border-left: 3px solid #dc2626; padding: 0.3rem 0.6rem; margin: 0.3rem 0; list-style: none; }}
  .needs-human {{ padding: 0; }}
  pre {{ background: #f9fafb; padding: 0.75rem; overflow-x: auto; font-size: 0.85rem; }}
</style>
</head>
<body>
<h1>dispatch — {html.escape(feature)}</h1>
<p class="meta">{n_done}/{len(tickets)} done · rendered {datetime.datetime.now():%Y-%m-%d %H:%M:%S} · auto-refreshes every 30s</p>
<pre class="mermaid">
{mermaid_dag(tickets)}
</pre>
<h2>Tickets</h2>
<table>
<tr><th>#</th><th>Title</th><th>Status</th><th>Blocked by</th></tr>
{rows}
</table>
{needs_human_section}
<h2>Recent commits</h2>
<pre>{html.escape(log)}</pre>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  mermaid.initialize({{ startOnLoad: true, theme: "neutral" }});
</script>
</body>
</html>
"""


def mermaid_dag(tickets: list[Ticket]) -> str:
    lines = ["flowchart LR"]
    for t in tickets:
        label = f"{t.num} {t.title}".replace('"', "#quot;")
        lines.append(f'  T{t.num}["{STATUS_SYMBOL[t.status]} {label}"]:::{t.status}')
    for t in tickets:
        lines.extend(f"  T{b} --> T{t.num}" for b in t.blocked_by)
    lines += [
        "  classDef done fill:#dcfce7,stroke:#16a34a,color:#166534",
        "  classDef claimed fill:#fef3c7,stroke:#d97706,color:#92400e",
        "  classDef open fill:#e0f2fe,stroke:#0284c7,color:#075985",
        "  classDef blocked fill:#f3f4f6,stroke:#9ca3af,color:#6b7280",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main(tyro.cli(Args, description=__doc__))
