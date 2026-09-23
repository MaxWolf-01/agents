# Needs human

- D32: may a Tests reviewer make its own checkout and run the tests there :: Today a reviewer may only read, so it cannot try a deliberate bug and see whether the tests catch it; that method found 9 real test gaps in `every-property`. Doing it in the worker's own tree is what broke a worker's test run. The fix: `git worktree add` a scratch copy inside the reviewer's report folder, edit and run the project's test command there only, remove it at the end. Yes or no; it rides along with the review-launcher amend that drops the two-at-a-time cap.
