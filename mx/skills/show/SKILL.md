---
name: show
description: "Show, don't tell — replace a struggling prose explanation with the artifact that carries it: a diagram, comparison, runnable demo, chart, figure, explainer page, video, ... Use when an explanation is ballooning in text, when the user is struggling to understand something, when they ask to see it shown rather than described, or when another skill needs an explanation artifact."
---

# Show

An explanation earns an artifact when prose stops carrying it. The craft is choosing the medium: ask what would make this click in one look, weigh a few candidates against the shape of the confusion, and pick deliberately — the best medium is often not the nearest familiar tool. Then produce it, look at it yourself, put it in front of the user.

## Media worth weighing

Examples with delivery notes — an open set, not a menu; combining media is normal, and anything that carries the explanation qualifies:

- **Diagram** — structure, flow, dependencies, states. Mermaid (invoke `mx:mermaid` first) when layout should be solved for you; hand-placed SVG (read `SVG-FIGURES.md`) when the figure is the artifact and deserves the control. Either way the classic families apply: UML, flowcharts, sequence and state charts, Nassi-Shneiderman, and the rest.
- **Comparison** — show a difference instead of describing it: a code diff (`diffview`), a table, before/after, two rendered variants side by side.
- **Runnable code** — the smallest script that exhibits the behavior; run it and show the output. When the question grows into "does this design/state model feel right?", that's `/mx:prototype`.
- **HTML/JS page** — the most flexible medium: interactive figures, animations, side-by-side panels, up to a full explainer in the distill.pub tradition — prose interleaved with figures the reader can poke at. Invoke `frontend-design` so it looks intentional.
- **LaTeX/TikZ** — publication-grade figures. TeX Live is fully installed: just compile, `pdftoppm` to PNG to inspect.
- **Animation** — a process unfolding over time. Interactive JS (the reader steps and scrubs) usually beats a linear video; manim is the option for math-heavy scenes when video is the right form.

## Produce and present

- Facts in an artifact come from primary sources — the config, the code, the live system — never only from prose docs about them. Docs drift, and the artifact inherits the drift; a figure states things with more authority than the README it was cribbed from.
- Artifacts go to `agent/show/<slug>/`; commit once the user has approved the final version, or once a decision rests on it. Use `${TMPDIR:-/tmp}/show/<slug>/` instead when the user wants it throwaway, when there's no repo to keep it in, or when the repo is the wrong home for it.
- Anything opened in a browser ships both color schemes and a visible control to switch between them; the reader's system setting is the default, not a constraint. Look at both before presenting. `SVG-FIGURES.md` has the token and toggle mechanics.
- Look at your own render before presenting — Read the PNG, run the demo, open the page. Done means you have seen it explain the thing *and* it looks good; an ugly artifact obscures what it was meant to clarify.
- Present it opened (`claude-browser` where it exists, else `xdg-open`), with one line on what it shows and the absolute path.

## Heavy artifacts fork

A diagram, diff, or small demo is cheaper to produce here than to delegate. An artifact with a build loop — a manim video, a multi-section explainer, anything needing render–debug cycles — goes to a context-inheriting fork (invoke `mx:fork`), so the build noise stays out of this conversation. The directive: the artifact spec, its output path, and nothing else.
