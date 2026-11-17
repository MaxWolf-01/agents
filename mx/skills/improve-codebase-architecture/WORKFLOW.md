# Improve codebase architecture in the mx workflow

## Where the candidates and the report live

**A repo with a living report keeps one list of candidates.** The report is `retro/report.md` in the agent repo of the project whose tracker plans the repo, the repo's own or one whose `agent/repos.toml` lists it. Run by hand on such a repo, read the report's candidates of the architecture code lens and its Dismissed section before the scan, and hold to the rules on ids and dismissals of [`../retro/REPORT.md`](../retro/REPORT.md). The scan's candidates go there, and each ruling the grilling gets on a candidate is written into that report as REPORT.md's max's verdicts section says. In such a repo, step 2's candidates enter it as those rules say, under the next ids. Elsewhere `candidates.md` goes in the show directory of the work (`/mx:orient`, The artefacts), slug `architecture-review-<date>`, and the report beside it.

A fork (`/mx:fork`) builds the report in step 3: it inherits the scan's reading, and the build loop stays out of this session, which grills from that same reading in step 4.
