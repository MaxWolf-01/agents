# Improve codebase architecture in the mx workflow

## Where the candidates and the report live

**A repo with a living report keeps one list of candidates.** The living report belongs to the tracker that plans the repo, kept in that tracker's agent repo, which is the repo's own or the one whose `agent/repos.toml` lists it. It is two files in that agent repo's `retro/`:

- `report.md` is what retro runs and sessions read and write.
- `report.html` is the page the user reads. Each retro run builds it from `report.md` by script and commits the two together. A verdict a session writes between runs leaves the page as it is, and the next run rebuilds it.

Run by hand on such a repo, the scan works in `report.md`:

1. Before the scan, read the report's candidates of the architecture code lens and its Dismissed section.
2. In step 2, enter the scan's candidates under the next ids, holding to the rules on ids and dismissals in [`../retro/REPORT.md`](../retro/REPORT.md).
3. In step 4, write each ruling the grilling gets on a candidate into the report, as that file's max's verdicts section says.

Elsewhere, step 2 writes `candidates.md` to the work's show directory, slug `architecture-review-<date>`, and the page step 3 builds from it goes beside it.

In step 3 a fork (`/mx:fork`) builds the page [`REPORT.md`](REPORT.md) describes, by `/mx:show`: it inherits the scan's reading, and the build loop stays out of this session, which grills from that same reading in step 4.
