---
status: review
blocked-by: [05]
priority: 3
size: XS
---

# Live state on GitHub links

## Brief

A GitHub link on a ticket shows whether its pull request is open, a draft, merged or waiting on changes, or its issue open or closed, without opening it.

Slice of `spec.md`, building on the Decision on GitHub state.

## What to build

The board resolves every `gh` reference in one GraphQL query per render; GitHub gives issues and pull requests one number space per repository, so the board tells them apart without being told. The answer is cached beside the board with a short lifetime, so the watcher makes one request per lifetime rather than one per reference. A link shows its state in its own look and says it in words on hover. No network or no `gh` auth leaves the links bare and says so once on the page.

## Acceptance criteria

- [x] The no-request-on-an-unchanged-render and render-without-GitHub checks from 01 pass and their annotations are gone.
- [x] Property, reviewed: every mark on a row explains itself on hover in words.
- [x] A merged pull request reads as merged without opening it.
- [x] Demo: a board rendered against real references in two repositories, and the request count for two renders in a row.

## Questions

- [D1] **How long should an answer stand?** Five minutes is mine; the spec says "a short lifetime" and gives no number. A pull request that merges reads as it was at the last render for up to that long, and the board asks GitHub at most once a window however often the tracker moves.
- [D2] **A question GitHub could not answer is cached like an answer.** So an unauthenticated board asks once a window rather than once a render; the cost is that logging `gh` in shows on the board only at the next window, or on deleting `agent/board.html.github.json`. The alternative is asking again on every render while it keeps failing.
- [D3] **Nothing ages a state out on a quiet tracker.** The watcher renders on a change under the tracker, so on a tracker nobody touches, a pull request that merges is never asked about again and the link stays open indefinitely. A watcher that re-renders when its answer lapses is a slice of its own.
- [D4] **Colour alone separates open, waiting on changes and merged.** Closed is struck through and a draft underlined, but those three differ in hue only, which asks something of the reader in the day scheme and everything of a colourblind one. The alternative is the state as a word on the link, at four to seven characters of row width per reference.

## Comments

Every `gh` reference on the board is resolved in one GraphQL query per render, cached beside the
page for five minutes, and each link wears the state that came back (merged, closed, a draft, a
review asking for changes, open) and says it in words on hover; no `gh`, no auth or no network
leaves every link bare and says why once at the top of the page. On branch
`ticket/board-orients/07-github-state`, not merged. My calls for you are this ticket's `## Questions`.

**Demo**

    agent/show/board-orients/07-github-state/demo

builds the demo tracker, puts three real references from two repositories on two of its tickets,
renders the board twice, and prints the queries those two renders cost. It has two halves, and the
second is yours to run.

The half that runs anywhere, run here, where `gh` is installed and logged out:

    $ agent/show/board-orients/07-github-state/demo
    /tmp/board-gh-demo/agent/board.html
    /tmp/board-gh-demo/agent/board.html

    Answering from nothing: GitHub was out of reach, and the page says so once.
    GraphQL queries sent for those two renders: 1

    What the board cached beside the page, which is what the second render read:

        {
         "asked": "2026-09-23T11:01:11.097873+00:00",
         "refs": [
          "anthropics/claude-code#96304",
          "cli/cli#1",
          "cli/cli#2"
         ],
         "states": {},
         "missing": "GitHub did not answer (To get started with GitHub CLI, please run:  gh auth login), so no GitHub link says whether it is open, merged or waiting on changes."
        }

The script prints where to look and what to look at, so this comment does not repeat it. What the
run above shows is the board with GitHub out of reach: one grey note at the top of the page
carrying that sentence, every reference the muted link it has always been, and one query between
the two renders, the second having read the answer from the file above.

**The half that needs your machine**, where `gh` is logged in. This is the leg I cannot run, since
this host has no GitHub credentials:

    agent/show/board-orients/07-github-state/demo

Same two renders, same one query, and the three links now differ from each other. The walkthrough
the script prints names each one and the words it says on hover.

To see that half without a login, `--stubbed` answers the query from `references.json` beside the
script, with the states those three references were in on 2026-09-23, read from `api.github.com`
that day:

    $ agent/show/board-orients/07-github-state/demo --stubbed
    ...
    Answering from references.json beside this script, as those three stood on 2026-09-23.
    GraphQL queries sent for those two renders: 1
    ...
         "states": {
          "cli/cli#1": "pr-merged",
          "cli/cli#2": "issue-closed",
          "anthropics/claude-code#96304": "issue-open"
         },
         "missing": ""

**The figure**

    agent/show/board-orients/07-github-state/figure.py    # writes figure.html beside it

`agent/show/board-orients/07-github-state/figure.html` is the change itself: the board before this
slice, the board after it, and the board after it with GitHub out of reach, as three panels of
rows lifted out of three real renders of that same tracker. The before panel runs the board as
`eaf3703` had it, read out of git, so it is what the board did rather than an account of it. Every
row sits under the board's own stylesheet, so the links are live: hover one and the words that
appear are the board's. Each panel carries a numbered note per link, and the day/night switch puts
all three through the other scheme. It is committed, so opening it needs no build; running
`figure.py` rebuilds it byte for byte.

**Details, if you want them**

- [D5] Assumptions
  - A1 `mx/skills/tracker/github.py:26`: the answer stands five minutes and a query waits twenty seconds; the spec gives neither number (D1).
  - A2 `mx/skills/tracker/github.py:72`: a question GitHub could not answer is written to the cache like an answer, so the next render inside the window asks nothing (D2).
  - A3 `mx/skills/tracker/github.py:118`: an answer carrying `data` is read whatever exit code `gh` gives it, since gh prints the body of a request it considers failed; a reference inside it that did not resolve stays bare and is not an absence, because the board asked and was answered.
  - A4 `mx/skills/tracker/github.py:157`: the answer is matched back to the reference as the ticket wrote it, differing case included; a repository renamed since the ticket was filed still goes bare, which keying by the query's own aliases would have caught, at the price of a check that mirrors the aliases rather than reading GitHub's answer.
  - A5 `mx/skills/tracker/board.py:1843`: the hues are mine, from the board's callout set (the spec defers them to agent taste); the spec's "Links stay the house accent" is older than this ticket's "a link shows its state in its own look", so the build follows the ticket and that sentence wants a one-line amendment when the ruling lands (D4).
  - A6 `mx/skills/tracker/board.py:1491`: `render_page` takes the answer as a defaulted argument, against the file's habit of defaults for production callers, because a property check from 01 calls it without one and a property is not mine to edit.
  - A7 `mx/skills/tracker/test_board.py:1513`: my `queries()` helper repeats the lambda inside that same property check, for the same reason.
  - A8 `mx/skills/tracker/github.py:57`: the Property "a render that finds nothing changed makes no GitHub request" is read as holding within the answer's lifetime; past it an unchanged render asks again, which is what the spec's own "short lifetime" asks for, and what the second check beside it now pins (D1).
  - A9 `mx/skills/tracker/conftest.py:60`: the shared stub fixture looked `tr` up after cutting PATH down, so every stub recorded an empty line and leaked "tr: not found" into the stubbed tool's stderr, which the board reads as GitHub's words; it now resolves `tr` before the cut and asserts it exists. Without that, 01's query-count property counts zero and passes for the wrong reason.
  - A10 `mx/skills/tracker/test_board.py:1541`: the query's shape is held by a rule (no state asked for under its own name), not by GitHub's schema, which is a 2 MB download; the command that validates the real thing is in that check's docstring.
- [D6] Findings, from `/mx:code-review` over `3d29de3..1d5ba17`, four axes, reports in `agent/reviews/3d29de3..1d5ba17/`
  - Fixed in e4a7748: the query merging `PullRequest.state` and `Issue.state` under one response name, which GraphQL rejects and GitHub's server tolerates only behind a flag it has announced it will flip (correctness 1); GitHub's answer outside the content stamp, so a merge that moves no file never reloaded the open tab (correctness 2, standards 11); an answer keyed by GitHub's canonical repository name and never found again when the ticket wrote another case (correctness 3, standards 16, spec C1); `resolve`'s injected clock that nobody passed (standards 6, spec scope); the lifetime and the timeout unmarked as this slice's numbers (spec A2); `gh_links`' docstring promising a note that is never said (standards 1); the `--help` still calling the render deterministic from disk (standards 2); the fixture comment blaming newlines in a query that has none (standards 3); the demo's usage line saying the reverse of what `--stubbed` does (standards 5). Eight checks the review found missing, each confirmed against the mutation it names: a cached answer dressing the links it served (tests 1), a tracker that changed without its references changing and one naming no reference at all (tests 3, spec A3/A4), a cache this version cannot read (tests 3), a `gh` that never answers (tests 3), a draft whose review asked for changes (tests 5), every state having a look of its own on the page (tests 4), the stamp moving on a state change, and the query's own shape.
  - Fixed in 48e5f34: the unknown state spelled two ways in one f-string (standards 8); the stub fixture's silent `tr` fallback (standards 9); a stub that could be asked to fail without words to fail with (standards 10); the CSS comment's unprovenanced purple and its figurative clause (standards 13); the module docstring's "a board with nothing to ask" naming the wrong branch (standards 14); the demo header over-promising a count per render (standards 15).
  - Declined, with the reason in the assumption it stands on: `render_page`'s default (standards 7) → A6; the duplicated query-count helper and its "auth probe" comment (standards 4) → A7; the hover check reading the state word out of the state's name rather than pinning the sentence (tests 6) → the oracle is the ticket's sentence, that a link says which of the two it is and which state it is in, and pinning `SAYS` would make the check the implementation; the unchanged-render Property against the lifetime (tests 2) → A8 and D1; a reference GitHub did not answer for saying nothing on the page (tests, spec) → A3.
- [D7] Friction
  - This host has no GitHub credentials, so the authenticated query has never run: the one part of the change no check on the branch could reach. What stood in for it was GitHub's own published schema (`docs.github.com/public/fpt/schema.docs.graphql`) through `graphql-core`, which caught a real bug the whole suite was blind to: the board would have gone bare on every link the day GitHub flips its legacy flag. A read-only token on the worker host would have caught it at the first render, and the demo's online half would not be yours to run.
  - The stub fixture every worker shares recorded nothing at all, because it looked `tr` up after cutting PATH down to the board's own tools. The failure surfaced three layers away, as a query count of zero, and reads exactly like "the board never asked". A stub that asserts what it needs, as it now does, turns that into one line.
  - A feature ticket is read from the worktree its feature is named after, so writing a `gh:` list into `agent/tickets/<feature>/NN-*.md` in the main checkout changes nothing the board renders. It cost me two test rewrites before I saw it; both GitHub fixtures now hang their references on standalone tickets, and the one check that needs a feature builds its own tracker.
  - The demo tracker's two `gh` references are both in one repository, so "two repositories" meant the demo rewriting them. A fixture that already spans two would have made the demo three lines shorter.

---

Rebased onto `board-orients` with 02, 03, 04, 05 and 10 landed: 10 retired the needs-human queue,
so `render`, `render_page` and `content_stamp` lost their `queue` argument and the three queue
checks went, this slice's one edit among them. Nothing of the slice was lost in the resolution
(`github.py` and `conftest.py` are byte for byte what they were). The before-and-after figure the
ruling on showing a landed change asks for is `figure.html` in the show directory, described under
**The figure** above, and the demo's walkthrough now names what changed rather than what is there.
Still on branch `ticket/board-orients/07-github-state`, not merged.

- [D8] Assumptions
  - A11 `agent/show/board-orients/07-github-state/figure.py:1`: the figure is the board's own rows under the board's own stylesheet rather than screenshots, because `agent/show/**/*.png` is gitignored and a picture cannot be hovered, which is half of what this slice added. The cost is that the panels are HTML in the repo: 67 KB of it, rebuilt byte for byte by the script beside them.
  - A12 `agent/show/board-orients/07-github-state/references.json:1`: the figure and the demo stub GitHub's answer from one file rather than asking, so both render the same on any machine and on any day; the states in it were read from `api.github.com` on 2026-09-23 and the review confirmed all three against the live API.
  - A13 `agent/show/board-orients/07-github-state/figure.py:43`: the before panel is pinned to `eaf3703`, the commit this slice was cut from, by a default the flag can override; after the merge that sha is still in the repo's history, which is what makes the panel reproducible.
- [D9] Findings, from `/mx:code-review` light over `eaf3703..086a91f`, report in `agent/reviews/eaf3703..086a91f/light.md`
  - Fixed in this round: the figure built in a random temp directory it then deleted, so the committed page carried 66 dead paths and six review-page links that opened nothing, and no rebuild matched the last one (correctness 1); `.rows { overflow-x: auto }` making a scroll box, which clipped the words of the bottom row's link in every panel, the one link a note tells you to hover (correctness 2); hand-rolled argument parsing where the repo's answer is tyro, so `--help` exited 1 (standards 3); fourteen em dashes in the figure's notes, the demo's text and this comment (standards 4); four of D5's anchors and A2's, which the rebase moved by 30 to 42 lines (standards 5); this comment re-narrating the walkthrough, and its copy already drifted to a group the rows are no longer in (standards 6); the demo and the figure holding the same references and the same stubbed answer in two languages (standards 7); `--before` working only backwards, since it copied one file out of a commit whose board imported no siblings (standards 8); the badges in the third panel reading 2 before 1; `mark()`'s split-and-rejoin; and the demo saying "Answering from GitHub itself" above a cache that says GitHub did not answer.
  - The commit message of 086a91f says "the three queue checks this slice had touched went with it". The slice had touched one of them; the other two were 03's and 10's, and all three went.
  - Nothing declined.
- [D10] Friction
  - The `path_with` guard that keeps the suite off the machine's own `gh` was a line I had added to a check ticket 10 then deleted, and nothing would have failed if I had dropped it in the rebase: the suite would simply have started making real GitHub requests from one check. A guard that lives in a fixture rather than in each check's argument list would not be rebase-fragile, which is 01's `path_with` growing a second job.
  - A figure of a page wants the page's own CSS, and the board's is 700 lines inside its script. Lifting the whole `<style>` out of a render is what made the panels faithful, and it is also why `figure.html` is 67 KB of mostly duplicated stylesheet. A board that wrote its stylesheet beside the page would make every figure of it a link instead.
