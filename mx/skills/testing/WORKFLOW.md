# Testing in the mx workflow

Who runs [`SKILL.md`](SKILL.md)'s two kinds of run, and what a ticket says about seams and properties.

## Two kinds of run

Every session and every worker runs the fast suite on every change. The full-path checks a change reaches are run by the session landing it. A landing's show is usually the output of such a run, so its runnable script (`/mx:show`, A runnable artifact) is the natural home for one: the check and the demonstration are the same run.

## The seam

The ticket's Testing seams names the seams for the work in hand (`/mx:tracker`).

## Property tests

A ticket's Properties are prose the reviewer checks each diff against, and turn into checks only by the route `SKILL.md` gives under the same heading.
