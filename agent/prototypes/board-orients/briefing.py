#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.14"
# dependencies = ["tyro", "pyyaml", "markdown"]
# ///
"""PROTOTYPE, throwaway (board-orients): the board as a briefing a returning user reads top down.

Answers, in order: where things stand, what is my turn, what agents can do without me, what is
parked, what landed this week. House style. Reads the live tracker through board.py's loaders,
names/briefs/priority/size/theme from fixture.yaml, sessions from the scratch scan. Writes
/var/tmp/board-orients-proto/briefing.html.

    uv run agent/prototypes/board-orients/briefing.py
"""

import datetime
import html
import importlib.util
import json
import re
import subprocess
from pathlib import Path

import markdown
import yaml

PROTO = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("board", PROTO / "board.py")
board = importlib.util.module_from_spec(spec)
spec.loader.exec_module(board)

REPO = Path.home() / "repos/github/MaxWolf-01/agents"
OUT = Path("/var/tmp/board-orients-proto/briefing.html")
FIXTURE = yaml.safe_load((PROTO / "fixture.yaml").read_text())
THEMES, FIX = FIXTURE["themes"], FIXTURE["tickets"]
MINUTES = {"XS": 10, "S": 20, "M": 60, "L": 240, "XL": 480}
SIZE = {"XS": "10 min", "S": "20 min", "M": "1 h", "L": "half a day", "XL": "several sessions"}
HITL = {"grilling", "prototype"}
REVIEW_BRANCH = "ticket/figures-and-demos/06-whole-feature-review"
WORDS = "no one two three four five six seven eight nine ten eleven twelve".split()


def words(n: int) -> str:
    return WORDS[n] if n < len(WORDS) else str(n)


def span(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    h, m = divmod(minutes, 60)
    return f"{h} h" + (f" {m} min" if m else "")


def inline(md: str) -> str:
    return re.sub(r"^<p>|</p>$", "", markdown.markdown(md).strip())


def plain(md: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inline(md))).strip()


# ---- the tracker, as items ------------------------------------------------


def item(tid, t=None, *, title="", status="open", kind=None, feature=None, path=None, source=None):
    fx = FIX.get(tid, {})
    return {
        "tid": tid,
        "name": fx.get("name") or (t.title if t else title),
        "brief": fx.get("brief", ""),
        "theme": fx.get("theme", "later"),
        "priority": fx.get("priority", 9),
        "size": fx.get("size"),
        "status": t.status if t else status,
        "kind": t.kind if t else kind,
        "feature": feature,
        "path": str(t.path if t else path),
        "calls": (t.calls if t else []) or [],
        "sessions": (t.sessions if t else []) or [],
        "demo": str(t.demo) if t and t.demo else None,
        "show": [str(p) for p in (t.show if t else []) or []],
        "review": t.diffview if t else None,
        "source": source,
    }


def load_items() -> tuple[list[dict], list[dict], list[dict]]:
    tickets_root = REPO / "agent/tickets"
    roots = board.tracker_roots(tickets_root)
    root = roots.main
    dv = board.serve_diffviews(root.parent / "diffviews")
    features = board.load_features(root, roots.overrides, dv)
    standalone = [k for k in board.load_standalone(roots, dv) if k.slug not in roots.overrides]
    items = []
    for f in features:
        for t in f.tickets:
            board.enrich(t, f"{f.name}/{t.num}", t.path.parent.parent.parent / "show" / f.name / t.path.stem)
            items.append(item(f"{f.name}/{t.num}", t, feature=f.name))
    for k in standalone:
        board.enrich(k, k.slug, root.parent / "show" / k.slug)
        items.append(item(k.slug, k))
    # tickets the whole-feature review filed on its own branch, not on master until it merges
    listed = subprocess.run(["git", "-C", str(REPO), "ls-tree", "--name-only", REVIEW_BRANCH, "agent/tickets/"], capture_output=True, text=True).stdout.split()
    have = {i["tid"] for i in items}
    for p in listed:
        slug = Path(p).stem
        if not p.endswith(".md") or slug in have or slug == "needs-human":
            continue
        text = subprocess.run(["git", "-C", str(REPO), "show", f"{REVIEW_BRANCH}:{p}"], capture_output=True, text=True).stdout
        meta, body = board.split_frontmatter(text)
        head = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        items.append(item(slug, title=head.group(1) if head else slug, status=str(meta.get("status", "open")), kind=meta.get("type"),
                          path=REPO / p, source="filed by the final review of figures-and-demos"))
    queue = board.load_needs_human(root / "needs-human.md")
    answers = []
    for entry in queue.entries:
        summary, _, detail = entry.partition(" :: ")
        tag, _, question = summary.partition(": ")
        answers.append({"tag": tag, "question": question or summary, "detail": detail, "path": str(queue.path)})
    features_state = [{"name": f.name, "spec": f.spec_status, "done": sum(t.status == "done" for t in f.tickets), "total": len(f.tickets)} for f in features]
    return items, answers, features_state


def landed(days: int = 8) -> list[tuple[str, str]]:
    out = subprocess.run(
        ["git", "-C", str(REPO), "log", "--first-parent", "--merges", f"--since={days}.days", "--format=%ad\t%s", "--date=format:%a %d %b", "master"],
        capture_output=True, text=True,
    ).stdout
    return [tuple(line.split("\t", 1)) for line in out.splitlines() if "\t" in line]


# ---- the page -------------------------------------------------------------


def split_call(md: str) -> tuple[str, str]:
    """A call's headline and the rest: its bold lead-in where it has one, else its first sentence."""
    m = re.match(r"\*\*(.+?)\*\*[\s.,:;]*(.*)", md, re.S)
    if m:
        return m.group(1).rstrip(".:"), m.group(2)
    m = re.match(r"(.+?[.?])\s+(.*)", md, re.S)
    return (m.group(1), m.group(2)) if m else (md, "")


def copy(label: str, payload: str) -> str:
    return f'<button class="copy" data-copy="{html.escape(payload, quote=True)}">{label}</button>'


def calls_html(i: dict) -> str:
    rows = []
    for tag, text in i["calls"]:
        head, rest = split_call(text)
        payload = f"{i['tid']} {tag}, in {i['path']}: {plain(head)}\nMy answer: "
        rows.append(
            f'<li><div class="call-head"><span>{inline(head)}</span>{copy("copy", payload)}</div>'
            + (f'<div class="call-rest v-small">{inline(rest)}</div>' if rest.strip() else "") + "</li>"
        )
    return f'<ol class="calls">{"".join(rows)}</ol>' if rows else ""


def more_html(i: dict) -> str:
    parts = [calls_html(i)]
    if i["sessions"]:
        lis = "".join(
            f'<li><span>{html.escape(s["title"])}</span><span class="v-meta">{s["first"][5:10].replace("-", "/")} to {s["last"][5:10].replace("-", "/")}</span>'
            f'{copy("copy resume", f"cd {s["cwd"]} && claude --resume {s["id"]}")}</li>'
            for s in reversed(i["sessions"])
        )
        parts.append(f'<p class="v-meta label">sessions</p><ul class="sessions">{lis}</ul>')
    if i["demo"]:
        parts.append(f'<p class="v-meta label">demo</p><p class="demo"><code>{html.escape(i["demo"])}</code>{copy("copy path", i["demo"])}</p>')
    return "".join(parts)


def turn_item(n: int, i: dict) -> str:
    verb = {"review": "rule on the build"}.get(i["status"]) or ("judge a prototype" if i["kind"] == "prototype" else "design session")
    meta = [verb]
    if i["review"]:
        meta.append(f'<a class="act" href="{html.escape(i["review"])}" target="_blank">review page</a>')
    if i["calls"]:
        meta.append(f'{words(len(i["calls"]))} call{"s" if len(i["calls"]) != 1 else ""}')
    extra = more_html(i)
    body = (
        f'<div class="line"><span class="name">{html.escape(i["name"])}</span><span class="v-meta">{span(MINUTES.get(i["size"], 20))}</span></div>'
        f'<p class="brief">{inline(i["brief"])}</p><p class="v-meta how">{" · ".join(meta)}</p>'
    )
    inner = f"<details><summary>{body}</summary><div class=\"more\">{extra}</div></details>" if extra else body
    return f'<li><span class="n v-num">{n}</span><div>{inner}</div></li>'


def answers_item(n: int, answers: list[dict]) -> str:
    lis = "".join(
        f'<li><div class="call-head"><span>{inline(a["question"])}</span>{copy("copy", f"{a["tag"]}, in {a["path"]}: {plain(a["question"])}\nMy answer: ")}</div>'
        f'<div class="call-rest v-small">{inline(a["detail"])}</div></li>'
        for a in answers
    )
    body = (
        f'<div class="line"><span class="name">{words(len(answers)).capitalize()} questions for a word</span><span class="v-meta">5 min</span></div>'
        f'<p class="brief">Yes-or-no calls agents raised along the way. Each answer unblocks a ticket or a fix.</p>'
        f'<p class="v-meta how">answer</p>'
    )
    return f'<li><span class="n v-num">{n}</span><div><details><summary>{body}</summary><div class="more"><ol class="calls">{lis}</ol></div></details></div></li>'


def board_session_item(n: int, group: list[dict]) -> str:
    lis = "".join(f'<li><span>{html.escape(i["name"])}</span><span class="v-meta">{span(MINUTES.get(i["size"], 20))}</span></li>' for i in group)
    total = sum(MINUTES.get(i["size"], 20) for i in group)
    body = (
        f'<div class="line"><span class="name">{html.escape(THEMES[group[0]["theme"]])}: this page</span><span class="v-meta">{span(total)}</span></div>'
        f'<p class="brief">The board a returning user reads. {words(len(group)).capitalize()} tickets, designed together in one session, the one you are in.</p>'
        f'<p class="v-meta how">design session · open now</p>'
    )
    return f'<li><span class="n v-num">{n}</span><div><details><summary>{body}</summary><div class="more"><ul class="plain">{lis}</ul></div></details></div></li>'


def render() -> str:
    items, answers, features = load_items()
    live = [i for i in items if i["status"] != "done"]
    reviews = [i for i in live if i["status"] == "review"]
    now_design = [i for i in live if i["kind"] in HITL and i["priority"] <= 1]
    later_design = [i for i in live if i["kind"] in HITL and i["priority"] > 1] + [i for i in live if i["kind"] == "legwork"]
    builds = [i for i in live if not i["kind"] and i["status"] in ("open", "proposed", "blocked") and i["theme"] != "later"]
    later_design += [i for i in live if not i["kind"] and i["status"] in ("open", "proposed", "blocked") and i["theme"] == "later"]
    running = [i for i in live if i["status"] == "claimed" and not i["kind"]]

    key = lambda i: (i["priority"], MINUTES.get(i["size"], 20), i["name"])
    turn = [("answers", None, 0, 1)] if answers else []
    turn += [("review", i, i["priority"], MINUTES.get(i["size"], 20)) for i in reviews]
    if now_design:
        turn.append(("board", None, 1, sum(MINUTES.get(i["size"], 20) for i in now_design)))
    turn.sort(key=lambda x: (x[2], x[3]))
    rows, total = [], 0
    for n, (what, i, _, minutes) in enumerate(turn, 1):
        if what == "answers":
            rows.append(answers_item(n, answers)); total += 5
        elif what == "board":
            rows.append(board_session_item(n, sorted(now_design, key=key))); total += minutes
        else:
            rows.append(turn_item(n, i)); total += minutes

    # without you: builds agents can start, by theme
    by_theme: dict[str, list[dict]] = {}
    for i in sorted(builds, key=key):
        by_theme.setdefault(i["theme"], []).append(i)
    themes_html = ""
    for theme in [t for t in THEMES if t in by_theme]:
        lis = ""
        for i in by_theme[theme]:
            note = "new" if i["source"] else ("waits on a blocker" if i["status"] == "blocked" else "")
            lis += (f'<li><span class="name-s">{html.escape(i["name"])}</span>'
                    f'<span class="v-meta">{note + " · " if note else ""}{SIZE.get(i["size"], "")}</span>'
                    f'<p class="brief-s v-small">{inline(i["brief"])}</p></li>')
        themes_html += f'<section class="theme"><h3 class="v-h3">{html.escape(THEMES[theme])}</h3><ul class="quiet">{lis}</ul></section>'
    running_line = (f'{words(len(running)).capitalize()} build{"s" if len(running) != 1 else ""} running: '
                    + ", ".join(html.escape(i["name"]) for i in running) + ".") if running else "No agent is working right now."

    later_lis = "".join(
        f'<li><span class="name-s">{html.escape(i["name"])}</span><span class="v-meta">{SIZE.get(i["size"], "")}</span>'
        f'<p class="brief-s v-small">{inline(i["brief"])}</p></li>'
        for i in sorted(later_design, key=key)
    )
    other_features = [f for f in features if f["name"] not in ("figures-and-demos",)]
    later_lis += "".join(
        f'<li><span class="name-s">{html.escape(f["name"])}</span><span class="v-meta">spec {f["spec"]}</span>'
        f'<p class="brief-s v-small">A feature being designed in another session.</p></li>'
        for f in other_features if f["total"] == 0
    )

    landed_lis = "".join(f'<li><span class="v-meta when">{html.escape(d.lower())}</span><span>{html.escape(s)}</span></li>' for d, s in landed()[:8])

    fd = next((f for f in features if f["name"] == "figures-and-demos"), None)
    lead = (f"{words(len(reviews)).capitalize()} builds wait for your ruling, and {words(len(answers))} questions for a word. "
            + ("No agent is working. " if not running else "")
            + (f"figures-and-demos merges once you accept its final review." if fd and any(i["tid"] == "figures-and-demos/06" and i["status"] == "review" for i in items) else ""))
    today = datetime.date.today()
    meta = f"{today:%A %d %B}".lower() + f" · {len(live)} open tickets · {len([f for f in features if f['total'] or f['spec']])} features in flight"

    return PAGE.replace("{{LEAD}}", html.escape(lead)).replace("{{META}}", html.escape(meta)).replace("{{TOTAL}}", "about " + span(total)) \
        .replace("{{TURN}}", "".join(rows)).replace("{{RUNNING}}", running_line).replace("{{THEMES}}", themes_html) \
        .replace("{{LATER}}", later_lis).replace("{{LANDED}}", landed_lis).replace("{{TOKENS}}", TOKENS)


TOKENS = (Path.home() / ".claude/plugins/cache/MaxWolf-01/mx/0.1.69/skills/house-style/tokens.css").read_text()

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agents</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400;1,6..72,600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
{{TOKENS}}
.page { max-width: 46rem; margin: 0 auto; padding: 0 2rem; }
header.row { display: flex; align-items: center; gap: 1.5rem; padding: 1rem 0; border-bottom: 1px solid var(--edge); }
header .v-h3 { margin: 0; }
header nav { color: var(--muted); font-size: .92em; }
.scheme { margin-left: auto; display: inline-flex; padding: .25rem; border: 0; background: none; color: var(--muted); cursor: pointer; transition: color 150ms; }
.scheme:hover { color: var(--accent); }
[data-theme="night"] .sun, [data-theme="day"] .moon { display: none; }
p { margin: 0; }
.hero { padding: 3.5rem 0 1rem; }
.hero .v-title { margin: 0; }
.hero .v-meta { margin-top: .75rem; }
.hero .v-lead { margin-top: 1.75rem; color: var(--muted); max-width: var(--measure); }
main > section { margin-top: 3.5rem; }
.divider { display: flex; align-items: baseline; gap: .75rem; margin-bottom: 1.75rem; }
.divider .rule { flex: 1; height: 1px; background: var(--edge); align-self: center; }
.intro { color: var(--muted); max-width: var(--measure); margin: -.75rem 0 2rem; }

/* your turn: numbered steps, the number in a margin column */
ol.turn { list-style: none; padding: 0; margin: 0; display: grid; gap: 2rem; }
ol.turn > li { display: grid; grid-template-columns: 2rem 1fr; }
ol.turn .n { color: var(--muted); padding-top: .2rem; }
details > summary { list-style: none; cursor: pointer; }
details > summary::-webkit-details-marker { display: none; }
.line { display: flex; align-items: baseline; gap: 1rem; }
.line .name { font-weight: 600; color: var(--strong); flex: 1; transition: color 150ms; }
summary:hover .name { color: var(--accent); }
.brief { margin-top: .3rem; max-width: var(--measure); }
.how { margin-top: .45rem; }
.how .act { color: var(--accent); }
.how .act:hover { text-decoration: underline; text-underline-offset: 3px; }
details[open] .how::after { content: " · less"; }
details:not([open]) .how::after { content: " · more"; }
.more { margin-top: 1.25rem; padding-left: 1.25rem; border-left: 1px solid var(--edge); max-width: calc(var(--measure) + 1.25rem); }
.label { margin: 1.5rem 0 .5rem; }
.more > .label:first-child { margin-top: 0; }

ol.calls { margin: 0; padding-left: 1.2em; display: grid; gap: 1.1rem; }
ol.calls li::marker { color: var(--muted); font-family: var(--font-mono); font-size: .8125rem; }
.call-head { display: flex; gap: 1rem; align-items: baseline; }
.call-head > span { flex: 1; color: var(--body); }
.call-rest { color: var(--muted); margin-top: .3rem; }
ul.sessions, ul.plain { list-style: none; margin: 0; padding: 0; display: grid; gap: .45rem; }
ul.sessions li, ul.plain li { display: flex; gap: 1rem; align-items: baseline; }
ul.sessions li > span:first-child, ul.plain li > span:first-child { flex: 1; }
.demo { display: flex; gap: 1rem; align-items: baseline; }
.demo code { flex: 1; overflow-wrap: anywhere; font-size: .8rem; color: var(--muted); }
code { background: var(--ground-2); padding: .08em .3em; border-radius: 3px; }

button.copy { flex: none; border: 0; background: none; padding: 0; font: 400 .8125rem/1.5 var(--font-mono); color: var(--muted); cursor: pointer; transition: color 150ms; }
button.copy:hover { color: var(--accent); }

/* without you, later: quiet lists */
.theme + .theme { margin-top: 2.25rem; }
.theme .v-h3 { margin: 0 0 .75rem; }
ul.quiet { list-style: none; margin: 0; padding: 0; display: grid; gap: .9rem; }
ul.quiet li { display: grid; grid-template-columns: 1fr auto; column-gap: 1rem; align-items: baseline; }
.name-s { color: var(--body); }
.brief-s { grid-column: 1 / -1; color: var(--muted); max-width: var(--measure); }
ul.landed { list-style: none; margin: 0; padding: 0; display: grid; gap: .4rem; }
ul.landed li { display: grid; grid-template-columns: 6.5rem 1fr; gap: 1rem; align-items: baseline; }
footer { padding: 5rem 0 4rem; }

#toast { position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%); background: var(--ground); border: 1px solid var(--edge);
  border-radius: var(--radius); padding: .35rem .9rem; font: .8125rem var(--font-mono); color: var(--muted); opacity: 0; transition: opacity 200ms; pointer-events: none; }
#toast.on { opacity: 1; }
</style>
</head>
<body>
<header class="row page">
  <span class="v-h3">board</span>
  <nav><a href="file:///home/max/repos/github/MaxWolf-01/agents/agent/board.html">all tickets</a></nav>
  <button class="scheme" id="scheme" title="switch colour scheme">
    <svg class="sun" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
    <svg class="moon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/></svg>
  </button>
</header>
<main class="page">
  <section class="hero">
    <h1 class="v-title">agents</h1>
    <p class="v-meta">{{META}}</p>
    <p class="v-lead">{{LEAD}}</p>
  </section>

  <section>
    <div class="divider"><span class="v-meta">your turn</span><span class="rule"></span><span class="v-meta">{{TOTAL}}</span></div>
    <ol class="turn">{{TURN}}</ol>
  </section>

  <section>
    <div class="divider"><span class="v-meta">without you</span><span class="rule"></span></div>
    <p class="intro v-small">{{RUNNING}} These can start whenever you say. Each comes back as a build to rule on, and the time beside it is yours for that.</p>
    {{THEMES}}
  </section>

  <section>
    <div class="divider"><span class="v-meta">later</span><span class="rule"></span></div>
    <p class="intro v-small">Ideas and design sessions nobody needs yet.</p>
    <ul class="quiet">{{LATER}}</ul>
  </section>

  <section>
    <div class="divider"><span class="v-meta">landed this week</span><span class="rule"></span></div>
    <ul class="landed">{{LANDED}}</ul>
  </section>
</main>
<footer class="page"></footer>
<div id="toast" role="status"></div>
<script>
  const root = document.documentElement;
  const theme = new URLSearchParams(location.search).get("theme");
  root.dataset.theme = (theme ? theme === "night" : matchMedia("(prefers-color-scheme: dark)").matches) ? "night" : "day";
  document.getElementById("scheme").addEventListener("click", () => root.dataset.theme = root.dataset.theme === "night" ? "day" : "night");
  const toast = document.getElementById("toast");
  let timer;
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-copy]");
    if (!b) { if (e.target.closest("summary a")) e.stopPropagation(); return; }
    e.preventDefault(); e.stopPropagation();
    const say = (m) => { toast.textContent = m; toast.classList.add("on"); clearTimeout(timer); timer = setTimeout(() => toast.classList.remove("on"), 1600); };
    (navigator.clipboard?.writeText(b.dataset.copy) ?? Promise.reject()).then(() => say("copied"), () => say("could not copy"));
  }, true);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    OUT.write_text(render())
    print(OUT)
