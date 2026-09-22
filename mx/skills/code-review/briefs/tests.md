## Tests: what do the tests this diff touches actually catch?

Your sources, read in full before you judge:

{{STANDARDS}}
- the Testing Decisions section of `{{SPEC}}`

Judge what these tests catch, not whether they pass. Read the tests in full and the code under test.

Report: (a) every test-smell from the test-smell baseline: name it and quote the hunk; (b) tests entering at a seam the Testing Decisions does not name, and seams it names that the diff leaves untested; (c) executable spec Properties with no check in the properties directory, and reviewed ones the diff contradicts; (d) behaviour the diff adds that no test could tell from its absence.

Each finding: the test, the mutation or input it would not catch, the fix.
