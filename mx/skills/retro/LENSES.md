# The workflow retro's leading words and questions

The workflow is the mx plugin: its skills, scripts, hooks and checks, run in every repo max works in. Each word below names friction that recurs, on max's side (his time, attention or nerves) or the agents' (slower, costlier, less successful), or both; the questions after them are max's, as he kept them in his brainstorm of 2026-10-13. A word or a question is a lead, never a quota.

## Words

- **meat proxy**: max carrying what an agent or a tool could have fetched or done: describing what he sees, pasting, running steps by hand, waiting on a turn.
- **repeating himself**: max saying again what he said before, in the session or in an earlier one.
- **didn't land**: a message that missed: too long or too loose to read, a frame or an assumption max had to correct, a question he need not have been asked.
- **fog of war**: what max could not see or follow: where a thing is, what is running, what changed, a page he could not read.
- **churn**: work built and then reverted or never used; workflow tooling reworked for its own sake.
- **frustration**, in max's own words.
- **reinvention**: the same throwaway tool rebuilt across sessions.
- **escaped defect**: a bug found after merge, or a defect a lint, a type, a test or a render check could have caught, and the cheapest stage that could have caught it.
- **rubber stamp** and **"glad I looked"**: a look, a review or a gate that changed nothing, and one that found something; what a reviewer should have held the diff to.
- **one-way and two-way doors, hinges**: whether what a gate guards is cheap to undo; a hinge mark, right or wrong, is evidence.
- **a word that beats a skill**: where one of max's words did more than the skill on the same ground.
- **no-op**: an instruction that changes nothing; a skill not invoked when it should have been, or invoked and not followed.
- **bloat**: repos, PRs and their bodies, comments, docs, skills (a skill's inlined `--help` counts toward it), always-loaded files grown past what they earn.
- **scavenger hunt**: an agent's long search for a file or a fact.
- **slow loop**: expensive or repeated calls, slow or flaky suites.
- **out of reach**: logs, remote state or a tool an agent lacked; harness and hook trouble.
- **pulls its weight**: a check, hook, rule or suite the workflow added: how often it fires, on what, at what cost, and whether what it catches gets acted on. One gone noisy, or outliving the bug it was added for, is a deletion to propose.

## Questions

Numbered as max numbered them. Each reads the digests in `sessions/` and `sample/`, their `MAX:` lines and session pages above all, unless it names other data.

- **Q1** Which of my messages only carry information an agent could have fetched? Sort them: decision / taste / slop correction / carrying information / approval with no change.
- **Q2** Permission friction, in three directions: prompts or blocks I approved unchanged; blocks the agent got past by rephrasing the same action; incidents nothing blocked. *The permissions worker's, in `deep/permissions.md`; not searched here.*
- **Q3** Which approval gates never change anything?
- **Q4** Which context, environment or tool would have let the agent answer its question itself?
- **Q5** False done: work reported as done or verified that I found broken. Which check was missing? *Also the worker reports in `git/<repo>.md`.*
- **Q7** Escaped defects: for each, which stage was the cheapest place to catch it, and why did it miss? *`git/<repo>.md`: fix commits and reverts after a merge.*
- **Q11** Which kinds of work have needed no rework after merging? Look at this once. *`git/<repo>.md`. Its answer stands in the report once given, so a run whose `previous/` holds it leaves the question.*
- **Q13** Do review findings change the environment, or only the diff? Do reviews keep finding the same things? *`git/<repo>.md`: commits with a `Workflow-stage: review` trailer, and the finding indexes in worker reports.*
- **Q14** What do unrelated sessions in one repo work out again: the same files read, the same searches, the same explanation written twice?
- **Q16** For each workflow change, which observation would show it worked, and was that observation made? *The agents repo's commits in `git/`, then the sessions after each.*
- **Q17** Per skill, how big is it at each release (not a running total), and how many rules were added versus retired? *The mx releases in `versions.md`, each with its commit, at which a skill reads as `git -C <agents repo> show <sha>:mx/skills/<skill>/SKILL.md`.*
- **Q18** Did parallel workers or orchestrators duplicate work, or miss a shared root cause? *`git/<repo>.md`: the tickets and worker reports of one wave.*
