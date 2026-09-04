# What the orchestrator types for ONE feature on a remote worker host, per the
# dispatch skill's Mechanics as they stand. Host agent-hl@pc, repo `workspace`,
# feature `architecture-map`, ticket 03-shape-curated-model-layout, model opus.
# Judgment steps (wave planning, reading the worker's exit, merging) are marked
# JUDGE and kept; everything else is the orchestrator assembling names and
# sequencing commands.

# ---- setup, once per run ---------------------------------------------------
worker-hosts                                              # JUDGE: pick a host
worker-hosts agent-hl@pc                                  # JUDGE: isolated → bypassPermissions
ssh agent-hl@pc claude plugin marketplace update MaxWolf-01   # only if no other dispatcher's workers are live there (you read that off the host list)
ssh agent-hl@pc claude plugin update mx@MaxWolf-01

# once per repo
ssh agent-hl@pc git init --bare repos/dispatch/workspace.git
git remote add agent-hl-pc agent-hl@pc:repos/dispatch/workspace.git

# feature branch, held in its own worktree
git worktree add ../workspace-architecture-map -b architecture-map
cd ../workspace-architecture-map
git push agent-hl-pc architecture-map

# scratch dir: this plugin version's ctl, runner, worker prompt
ssh agent-hl@pc mkdir -p /tmp/dispatch-workspace-architecture-map
scp ~/.claude-helferline/plugins/cache/MaxWolf-01/mx/0.1.20/skills/dispatch/dispatch-ctl agent-hl@pc:/tmp/dispatch-workspace-architecture-map/
scp ~/.claude-helferline/plugins/cache/MaxWolf-01/mx/0.1.20/skills/dispatch/run-worker.sh agent-hl@pc:/tmp/dispatch-workspace-architecture-map/
scp ~/.claude-helferline/plugins/cache/MaxWolf-01/mx/0.1.20/skills/dispatch/worker-prompt.md agent-hl@pc:/tmp/dispatch-workspace-architecture-map/

# ---- per ticket: claim and spawn --------------------------------------------
# JUDGE: frontier, file overlap, coherence → ticket 03 goes in this wave
sed -i 's/^status: open/status: claimed/' agent/tasks/architecture-map/03-shape-curated-model-layout.md
git commit -m "architecture-map: claim 03" -- agent/tasks/architecture-map/03-shape-curated-model-layout.md
git push agent-hl-pc architecture-map

# worktree + branch on the host: names assembled by hand, feature-namespaced
# because the bare repo and the sibling directory are shared across features
ssh agent-hl@pc git -C repos/dispatch/workspace.git worktree add ../workspace-architecture-map-03-shape-curated-model-layout -b ticket/architecture-map/03-shape-curated-model-layout architecture-map
# the project's setup target, in the worktree (nix develop -c make install where a flake.nix exists)
ssh agent-hl@pc make -C repos/dispatch/workspace-architecture-map-03-shape-curated-model-layout install

# worker prompt: the contract, concretized
cat > /tmp/prompt-03.md <<'P'
Load /mx:implement and work the ticket at agent/tasks/architecture-map/03-shape-curated-model-layout.md.
You own only this ticket and this worktree; the feature branch and other tickets belong to the orchestrator.
Your final act, once the implementation is committed and verified: set `status: done` in the ticket's frontmatter and commit.
P
scp /tmp/prompt-03.md agent-hl@pc:/tmp/dispatch-workspace-architecture-map/prompt-03.md

ssh agent-hl@pc DISPATCH_PERMISSION_MODE=bypassPermissions bash /tmp/dispatch-workspace-architecture-map/dispatch-ctl spawn \
    dispatch-workspace-architecture-map-03 \
    /home/agent-hl/repos/dispatch/workspace-architecture-map-03-shape-curated-model-layout \
    /tmp/dispatch-workspace-architecture-map/prompt-03.md \
    agent/tasks/architecture-map/03-shape-curated-model-layout.md \
    opus
# → spawned dispatch-workspace-architecture-map-03  channel=dispatch-workspace-architecture-map-03-1788500000
ssh -o ServerAliveInterval=15 -o ServerAliveCountMax=2 agent-hl@pc tmux wait-for dispatch-workspace-architecture-map-03-1788500000   # run_in_background

# ---- on exit: integrate ----------------------------------------------------
ssh agent-hl@pc bash /tmp/dispatch-workspace-architecture-map/dispatch-ctl probe
# → dispatch-workspace-architecture-map-03 exited  channel=…-1788500000  attempts=1 exit=0 status=done session=…
# not done? read /tmp/<channel>.status and /tmp/<channel>.log there (channel from the probe line)
git fetch agent-hl-pc ticket/architecture-map/03-shape-curated-model-layout:ticket/architecture-map/03-shape-curated-model-layout
git show ticket/architecture-map/03-shape-curated-model-layout:agent/tasks/architecture-map/03-shape-curated-model-layout.md | sed -n 's/^status: //p'   # JUDGE: done?

# review range: the merge-base MUST be read before merging (afterwards the tip
# is an ancestor of the feature branch and the range comes out empty)
base=$(git merge-base architecture-map ticket/architecture-map/03-shape-curated-model-layout)
tip=$(git rev-parse ticket/architecture-map/03-shape-curated-model-layout)

git merge --no-ff ticket/architecture-map/03-shape-curated-model-layout        # JUDGE: conflict → resume the worker with "the feature branch moved"
make check                                                                     # JUDGE: red → same

# landed: record the range, project the ticket's assumptions into notes, render, serve
sed -i "s|^diff: \[\(.*\)\]|diff: [\1, $base..$tip]|" agent/tasks/architecture-map/03-shape-curated-model-layout.md   # or insert `diff: [...]` if absent
# notes: every `- A<n> \`path:line\`: text` bullet → {"id": n, "path", "line", "text"}; every `Addressed: C1, C4` → resolved
#        (assembled by hand or by an inline python; a duplicate id must fail the render)
diffview "$PWD@$base..$tip" --notes agent/diffviews/architecture-map/03-shape-curated-model-layout.notes.json -o agent/diffviews/architecture-map/03-shape-curated-model-layout.html
diffview --serve agent/diffviews
uv run ~/.claude-helferline/plugins/cache/MaxWolf-01/mx/0.1.20/skills/dispatch/dashboard.py agent/tasks
# JUDGE: announce the landed slice: what works, how to exercise it

# ---- cleanup ----------------------------------------------------------------
ssh agent-hl@pc git -C repos/dispatch/workspace.git worktree remove ../workspace-architecture-map-03-shape-curated-model-layout
ssh agent-hl@pc git -C repos/dispatch/workspace.git branch -d ticket/architecture-map/03-shape-curated-model-layout
ssh agent-hl@pc bash /tmp/dispatch-workspace-architecture-map/dispatch-ctl cleanup dispatch-workspace-architecture-map-03
git branch -d ticket/architecture-map/03-shape-curated-model-layout
