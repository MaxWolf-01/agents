## Reading the diff: one pass per question

The sections below are your passes, worked in the order they come: each one reads its own sources and sweeps the whole diff for its question before the next one opens its sources. Your report keeps them apart: a `## <pass>` heading per pass, in that order, each finding under the pass that found it, and a pass that found nothing says so in a line, so one failure stays visible beside passes that came back clean.

The commit messages above are orientation over the diff, the author's account of what each commit does, never an anchor to judge it against. Nothing else in this prompt says what the work was asked for: where a section below carries it, judge the diff against that as well; where none does, judge the diff on its own terms and invent no requirement for it.
