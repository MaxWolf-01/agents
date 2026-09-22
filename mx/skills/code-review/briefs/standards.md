## Standards: does it conform to the repo's documented standards and the smell baseline?

The standards sources, every one of them read in full before you judge:

{{STANDARDS}}

Then read the standards the repo never wrote down, which are the code itself: for each kind of surface the diff adds or extends (a view, a command, an error path, a module API, a test file), find the two nearest existing instances of that same kind and read them in full. They sit outside the diff and outside its call graph, so find them by kind, not by reference.

Report, per file/hunk where relevant, (a) every place the diff violates a documented standard: cite the standard (file + the rule); and (b) any smell from the smell baseline or rule violation from the skill files: name it and quote the hunk. A finding that the diff diverges from an existing convention cites two instances of that convention by file:line and states the answer they share; without them it is not a finding. Distinguish hard violations from judgement calls per the baseline's binding rules. Skip anything tooling enforces.
