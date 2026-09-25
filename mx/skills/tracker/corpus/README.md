# The corpus

Real ticket files, kept as the fixture the checks beside them read.

These five are the board-orients feature as it shipped, converted to the one-ticket model by hand:
its `spec.md` is the top-level ticket, its `NN-<slug>.md` tickets are child tickets with `parent:`,
its `blocked-by` numbers are slugs, and the `Property, reviewed:` stamps its tickets carried are
`board-orients#P<n>` citations of the properties the top-level ticket now states. The originals are
in git history, retired in `93fd4de`.

Everything else in them is what their writers wrote, wrapping and all: the assumption bullets
wrapped at about a hundred columns, the `I need from you` block a worker used before `## Questions`
existed, the headings a spec had. That is what makes the fixture worth having, so nothing here is
tidied to the shape a ticket would be written in today.
