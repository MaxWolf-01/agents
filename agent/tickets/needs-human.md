# Needs human


- debrief: board-orients :: Merged into master as `4d6c323`, with the tracker migration in `8629db1`.
  - **Fixed at close-out.** 13's whole-feature review, two rounds of four axes, with 58 findings and 51 on its own fixes, in `46b551f` to `5d16011`. A test stub that echoed JSON through dash, in `7077ed2`. Two slices each defining the test helper `moved`, in `a160de1`.
  - **Proposed tickets from the feature.** `one-demo-tracker`, `layout-probes-are-scripts`, `board-splits-at-its-seams`, `the-board-reads-what-a-box-cuts-off` (13) and `layout-check-flaky` (14 and 16). `debrief-ticket` and `readme-reshoot` moved out of the feature, postponed. `context-checkpoints` came from 13's D5.
  - **Left, with the reason.** `make harden` did not run, because the repo has no target for it (`harden-has-no-target`). The board's layout check is an expected failure until `layout-check-flaky` fixes it or retires it. No fuzz run, because the repo has no `make fuzz`.
