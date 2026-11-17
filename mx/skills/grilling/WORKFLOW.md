# Grilling in the mx workflow

## The ticket

In a repo, the design lives in a ticket from the first round that has a design to write, in the shape `/mx:tracker` gives the body; read [DESIGN.md](DESIGN.md) as the round writes its design sections, since it is how each one is written. A ticket the conversation started from is the one that grows, and where it started from none, `tracker new` files it: grilling adds the sections the design fills, and never a second file. Rewrite it at the end of each round, link it from the round's turn record, whose Details say what this round moved in each section it touched, so the user reads the round's changes rather than the whole document, and commit the round's state when the answers arrive (`/mx:tracker`, The tree). The brief is the one section those Details quote, since the user corrects your reading of the intent by seeing it. The first round that writes it quotes it whole. A round whose answers changed it quotes it as a before and after, against the brief as a round last showed it: each dropped sentence struck through (`~~like this~~`), each new one beside it. The ticket changes only through a round the user is in: a research finding or a prototype verdict is proposed in a round before it lands in the file.

A call mark stays in the ticket until the user rules on it, in whichever session holds the ticket, and is stripped then; the ruling on what that ticket built shows them the unruled ones that change what they asked for (`/mx:dispatch`).

When the frontier empties, bring the ticket current. Then cut it into child tickets (`/mx:tracker`, SLICING.md).

## Across sessions

Nobody decides up front whether a grilling fits one session; the frontier either drains or it doesn't. When a session ends with questions still open, they leave the conversation as child tickets carrying `needs-user`, filed `open` since the user asked for the answer by leaving the question standing (`/mx:tracker`): questions that share their context go in one ticket, sized to one session of grilling. Such a ticket carries the questions with their options as the last round put them (the recommendation and its argument too, when the round had one) and names the sections its answers may rewrite; like any ticket it gets a priority, a size, a short name and a brief, the priority from how soon the user wants what the answer unblocks. The parent ticket's `(open → Qn)` marks become `(open → <slug>)`, and `(fog)` stays in Fog.

A fresh session claims a child ticket per `/mx:tracker` and grills it as a round like any other. The answer lands on the parent ticket as the user gave it (their reason when they gave one, none invented), each call marked `(you, <slug>)`, and the reasoning in the child ticket's Comments; the sections it named are rewritten in the same session.
