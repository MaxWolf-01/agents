## Tests: what do the tests this diff touches actually catch?

Your sources, read in full before you judge:

{{STANDARDS}}
- the Testing seams section of `{{SPEC}}`

Judge what these tests catch, not whether they pass. Read the tests in full and the code under test.

You start in `{{CHECKOUT}}`, your own checkout of the tip under review: mutate a file there and run the tests that exercise it there, the test files that reach the mutated code rather than the whole suite. Restore the file (`git restore <path>`) before the next mutation, so each run measures one change, and add the mutation's result to your report as its run returns. A mutation the suite still passes under is the strongest evidence a finding on this axis can rest on: name the mutation, the test that should have failed, and what the suite did.

The checkout holds what the commit holds, with nothing an install would add, and it is removed when you finish. So a suite that cannot run without an install, or a test command you are not allowed to run, is a line in the report; and a finding cites the repo's paths, not your checkout's. Outside the checkout you read files and history.

Report: (a) every test-smell from `TEST-SMELLS.md`: name it and quote the hunk; (b) tests entering at a seam the Testing seams section does not name, and seams it names that the diff leaves untested; (c) executable Properties with no check in the properties directory, and reviewed ones the diff contradicts; (d) behaviour the diff adds that no test could tell from its absence.

Each finding: the test, the mutation or input it would not catch, the fix.
