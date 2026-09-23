"""What GitHub says about the pull requests and issues a tracker's tickets name.

One GraphQL query per render resolves every reference the board shows: GitHub gives issues and
pull requests one number space per repository, so a reference is resolved without being told which
of the two it is. The answer is cached beside the rendered board for LIFETIME, so a board watching
a busy tracker asks once a window rather than once a render, and never once a reference.

No `gh`, no auth or no network leaves every link bare and gives the page one note saying so
(board.absences). A question that could not be answered is cached like any other, so a board GitHub
is out of reach of asks once a window rather than once a render.
"""

import datetime
import json
import re
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

GH_REF = re.compile(r"[\w.-]+/[\w.-]+#\d+")  # a reference as a ticket writes it: owner/repo#number

# The spec asks for "a short lifetime" and gives no number: five minutes is 07-github-state's pick,
# the window the briefing debounces a burst of tracker changes into.
LIFETIME = datetime.timedelta(minutes=5)
TIMEOUT = 20  # seconds a render waits for GitHub before going on without it, this slice's pick too

# What a link says on hover, one per state a reference can be in. A pull request is open until it
# is merged or closed; a draft is one not offered for review yet, and a review that asked for
# changes is what "waiting on changes" means.
SAYS = {
    "pr-open": "An open pull request on GitHub.",
    "pr-draft": "A draft pull request on GitHub: not offered for review yet.",
    "pr-changes": "An open pull request on GitHub whose review asked for changes.",
    "pr-merged": "A merged pull request on GitHub.",
    "pr-closed": "A pull request on GitHub, closed without being merged.",
    "issue-open": "An open issue on GitHub.",
    "issue-closed": "A closed issue on GitHub.",
}

WHETHER = "whether it is open, merged or waiting on changes"  # what a bare link cannot say


@dataclass(frozen=True)
class Answer:
    """What a render knows about its references: the state of each one GitHub resolved, and, where
    GitHub was not asked or did not answer, the words the page says once about the absence."""

    states: dict[str, str]  # reference -> a key of SAYS
    missing: str = ""  # empty when GitHub answered


NOTHING = Answer({})  # a render that asked nothing: bare links, and no absence to report


def resolve(refs: Sequence[str], cache: Path) -> Answer:
    """The state of every reference in `refs`, from the cache beside the board while it is younger
    than LIFETIME and holds the answer to every one of them, and from GitHub otherwise.

    A reference the render did not ask about last time is enough to ask again: the query costs the
    same whatever it resolves, and a ticket filed with a new reference would otherwise wait out the
    window bare.
    """
    now = datetime.datetime.now().astimezone()
    wanted = sorted(set(refs))
    if not wanted:
        return NOTHING
    if (held := read(cache, now)) and set(held[0]) >= set(wanted):
        return held[1]
    answer = ask(wanted)
    write(cache, wanted, answer, now)
    return answer


def cache_path(board: Path) -> Path:
    """The cache beside the rendered board, as the stamp file and the briefing are."""
    return Path(str(board) + ".github.json")


def read(cache: Path, now: datetime.datetime) -> tuple[list[str], Answer] | None:
    """The references the last query asked about and what came back, or None where no answer stands:
    none written, older than LIFETIME, or a file this version cannot read."""
    try:
        held = json.loads(cache.read_text())
        if now - datetime.datetime.fromisoformat(held["asked"]) >= LIFETIME:
            return None
        return held["refs"], Answer(held["states"], held["missing"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def write(cache: Path, refs: Sequence[str], answer: Answer, now: datetime.datetime) -> None:
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(
        {"asked": now.isoformat(), "refs": list(refs), "states": answer.states, "missing": answer.missing}, indent=1
    ))


def ask(refs: Sequence[str]) -> Answer:
    """One `gh api graphql` for every reference at once. GitHub answering about some of them and
    not others (a reference to a repository this account cannot see) leaves those links bare and is
    not an absence: the board asked and was answered."""
    if not shutil.which("gh"):
        return Answer({}, f"No gh on this machine, so no GitHub link says {WHETHER}.")
    try:
        done = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={query(refs)}"], capture_output=True, text=True, timeout=TIMEOUT
        )
    except subprocess.TimeoutExpired:
        return Answer({}, f"GitHub did not answer within {TIMEOUT}s, so no GitHub link says {WHETHER}.")
    try:
        body = json.loads(done.stdout)
    except ValueError:
        body = None
    # gh prints the response body whether or not the request succeeded, and reports the failure on
    # stderr: an answer carrying data is usable even where a reference in it did not resolve.
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        said = next((line for line in done.stderr.splitlines() if line.strip()), "it said nothing")
        return Answer({}, f"GitHub did not answer ({said.strip()}), so no GitHub link says {WHETHER}.")
    return Answer(states(body["data"], refs))


def query(refs: Sequence[str]) -> str:
    """The GraphQL query that resolves every reference, its repositories asked about once each.

    Each node carries the repository and number it answers for, so the answer is read by what it
    says rather than by the aliases this query gave it. The two states are asked for under names of
    their own: one response name cannot hold two enums, and a query that merges them is one GraphQL
    rejects.
    """
    by_repo: dict[str, list[str]] = {}
    for ref in refs:
        assert GH_REF.fullmatch(ref), f"gh reference {ref!r}; a reference is owner/repo#number"
        repo, number = ref.split("#")
        by_repo.setdefault(repo, []).append(number)
    parts = []
    for i, (repo, numbers) in enumerate(by_repo.items()):
        owner, name = repo.split("/")
        asked = " ".join(
            f"n{j}: issueOrPullRequest(number: {number}) {{ __typename "
            f"... on PullRequest {{ number prState: state isDraft reviewDecision }} "
            f"... on Issue {{ number issueState: state }} }}"
            for j, number in enumerate(numbers)
        )
        parts.append(f'r{i}: repository(owner: "{owner}", name: "{name}") {{ nameWithOwner {asked} }}')
    return "query { " + " ".join(parts) + " }"


def states(data: dict, refs: Sequence[str]) -> dict[str, str]:
    """Which state each reference GitHub answered about is in, read from the answer's own account of
    which repository and number each node is, and keyed by the reference as the ticket wrote it.

    GitHub answers under the repository's canonical name, which a ticket may have written in another
    case; a row looks its reference up by the string in its own file, so the answer is matched back
    to that string."""
    wrote: dict[str, list[str]] = {}
    for ref in refs:  # two tickets may write one reference two ways, and both rows want its state
        wrote.setdefault(ref.lower(), []).append(ref)
    found = {}
    for repo in data.values():
        if not isinstance(repo, dict) or not (name := repo.get("nameWithOwner")):
            continue  # a repository the query could not resolve answers as null
        for key, node in repo.items():
            if key == "nameWithOwner" or not isinstance(node, dict) or not node.get("number"):
                continue
            if state := classify(node):
                found.update(dict.fromkeys(wrote.get(f"{name}#{node['number']}".lower(), []), state))
    return found


def classify(node: dict) -> str | None:
    """The state of one issue or pull request, as a key of SAYS.

    A merged or closed pull request is that whatever else it says; among open ones a draft is a
    draft first, since a review cannot have asked anything of one that is not offered for review.
    """
    if node.get("__typename") == "PullRequest":
        state = str(node.get("prState", "")).lower()
        if state in ("merged", "closed"):
            return f"pr-{state}"
        if node.get("isDraft"):
            return "pr-draft"
        return "pr-changes" if node.get("reviewDecision") == "CHANGES_REQUESTED" else "pr-open"
    if node.get("__typename") == "Issue":
        return "issue-closed" if str(node.get("issueState", "")).lower() == "closed" else "issue-open"
    return None
