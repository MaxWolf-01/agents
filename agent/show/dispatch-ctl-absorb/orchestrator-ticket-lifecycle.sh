# What the orchestrator types for ONE feature on a remote worker host, with the
# host's mechanics in dispatch-ctl and the orchestrator's in dispatch.
# Host agent-hl@pc, repo `workspace`, feature `architecture-map`, ticket
# 03-shape-curated-model-layout, model opus. Judgment steps (wave planning,
# reading the worker's exit, merging) are marked JUDGE and are all that is left
# besides the worker prompt.

# ---- setup, once per run ---------------------------------------------------
worker-hosts                                              # JUDGE: pick a host
worker-hosts agent-hl@pc                                  # JUDGE: isolated → bypassPermissions

# feature branch, held in its own worktree
git worktree add ../workspace-architecture-map -b architecture-map
cd ../workspace-architecture-map

# remote + scratch dir + bare repo + plugin update + first push of the feature branch
bash ~/.claude-helferline/plugins/cache/MaxWolf-01/mx/0.1.21/skills/dispatch/dispatch setup agent-hl@pc workspace
# → initialised /tmp/dispatch-workspace-architecture-map  mx=0.1.21  git=/home/agent-hl/repos/dispatch/workspace.git  worktrees=/home/agent-hl/repos/dispatch
# → remote=agent-hl-pc  scratch=/tmp/dispatch-workspace-architecture-map  ctl='ssh agent-hl@pc bash /tmp/dispatch-workspace-architecture-map/dispatch-ctl'

# ---- per ticket: claim and spawn --------------------------------------------
# JUDGE: frontier, file overlap, coherence → ticket 03 goes in this wave
sed -i 's/^status: open/status: claimed/' agent/tasks/architecture-map/03-shape-curated-model-layout.md
git commit -m "architecture-map: claim 03" -- agent/tasks/architecture-map/03-shape-curated-model-layout.md
git push agent-hl-pc architecture-map

# worker prompt: the contract, concretized
cat > /tmp/prompt-03.md <<'P'
Load /mx:implement and work the ticket at agent/tasks/architecture-map/03-shape-curated-model-layout.md.
You own only this ticket and this worktree; the feature branch and other tickets belong to the orchestrator.
Your final act, once the implementation is committed and verified: set `status: done` in the ticket's frontmatter and commit.
P
scp /tmp/prompt-03.md agent-hl@pc:/tmp/dispatch-workspace-architecture-map/prompt-03.md

# worktree, branch, setup target, session: all derived from 03-shape-curated-model-layout
ssh agent-hl@pc DISPATCH_PERMISSION_MODE=bypassPermissions bash /tmp/dispatch-workspace-architecture-map/dispatch-ctl spawn 03-shape-curated-model-layout opus
# → + git -C /home/agent-hl/repos/dispatch/workspace.git worktree add /home/agent-hl/repos/dispatch/workspace-architecture-map-03-shape-curated-model-layout -b ticket/architecture-map/03-shape-curated-model-layout architecture-map
# → + (cd /home/agent-hl/repos/dispatch/workspace-architecture-map-03-shape-curated-model-layout && make install)  > /tmp/dispatch-workspace-architecture-map-03.install.log
# → spawned dispatch-workspace-architecture-map-03  channel=dispatch-workspace-architecture-map-03-1788500000
ssh -o ServerAliveInterval=15 -o ServerAliveCountMax=2 agent-hl@pc tmux wait-for dispatch-workspace-architecture-map-03-1788500000   # run_in_background

# ---- on exit: integrate ----------------------------------------------------
ssh agent-hl@pc bash /tmp/dispatch-workspace-architecture-map/dispatch-ctl probe
# → dispatch-workspace-architecture-map-03 exited  channel=…-1788500000  attempts=1 exit=0 status=done session=…
ssh agent-hl@pc bash /tmp/dispatch-workspace-architecture-map/dispatch-ctl log 03-shape-curated-model-layout   # not done? status line + worklog tail, no channel lookup
git fetch agent-hl-pc ticket/architecture-map/03-shape-curated-model-layout:ticket/architecture-map/03-shape-curated-model-layout
git show ticket/architecture-map/03-shape-curated-model-layout:agent/tasks/architecture-map/03-shape-curated-model-layout.md | sed -n 's/^status: //p'   # JUDGE: done?

git merge --no-ff ticket/architecture-map/03-shape-curated-model-layout        # JUDGE: conflict → resume the worker with "the feature branch moved"
make check                                                                     # JUDGE: red → same

# landed: range (found from the merge commit, so the order no longer matters) committed to the ticket,
# notes projected from the ticket, page rendered and served, board re-rendered
bash ~/.claude-helferline/plugins/cache/MaxWolf-01/mx/0.1.21/skills/dispatch/dispatch review 03-shape-curated-model-layout
# JUDGE: announce the landed slice: what works, how to exercise it

# ---- cleanup ----------------------------------------------------------------
ssh agent-hl@pc bash /tmp/dispatch-workspace-architecture-map/dispatch-ctl cleanup 03-shape-curated-model-layout   # pane, manifest, worktree, branch
git branch -d ticket/architecture-map/03-shape-curated-model-layout
