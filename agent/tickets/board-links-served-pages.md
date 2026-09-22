---
status: done
diff: [f7ddec3b4660b5030d7a5b067226fc182d0ea491..1c3c3a9dbd1ee7c749c9efa042adc6ee775ba38c]
---

# The board opens a ticket's review page served, so a review starts from the board

Ruled worth doing by the user in chat, 2026-09-18. The board links each ticket's review page as a file, and a page opened as a file is read-only: the user clicks through from needs-my-review, cannot comment, and has to find the session that rendered the page and ask it to serve it. The queue exists so a review starts from the board.

## What to build

The board links a ticket's review page at the address it is served on, so a click from the board opens a page that saves comments. `diffview --serve <dir>` is idempotent and prints the address it serves a directory on; the board can ask it at render time for each diffviews directory it links into, or derive the address the same way `diffview` does, whichever keeps one home for the port. A page whose server has exited (it stops itself a while after the last page closes) is served again by the board's next render, or the link says how.

## Acceptance criteria

- [x] A review-page link on the board opens a served page; a comment made there is saved beside the page.
- [x] The address is derived or asked from `diffview`, never hard-coded in the board.
- [x] `test_board.py` covers the link's form.
- [x] Demo: `agent/show/board-links-served-pages/demo`, executable, no arguments: a toy tracker with one rendered review page, the board rendered, the link's address shown and fetched.

## Comments

The board now links every review page on the address `diffview --serve` answers for it, so a click from **needs my review** opens a page that saves comments; on branch `ticket/master/board-links-served-pages` (`685e1bc`, `fb5d592`), not merged.

**Demo** (needs `diffview` on PATH; builds and removes its own temp tracker, and the page server it starts exits a minute after that tree is gone):

    agent/show/board-links-served-pages/demo

    == a tracker with one ticket in review, under /tmp/tmp.XZUqSqiBhs
    == the review page, as dispatch renders one when the work comes back
    /tmp/tmp.XZUqSqiBhs/agent/diffviews/fix-login.html  (2 files, +8 -1, 132 KB)
    == the board
    /tmp/tmp.XZUqSqiBhs/agent/board.html
    == the address the board put on the ticket's row
    http://127.0.0.1:44946/fix-login.html
    fetched: HTTP 200, 136006 bytes
    == a comment on that page, saved the way the page saves one
    posted: HTTP 204
    beside the page:
    {"savedAt": 1, "writer": "demo", "comments": [{"id": 1, "text": "this wants a test"}], ...}

The last two steps are the comment save driven over HTTP, since this host has no browser to click in: the page's own save is that POST, and the file it lands in is the one the page reads back. To see it on your own board, open this very ticket's row once its review page is rendered: the link is an `http://127.0.0.1:…` one, and the page takes comments.

**I need from you**

- [D1] Whether `dispatch review` should keep serving `agent/diffviews` itself now that the board render on the next line does it (A1).
- [D2] Whether a board left watching should keep a page server cycling so its links stay clickable, against diffview's idle exit taking effect while the board is open (A2).
- [D3] The board reads the address out of the sentence `diffview --serve` prints. A wording change there would turn every link back into a read-only file link with the suite still green. Worth a machine-readable print from diffview, or is the demo enough of a check?

**Details, if you want them**

- [D4] `Assumptions`

  - A1 `mx/skills/dispatch/dispatch:481`: left `diffview --serve agent/diffviews` where it is, though the board render below it now covers every directory it links into. The call is idempotent, and the address it prints is what an orchestrator can hand over without the board. This is the review's finding 2, declined.
  - A2 `mx/skills/tracker/board.py:179`: the watcher reads the page server's own marker, so the server's exit is a change to re-render on, and the render puts the pages back on the port the marker kept. A board left open therefore keeps a server cycling (two renders per idle period), which is the price of a link that works when clicked; skipping those files instead left the board linking a port nobody answered on.
  - A3 `.gitignore:10`: added `agent/board.html*` and `agent/diffviews/`, outside this ticket. The board's `--help` and the tracker conventions both already say those are ignored, this repo's `.gitignore` never matched them, and the serving now writes a server's files under there too.
  - A4 `mx/skills/tracker/board.py:429`: the address is the first `http(s)://…` in what `diffview --serve` prints, and an exit code of 0. Both of its real messages ("serving … at", "already serving … at") carry it, and a directory diffview refuses leaves the pages linked as files with a line on stderr.

- [D5] Findings, review `f7ddec3..685e1bc`, light mode (a standalone ticket, no spec):

  - a link going dead once the server idled out and nothing else changed → fixed, `fb5d592`
  - `dispatch` serving the same directory the board now serves → declined, A1
  - the same directory asked twice per render, each ask a `uv run` → fixed, `fb5d592`

- [D6] Friction

  - `diffview` is not on this host's PATH, and `~/HOST.md` does not mention it either way, though the board now calls it at render time and the demo needs it. The dotfiles source in the nix store carries a runnable copy (`/nix/store/40hn1gwf7ij6xb80hfbs46f9ah8z80pk-source/bin/diffview`), which is what every verification here ran against, `PATH`-prepended for the run; everything in the transcript above is that copy's real output. A worker host with `diffview` installed, or a line in `HOST.md` saying it has none, would have saved the search.
  - `make test` cannot cover the board's side of this at all, since the test stub is the only `diffview` the suite has. The demo is the live check and nothing runs it automatically.
  - This host has no CA certificates, so the page render prints a warning about the highlight.js asset it could not fetch. Harmless, and absent on a machine with certs.
