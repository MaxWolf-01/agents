## Grug: what in this diff should not exist?

Complexity is the enemy, and the other passes look for what is wrong or missing, so this one looks for what could go. Take each thing the diff adds (code, a test, a comment, a guard, a flag, a config key, a dependency, a doc line) and ask of it in turn:

- Would the order still be met without it? A feature, fix or refactor that nothing needs is one finding as a whole, however well built.
- Where the order needs it, is a smaller form at hand: what the codebase already has, the standard library, the platform, one line, the 80/20 version that gives most of the value for a fraction of the code?
- Does a fix add what a removal would do: a new guard on code that could be simplified or deleted?
- Does an abstraction earn its interface: more than one caller, a seam the code has already shown? A cut made early costs more than the repetition it replaced.
- Can a reader follow it in one pass? "This is too complex to follow" is a finding by itself, with where you lost the thread.

Report each finding as what goes or shrinks, tagged `delete:`, `stdlib:`, `native:`, `yagni:`, `shrink:` or `refactor:`, quoting the hunk, with the case lost by removing it, or "none". A part the author names with the case it serves still gets the question of whether that case occurs.

Fewer lines are not the aim: plain repetition, or a named intermediate, beats a clever abstraction or a compressed expression, and code the diff removes earns the opposite question, why it was there.
