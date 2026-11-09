"""A session's plan: the file `plan` in its directory, which the agent keeps as the work moves and
the page's tasks column draws (RULES.md, The plan).

One step a line, `<state> <text>`, then fields after ` | `, each opened by its keyword:

    doing Prototype the new top of the session page | waits Q12 Q13 | see agent/show/top/index.html
      next The phone layout of it
    done  Merge the heavy-work line | settles Q14
    doing Collect last week's denials | job a local subagent

A line indented two spaces deeper than the one above is a step under it: a tangent, or a step that
waits on it. `#` opens a comment line. The file is read leniently, since nothing checks it as it is
written: a line whose first word is no state is a `next` step of all its words, and a field of no
keyword stays part of the text.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PLAN = "plan"  # in the session's directory
STATES = ("wait", "doing", "next", "done")
State = Literal["wait", "doing", "next", "done"]
TAG = re.compile(r"[QA]\d+")


@dataclass(frozen=True)
class PlanStep:
    state: State
    text: str
    # The questions and to-dos it names, under `waits` or `settles`: while it is open they hold it
    # up, and once it is done they leave the page, settled by what the step did.
    names: tuple[str, ...] = ()
    see: tuple[str, ...] = ()  # artefacts to look at for it, paths as a turn record's links take them
    jobs: tuple[str, ...] = ()  # what runs it in the background, in words
    under: tuple["PlanStep", ...] = ()


def read_plan(directory: Path) -> tuple[PlanStep, ...]:
    """The plan in `directory`, its steps in the file's order; none where there is no plan."""
    path = directory / PLAN
    if not path.is_file():
        return ()
    # Each open level is the steps read so far at that depth, as lists the next line may extend.
    top: list[tuple[PlanStep, list]] = []
    levels: list[list[tuple[PlanStep, list]]] = [top]
    for line in path.read_text().split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        depth = min((len(line) - len(line.lstrip())) // 2, len(levels) - 1)
        del levels[depth + 1:]
        children: list = []
        levels[depth].append((step_of(line.strip()), children))
        levels.append(children)
    return built(top)


def built(level: list[tuple[PlanStep, list]]) -> tuple[PlanStep, ...]:
    return tuple(PlanStep(s.state, s.text, s.names, s.see, s.jobs, built(children)) for s, children in level)


def step_of(line: str) -> PlanStep:
    head, *fields = line.split(" | ")
    first, _, rest = head.partition(" ")
    state, text = (first, rest.strip()) if first in STATES else ("next", head)
    names, see, jobs = [], [], []
    for f in fields:
        keyword, _, value = f.strip().partition(" ")
        if keyword in ("waits", "settles"):
            names += TAG.findall(value)
        elif keyword == "see":
            see += value.split()
        elif keyword == "job":
            jobs.append(value.strip())
        else:
            text = f"{text} | {f}"
    return PlanStep(state, text, tuple(names), tuple(see), tuple(jobs))  # type: ignore[arg-type]


def walk(steps: tuple[PlanStep, ...]):
    """Every step, each before those under it."""
    for s in steps:
        yield s
        yield from walk(s.under)
