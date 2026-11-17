# Improve codebase architecture in the mx workflow

Where the candidates of [`SKILL.md`](SKILL.md) are kept, and who builds their report.

## A living report

**A repo with a living report keeps one list of candidates.** The report is `retro/report.md` in the agent repo of the project whose tracker plans the repo, the repo's own or one whose `agent/repos.toml` lists it. Run by hand on such a repo, read the report's candidates of the architecture code lens and its Dismissed section before the scan, and hold to the rules on ids and dismissals of [`../retro/REPORT.md`](../retro/REPORT.md). The scan's candidates go there, and each ruling the grilling gets on a candidate is written into that report as REPORT.md's max's verdicts section says.

## 2. Write the candidates down

In a repo with a living report they enter it as the rules above say, under the next ids. Elsewhere `candidates.md` goes in the show directory `/mx:show`'s `WORKFLOW.md` gives the work, slug `architecture-review-<date>`, and the report beside it.

## 3. The report

Fork (`/mx:fork`) to build it: the fork inherits the scan's reading, and the build loop stays out of this session, which grills from that same reading in step 4.
