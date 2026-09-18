---
status: review
---

# The board opens a ticket's review page served, so a review starts from the board

Ruled worth doing by the user in chat, 2026-09-18. The board links each ticket's review page as a file, and a page opened as a file is read-only: the user clicks through from needs-my-review, cannot comment, and has to find the session that rendered the page and ask it to serve it. The queue exists so a review starts from the board.

## What to build

The board links a ticket's review page at the address it is served on, so a click from the board opens a page that saves comments. `diffview --serve <dir>` is idempotent and prints the address it serves a directory on; the board can ask it at render time for each diffviews directory it links into, or derive the address the same way `diffview` does, whichever keeps one home for the port. A page whose server has exited (it stops itself a while after the last page closes) is served again by the board's next render, or the link says how.

## Acceptance criteria

- [ ] A review-page link on the board opens a served page; a comment made there is saved beside the page.
- [ ] The address is derived or asked from `diffview`, never hard-coded in the board.
- [ ] `test_board.py` covers the link's form.
- [ ] Demo: `agent/show/board-links-served-pages/demo`, executable, no arguments: a toy tracker with one rendered review page, the board rendered, the link's address shown and fetched.
