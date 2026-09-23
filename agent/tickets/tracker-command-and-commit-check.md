---
status: review
parent: ticket-file-contract
priority: 1
size: L
---

# The tracker command, and the commit check that runs it

## Brief

One `tracker` command does every mechanical thing to ticket files, reads and writes, and a pre-commit hook runs its check so a malformed ticket is refused the moment it is committed. The two sibling tickets build on its interface: the scripts call it, the skills name it.

Child ticket of `ticket-file-contract`, building on its Decisions: the `tracker` command owning every mechanical operation (you, r6), the flat layout with slugs as ids and `parent:` (you, r1 and r2), the pre-commit check (you, r3) installed per repo (you, r4) and running the command's own check (you, r6), and its Properties P1 to P4 and P6 (you, r5 and r6). The operations and a sketch of the interface are drawn at `agent/show/ticket-file-contract/tracker-cli.html`; the sketch is yours to redesign.

## What to build

`tracker` lives in the tracker skill and is on PATH through `mx/bin/`, as `board` is. It is the only code that reads or writes ticket files; `board`, `dispatch` and the other scripts move onto it in `scripts-go-through-tracker-command`.

Reads its callers need:

- a check over given files or the staged ones, reporting `file:line: message` and exiting non-zero on any refusal;
- one frontmatter field of one ticket, for shell scripts (`status` above all, read today by four scripts four ways);
- the whole tracker as data: every ticket with its frontmatter, sections, questions, properties, acceptance criteria and assumptions (the board, `property-coverage`);
- a ticket's context: its body, then every ancestor's body, assembled one way (the worker's brief; the review's `--spec` file);
- the frontier: the unclaimed, unblocked tickets that are open or proposed and do not need the user, with what holds the rest back;
- the Assumptions bullets whole, however the writer wrapped them (`dispatch review`'s notes, where board-orients 10 lost every line past the first).

Writes, each refusing what the tracker's rules forbid and saying which rule:

- filing a ticket: its frontmatter and skeleton, with the body left for the agent to write;
- status changes along the transitions `/mx:tracker` defines (Ticket state), e.g. `done` only for a ticket whose branch has merged, and a ticket in `review` unblocking nothing;
- recording the user's answer to a `## Questions` item (the `Ruled <date>:` line);
- retiring a ticket and its descendants, together with what the tracker retires with them (show directories, prototypes, research notes), printing each step it runs and leaving the commit to the caller.

The ticket body stays prose the agent writes in the file; the check is what holds it to the format.

`--help` states the function: the subcommands, their flags, their arguments and what each returns or refuses. The flow they sit in (when to file, what a status means, how to cut child tickets) is the tracker skill's, and the two never say the same thing (you, r6). Fewer subcommands and flags are better. Record the interface as an assumption so the user rules on it from the review page.

The pre-commit hook is a few lines that run `tracker`'s check over the staged files under `agent/tickets/`; the check has one home, in the command. Install it in this repo; the other installs belong to the sibling tickets.

## Acceptance criteria

- [x] `ticket-file-contract#P1`, `#P2` and `#P3` hold as checks over generated ticket files at `tracker`'s command line, beside the tracker skill's other tests (this repo has no `tests/properties/`).
- [x] `ticket-file-contract#P4`: a ticket's context is its body with its ancestors' bodies, in one order you choose and record, and a missing ancestor is refused like any dangling reference.
- [x] `ticket-file-contract#P6`: retiring deletes nothing that git history or `~/logs` does not keep, beyond renders whose generating source is tracked; a run over a fixture tracker shows each file's route.
- [x] Every status transition the tracker skill defines is accepted, and each one it forbids is refused with the rule named.
- [x] Every construct in the parent ticket's "What reads a ticket today" table that survives the new model has its one reading here, and the constructs the new model drops (the spec's `draft | confirmed`, `type`, NN numbering, `feature/NN` references) are refused with a line saying what replaced them.
- [x] The fixture corpus includes real ticket files from this tracker, converted to the new layout by hand: board-orients 10's wrapped Assumptions read whole.
- [ ] A commit in this repo that stages a ticket file `tracker` refuses is blocked, and the message names the file and line.

## Questions

- [D1] **The commit hook is not installed in this repo.** `tracker hook` writes into the hooks directory git points at, which on this worker host is one bare repo's, shared by every dispatch worktree on it: installing it here would have run the check over every other worker's commits, on tickets still written in the old shape. The mechanism is built and checked end to end against a fixture repo, and the demo's third panel is a real `git commit` refused; what is left is one `tracker hook` in your own checkout, which is yours to run now or to leave until the tracker is converted (A6).
  - Ruled 2026-09-23: stays as built; the hook is installed in your own checkout once the tracker is converted.
- [D2] **A reference that names no ticket is refused, where the tracker conventions count a missing one as done.** The parent ticket's P3 refuses any dangling `parent`, `blocked-by` or `<slug>#P<n>`; MARKDOWN.md's Ticket state says "A reference whose file no longer exists counts as `done`, a deleted proposal included". Both cannot hold. As built P3 wins: `retire` drops the edges onto what it retires and refuses while a ticket that stays cites a property of one leaving, so nothing is left dangling (A4). The cost is that rejecting a proposal now means dropping the edges onto it in the same commit, which the hook will say. The other reading keeps MARKDOWN.md's rule and takes `blocked-by` out of P3's reach.
  - Ruled 2026-09-23: P3 stands, as built. The gap it leaves, a rejected ticket every other one still names, is `tracker drop`.
- [D3] **A ticket the user is in the loop for is done by your ruling alone.** `done` otherwise needs the ticket's branch merged, or every child ticket done. A grilling or a piece of legwork produces conversation and rounds on somebody else's branch, so under those two rules it could never reach `done` and could never be retired. As built, a ticket carrying `needs-user: true` takes your ruling as the landing (A5). The alternative is that it gets a branch like any other build, which would make every grilling carry an empty one.

## Comments

The `tracker` command and its pre-commit hook landed on `ticket/ticket-file-contract/tracker-command-and-commit-check`, with its checks and a corpus of real ticket files beside the tracker skill; nothing is merged, and the hook is not installed in this repo (D1).

**Demo**

```
$ /home/agent/repos/dispatch/agents-ticket-file-contract-tracker-command-and-commit-check/agent/show/tracker-command-and-commit-check/demo
wrote /home/agent/repos/dispatch/agents-ticket-file-contract-tracker-command-and-commit-check/agent/show/tracker-command-and-commit-check/out/tracker-command.html
no display here; open the file above to read it
```

It builds a throwaway tracker out of the corpus and drives the real command over it, writing the walkthrough as one page: the interface, the incident read both ways (the review page's one-line-per-bullet reader beside `tracker data`, which is the before and after this change has), a commit the hook refuses construct by construct, filing, the transitions, the frontier, a ticket's context, and retiring with each file's route printed. Every run on the page is a real one.

**Details, if you want them**

- [D4] Assumptions
  - A1 `mx/skills/tracker/tracker.py:14`: the interface, which the ticket asked to have ruled on from this page. Ten subcommands: `check` (the staged files by default, which is what the hook runs), `get` one field for a shell, `data` the tracker or one ticket as JSON, `context`, `frontier`, `new`, `set field=value` with `field+=value` for a list field, `rule`, `retire`, `hook`. `set` is a general frontmatter writer rather than a `status` subcommand, since `dispatch review` has a `diff:` range to append; `data` takes a slug, a path or `-`, since a review page reads a ticket off its branch; `hook` is the eleventh thing the command does because two sibling tickets need one installer. No subcommand writes into a ticket's body.
  - A2 `mx/skills/tracker/tracker.py:645`: `needs-user: true` is the frontmatter field for a ticket worked with the user, which dispatch keeps from a worker; the parent ticket asked for one field and did not name it.
  - A3 `mx/skills/tracker/tracker.py:188`: a ticket's context is its own body first, then each ancestor's nearest first, which is the order the sketch drew and reads as the work widening; `ticket-file-contract#P4` left the order to me. Each body is headed `## <slug>` or `## parent ticket: <slug>`, so a worker can tell its own from its context.
  - A4 `mx/skills/tracker/tracker.py:668`: a `parent`, `blocked-by` or `<slug>#P<n>` that names no ticket is refused, per `ticket-file-contract#P3`, where the tracker conventions count a missing reference as done (D2).
  - A5 `mx/skills/tracker/tracker.py:368`: `done` is written for a ticket whose own branch, under either naming git has here, is merged into the branch the command runs on; for a parent ticket every child of which is done; and for a ticket the user is in the loop for (D3). There is no way past it: work landed without a ticket branch cannot be marked done here.
  - A6 `mx/skills/tracker/tracker.py:26`: `tracker hook` is not run in this repo (D1).
  - A7 `mx/skills/tracker/tracker.py:1090`: a bare `#P<n>` continues the slug cited before it in the same bullet, which is how this ticket's own criteria cite three properties of one ticket; one with no slug before it is refused. The parent ticket's Decisions give only the `<slug>#P<n>` form, so this is a second shape the prose sibling has to document if it stays.
  - A8 `mx/skills/tracker/tracker.py:976`: a top-level bullet under `## Questions` that follows a question and is not one is refused, since every reader takes it for the detail of the question above it. One *above* the first question is not refused: the board shows the section's words above its first item, so nothing is dropped there.
  - A9 `mx/skills/tracker/tracker.py:627`: a frontmatter field the tracker does not define is refused, so a typo is caught where it is written rather than read as absent.
  - A10 `mx/skills/tracker/tracker.py:533`: a render a retire may delete is an untracked file with a tracked same-stem source beside it, or one under an `out/` directory beside a tracked file; everything else untracked is moved to `~/logs`.
  - A11 `mx/skills/tracker/test_tracker.py:64`: the checks drive the command line in process rather than spawning one per example, so a property can run over a hundred generated tickets; the hook's own checks, and the one that reads `--help`, spawn the real thing.
  - A12 `mx/skills/tracker/corpus/README.md:1`: the corpus is the retired board-orients feature rather than live tickets, so the fixture is not a second home for a fact a live ticket still owns.
  - A13 `mx/skills/tracker/SKILL.md:1`: the tracker skill and `MARKDOWN.md` are left as they are, so on this branch they still describe the three kinds of file while the command refuses two of them. The prose is `skills-and-glossary-speak-one-ticket-kind`'s, which waits on this ticket; until it lands, the skill is the one agents read.
  - A14 `mx/skills/tracker/tracker.py:597`: the readers fill a caller's list of refusals rather than returning them beside their value, which the Standards review named as the repo's third shape for collecting findings. Ten tuple-returning signatures buy one less argument each; the sibling that moves `property_coverage` onto this command inherits whichever shape stays.
  - A15 `mx/skills/tracker/tracker.py:1075`: a bullet under `## Acceptance criteria` with no checkbox is not a criterion and is not refused. The Tests review read that as a drop; it is not one, since a section's whole text is what `data` hands back and what the board renders.
- [D5] Findings, from `/mx:code-review` over `a1e5b72..c6bfd6e`, four axes, reports in `agent/reviews/a1e5b72..c6bfd6e/`
  - Fixed in `842be04`, correctness: a write refused over breakage it did not make, wherever it shifted a line (`set diff+=`, `rule`); `new` built a path from a slug before checking it, writing outside the tracker; the hook blocked every commit in a repo with no tracker, and ignored `core.hooksPath`; `done` looked for `ticket/<slug>` where the branches cut here are `ticket/<base>/<slug>`, and passed on the ticket's own branch; two files claiming one slug collided silently; retiring left a linked prototype directory, skipped grandchildren, could move a note a live ticket still links, and staged less than it wrote; a bare `#P<n>` meant one thing in a criterion and another in the citation check, so a re-wrap changed a bullet's meaning; a list field written as one value was refused once per character; `get` printed Python's `True`; a broken YAML frontmatter pointed every later refusal at the wrong line.
  - Fixed in `ee22031`, found while driving the demo: `data <path>` read the surrounding tracker from the ticket's body, so a ticket read by path reported no ancestors; a section's text came from the unfenced scan, so a fenced block came back blank.
  - Fixed in `842be04`, standards: the file reads top down now (commands, rules, parser); the predicates are named for what they return; `--help` names the command; `get`'s field is a `Literal`; two flag help strings said what a status means, which is the skill's; `vars()` gave way to `asdict`; the demo's middle man and its four-clause "did this run fail" condition went.
  - Fixed in `842be04`, tests: the mutation run behind the Tests axis named 32 mutations no check could see. The fixtures that could not discriminate now do (the frontier's order and a ticket in review offered as work, a parent done on `any` child, a retire that left a grandchild or took a live ticket's note, the render rule's "whose generating source is tracked"), the expectations come from `MARKDOWN.md`'s file shape rather than from the command's own renderer, the refusals that had no input at all have one, and the seams the docstring promises (the tracker found from a subdirectory, the hook in a worktree, `--help`) are driven.
  - Fixed in `842be04`, spec and standards: the corpus conversion had renamed another feature's tickets into board-orients' slugs; the corpus says what it is in a README; three captions on the show page said something the run above them contradicted.
  - Declined: the readers' out-parameter (A14); a bullet above the first question and a criterion without a checkbox read as drops (A8, A15).
  - Noted for the siblings, not fixed here: `dispatch review`'s notes come from `tracker data`'s `assumptions` and `resolved`, whose keys are not `notes_of`'s; the `INTO` transition rules are strings in the command because a refusal has to name its rule, so `MARKDOWN.md` should point at `tracker --help` for them rather than restate them; `ticket-file-contract#P2`'s other half, every script reading through the command, is not executable at this seam.
- [D6] Friction
  - The parent ticket's P3 and `MARKDOWN.md`'s Ticket state contradict each other outright (D2), and nothing in the ticket said which wins. A build can pick, but the pick is a rule change that reaches the prose sibling and the orchestrator's reject step.
  - `tracker hook` writes into the hooks directory shared by every worktree of a repo. On a dispatch worker host that is the whole bare repo, so a worker cannot install a hook without reaching into every other worker's commits (D1). Anything that has a worker install a repo-wide hook wants an isolated clone, or a hook that only fires for the worktree that installed it.
  - The four-axis review took about 25 minutes of wall clock against a 1,100-line diff, which is most of what this ticket spent waiting. The Tests axis's mutation run was worth all of it: it found the eight fixtures that could not tell the fix from the bug, which no amount of reading had.

Addressed: D1, D2, D3

`tracker drop <slug>` landed on the same branch, in `1c04735`: the reject ruling as one command. It `git rm`s the ticket, drops the `blocking` edges onto it from the tickets that stay, prints each step and leaves the commit to the caller, so the reason for the rejection goes in that message and git history holds the file and the reason together; `--help` says so in a line. It refuses a `done` ticket, which is `retire`'s, and refuses while a ticket that stays names it as its parent or cites one of its properties, the way retiring already refuses a citation. D1 and D3 are as they were, and the rulings on D1 and D2 are written under their questions.

**Demo**

```
$ /home/agent/repos/dispatch/agents-ticket-file-contract-tracker-command-and-commit-check/agent/show/tracker-command-and-commit-check/demo
wrote /home/agent/repos/dispatch/agents-ticket-file-contract-tracker-command-and-commit-check/agent/show/tracker-command-and-commit-check/out/tracker-command.html
no display here; open the file above to read it
```

The page has a panel for it now, the eighth: a proposal dropped, the edge onto it gone from the ticket that waited on it while the edge it still has stays, and a shipped ticket refused because taking shipped work out is retiring, which is the panel after.

**Details, if you want them**

- [D7] Assumptions, continuing the block above
  - A16 `mx/skills/tracker/tracker.py:512`: `drop` takes the ticket alone and refuses while any ticket that stays names it as its parent, rather than taking the child tickets with it as `retire` does. A rejection is a ruling on one ticket, and child tickets of a rejected one are their own rulings; dropping them unasked would delete work the user never ruled on.
  - A17 `mx/skills/tracker/tracker.py:524`: the guard against uncommitted changes is now shared with `retire`, so the message both print says "a file that leaves" rather than "a retired file".
  - A18 `mx/skills/tracker/tracker.py:518`: `drop` leaves a show directory or a research note the dropped ticket owns where it is. The reject ruling discards the build with `git branch -D`, so what a rejected ticket produced lives on that branch and not in the tracker's copy; anything that did reach this branch is the caller's to remove in the same commit.
- [D8] The round
  - The suite is 336 passing, `make check` and `render-lint` clean. Seven checks cover `drop`: the four statuses it takes, the edges it sweeps and the one it leaves, the file in history and the removal staged, and each of the three refusals.
  - Nothing else moved: the review's findings from the first round stand as `842be04` left them, and D3 and D5 are as built.
