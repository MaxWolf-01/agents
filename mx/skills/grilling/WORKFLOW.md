# Grilling in the mx workflow

In a repo the mx workflow runs in, the rounds of [`SKILL.md`](SKILL.md) are turns on the session page, and the design they settle lives in a ticket.

## The round

A round is one turn on [the session page](../session-page/RULES.md): the design as it stands and the frontier's open questions. Each question is a question of the round's turn record, in the shape [the session page's rules](../session-page/RULES.md) give it (The turn record), and the intent the questions lean to is the turn record's Questions there.

For a blind test, write the pairs file `blind-test --help` describes into the ticket's show directory, render it, and ask the question as a blind one ([the session page's rules](../session-page/RULES.md), Questions), so the page holds your pick; leave the pick out where you have none.

## The ticket

In a repo, the design lives in a ticket from the first round that has a design to write, in the shape `/mx:tracker` gives the body; read [DESIGN.md](DESIGN.md) as the round writes its design sections, since it is how each one is written; user stories grow from round one, since that is where misunderstandings show. A ticket the conversation started from is the one that grows, and where it started from none, `tracker new` files it: grilling adds the sections the design fills, and never a second file. Rewrite it at the end of each round (skip a round when you must clarify first or the picture is mid-flip), link it from the round's turn record, whose Details say what this round moved in each section it touched, so the user reads the round's changes rather than the whole document, and commit the round's state when the answers arrive, in the agent repo where ticket files are written (`/mx:tracker`), with no branch of its own. The brief is the one section those Details quote, since the user corrects your reading of the intent by seeing it. The first round that writes it quotes it whole. A round whose answers changed it quotes it as a before and after, against the brief as a round last showed it: each dropped sentence struck through (`~~like this~~`), each new one beside it. A round that leaves it alone says nothing of it. The ticket changes only through a round the user is in: a research finding or a prototype verdict is proposed in a round before it lands in the file.

A round's figure is built by a subagent or a fork (`/mx:show`), an artifact of the ticket, committed in the round's commit beside it (`/mx:show`'s `WORKFLOW.md`, Where it goes); the ticket's board row lists it. The round's turn record links each figure the round drew or moved, and its Details leave to the figure what the figure shows.

## Facts and decisions

A `/mx:prototype` detour that cannot run in this session is filed as a child ticket the prototype answers.

## Fog and scope

Fog lives in the ticket's Fog section. A question that can be stated is a child ticket, even while it is blocked. A part dropped as past the brief gets one line in Out of scope giving the reason.

## The frontier empties

When it empties, bring the ticket current; one that several sessions wrote is read whole once first, because each session saw only its part and the parts can disagree. Then cut it into child tickets (`/mx:tracker`, SLICING.md), or build it as it stands when it is one slice. A question the design does not rest on, one that is naturally its own work, leaves as a child ticket so the rest can be cut; one the design rests on holds the cut, and so does a shape the slices would consume (SLICING.md).

A mark is stripped when the user rules on it, in whichever session holds the ticket; the ruling on what that ticket built shows them the unruled ones that change what they asked for (`/mx:dispatch`).

## Across sessions

Nobody decides up front whether a grilling fits one session; the frontier either drains or it doesn't. When a session ends with questions still open, they leave the conversation as child tickets carrying `needs-user`, filed `open` since the user asked for the answer by leaving the question standing (`/mx:tracker`): questions that share their context go in one ticket, sized to one session of grilling. Such a ticket carries the questions with their options as the last round put them (the recommendation and its argument too, when the round had one) and names the sections its answers may rewrite; like any ticket it gets a priority, a size, a short name and a brief, the priority from how soon the user wants what the answer unblocks. The parent ticket's `(open → Qn)` marks become `(open → <slug>)`, and `(fog)` stays in Fog.

A fresh session reads the ticket top-down: Brief, the marks (in Decisions and wherever else they sit), Fog, plus its open child tickets; the middle sections when one of them touches them. It claims a child ticket per `/mx:tracker`, reads its Comments first (the answer, or the user's instinct about it, may already sit there), and grills it as a round like any other. The answer lands on the parent ticket as the user gave it (their reason when they gave one, none invented), each call marked `(you, <slug>)`, and the reasoning in the child ticket's Comments; the sections it named are rewritten in the same session.
