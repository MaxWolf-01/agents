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
page for five minutes, and each link wears the state that came back — merged, closed, a draft, a
review asking for changes, open — and says it in words on hover; no `gh`, no auth or no network
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

    Answering from GitHub itself.
    GraphQL queries sent for those two renders: 1

    What the board cached beside the page, which is what the second render read:

        {
         "asked": "2026-09-23T10:27:57.983924+00:00",
         "refs": [
          "anthropics/claude-code#96304",
          "cli/cli#1",
          "cli/cli#2"
         ],
         "states": {},
         "missing": "GitHub did not answer (To get started with GitHub CLI, please run:  gh auth login), so no GitHub link says whether it is open, merged or waiting on changes."
        }

Open `/tmp/board-gh-demo/agent/board.html`. At the top of the page, above the rows, is one grey
note carrying that same sentence: the board's one word about GitHub, said once however many links
it shows. In the *needs me* group, the row "Map columns once per bank" carries `cli/cli#1` and
`cli/cli#2` to the right of its name, after the green `review page` link; in *frontier*, "A faster
test suite" carries `anthropics/claude-code#96304`. All three are the muted grey the board has
always given a reference, and hovering one says only "A pull request or issue this ticket names, on
GitHub." That is the board with GitHub out of reach, and the two renders cost one query between
them: the second read the answer from the file above.

**The half that needs your machine**, where `gh` is logged in — this is the leg I cannot run, since
this host has no GitHub credentials:

    agent/show/board-orients/07-github-state/demo

Same two renders, same one query. The note at the top of the page is gone, and the three links now
differ from each other: `cli/cli#1` in purple (a merged pull request), `cli/cli#2` struck through (a
closed issue), `anthropics/claude-code#96304` in the moss accent (an open issue). Hover each for
the words — "A merged pull request on GitHub.", "A closed issue on GitHub.", "An open issue on
GitHub." — and the switch in the top bar puts the same three through the night scheme. The `states`
map in the cache file names what the board made of each reference.

To see that half without a login, `--stubbed` answers the query from the script with the states
those three references were in on 2026-09-23, read from `api.github.com` that day:

    $ agent/show/board-orients/07-github-state/demo --stubbed
    ...
    Answering from this script, as the three references stood on 2026-09-23.
    GraphQL queries sent for those two renders: 1
    ...
         "states": {
          "cli/cli#1": "pr-merged",
          "cli/cli#2": "issue-closed",
          "anthropics/claude-code#96304": "issue-open"
         },
         "missing": ""

which is the render the paragraph above describes, on this host, with GitHub's answer faked and
everything after it real.

**Details, if you want them**

- [D5] Assumptions
  - A1 `mx/skills/tracker/github.py:26`: the answer stands five minutes and a query waits twenty seconds; the spec gives neither number (D1).
  - A2 `mx/skills/tracker/github.py:71`: a question GitHub could not answer is written to the cache like an answer, so the next render inside the window asks nothing (D2).
  - A3 `mx/skills/tracker/github.py:118`: an answer carrying `data` is read whatever exit code `gh` gives it, since gh prints the body of a request it considers failed; a reference inside it that did not resolve stays bare and is not an absence, because the board asked and was answered.
  - A4 `mx/skills/tracker/github.py:157`: the answer is matched back to the reference as the ticket wrote it, differing case included; a repository renamed since the ticket was filed still goes bare, which keying by the query's own aliases would have caught, at the price of a check that mirrors the aliases rather than reading GitHub's answer.
  - A5 `mx/skills/tracker/board.py:1885`: the hues are mine, from the board's callout set (the spec defers them to agent taste); the spec's "Links stay the house accent" is older than this ticket's "a link shows its state in its own look", so the build follows the ticket and that sentence wants a one-line amendment when the ruling lands (D4).
  - A6 `mx/skills/tracker/board.py:1530`: `render_page` takes the answer as a defaulted argument, against the file's habit of defaults for production callers, because a property check from 01 calls it without one and a property is not mine to edit.
  - A7 `mx/skills/tracker/test_board.py:1543`: my `queries()` helper repeats the lambda inside that same property check, for the same reason.
  - A8 `mx/skills/tracker/github.py:57`: the Property "a render that finds nothing changed makes no GitHub request" is read as holding within the answer's lifetime; past it an unchanged render asks again, which is what the spec's own "short lifetime" asks for, and what the second check beside it now pins (D1).
  - A9 `mx/skills/tracker/conftest.py:60`: the shared stub fixture looked `tr` up after cutting PATH down, so every stub recorded an empty line and leaked "tr: not found" into the stubbed tool's stderr, which the board reads as GitHub's words; it now resolves `tr` before the cut and asserts it exists. Without that, 01's query-count property counts zero and passes for the wrong reason.
  - A10 `mx/skills/tracker/test_board.py:1571`: the query's shape is held by a rule (no state asked for under its own name), not by GitHub's schema, which is a 2 MB download; the command that validates the real thing is in that check's docstring.
- [D6] Findings, from `/mx:code-review` over `3d29de3..1d5ba17`, four axes, reports in `agent/reviews/3d29de3..1d5ba17/`
  - Fixed in e4a7748: the query merging `PullRequest.state` and `Issue.state` under one response name, which GraphQL rejects and GitHub's server tolerates only behind a flag it has announced it will flip (correctness 1); GitHub's answer outside the content stamp, so a merge that moves no file never reloaded the open tab (correctness 2, standards 11); an answer keyed by GitHub's canonical repository name and never found again when the ticket wrote another case (correctness 3, standards 16, spec C1); `resolve`'s injected clock that nobody passed (standards 6, spec scope); the lifetime and the timeout unmarked as this slice's numbers (spec A2); `gh_links`' docstring promising a note that is never said (standards 1); the `--help` still calling the render deterministic from disk (standards 2); the fixture comment blaming newlines in a query that has none (standards 3); the demo's usage line saying the reverse of what `--stubbed` does (standards 5). Eight checks the review found missing, each confirmed against the mutation it names: a cached answer dressing the links it served (tests 1), a tracker that changed without its references changing and one naming no reference at all (tests 3, spec A3/A4), a cache this version cannot read (tests 3), a `gh` that never answers (tests 3), a draft whose review asked for changes (tests 5), every state having a look of its own on the page (tests 4), the stamp moving on a state change, and the query's own shape.
  - Fixed in 48e5f34: the unknown state spelled two ways in one f-string (standards 8); the stub fixture's silent `tr` fallback (standards 9); a stub that could be asked to fail without words to fail with (standards 10); the CSS comment's unprovenanced purple and its figurative clause (standards 13); the module docstring's "a board with nothing to ask" naming the wrong branch (standards 14); the demo header over-promising a count per render (standards 15).
  - Declined, with the reason in the assumption it stands on: `render_page`'s default (standards 7) → A6; the duplicated query-count helper and its "auth probe" comment (standards 4) → A7; the hover check reading the state word out of the state's name rather than pinning the sentence (tests 6) → the oracle is the ticket's sentence, that a link says which of the two it is and which state it is in, and pinning `SAYS` would make the check the implementation; the unchanged-render Property against the lifetime (tests 2) → A8 and D1; a reference GitHub did not answer for saying nothing on the page (tests, spec) → A3.
- [D7] Friction
  - This host has no GitHub credentials, so the authenticated query has never run: the one part of the change no check on the branch could reach. What stood in for it was GitHub's own published schema (`docs.github.com/public/fpt/schema.docs.graphql`) through `graphql-core`, which caught a real bug the whole suite was blind to — the board would have gone bare on every link the day GitHub flips its legacy flag. A read-only token on the worker host would have caught it at the first render, and the demo's online half would not be yours to run.
  - The stub fixture every worker shares recorded nothing at all, because it looked `tr` up after cutting PATH down to the board's own tools. The failure surfaced three layers away, as a query count of zero, and reads exactly like "the board never asked". A stub that asserts what it needs, as it now does, turns that into one line.
  - A feature ticket is read from the worktree its feature is named after, so writing a `gh:` list into `agent/tickets/<feature>/NN-*.md` in the main checkout changes nothing the board renders. It cost me two test rewrites before I saw it; both GitHub fixtures now hang their references on standalone tickets, and the one check that needs a feature builds its own tracker.
  - The demo tracker's two `gh` references are both in one repository, so "two repositories" meant the demo rewriting them. A fixture that already spans two would have made the demo three lines shorter.
