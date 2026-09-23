## Tests: what do the tests this diff touches actually catch?

Your sources, read in full before you judge:

{{STANDARDS}}
- the Testing Decisions section of `{{SPEC}}`

Judge what these tests catch, not whether they pass. Read the tests in full and the code under test.

You start in `{{CHECKOUT}}`, a checkout of the tip under review that belongs to this review and to you: mutate a file there, run the project's test command there, and put the file back (`git checkout -- <path>`) when that mutation has told you what it can. A mutation the suite fails to catch is the sharpest evidence this axis can carry, so where a finding rests on one, name the mutation, the test that should have failed, and what the suite did instead. The checkout is removed when you finish, which makes the report the only thing that outlives it: cite the repo's paths, never your checkout's. Everywhere else you read and you run git, so a test runner this project needs that you are not allowed to run is a line in the report rather than a route around it.

Report: (a) every test-smell from `TEST-SMELLS.md`: name it and quote the hunk; (b) tests entering at a seam the Testing Decisions does not name, and seams it names that the diff leaves untested; (c) executable spec Properties with no check in the properties directory, and reviewed ones the diff contradicts; (d) behaviour the diff adds that no test could tell from its absence.

Each finding: the test, the mutation or input it would not catch, the fix.
