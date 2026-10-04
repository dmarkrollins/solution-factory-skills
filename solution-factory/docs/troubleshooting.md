# Troubleshooting

## Setup

**"No `.solution-factory/`" or a command tells me to run `/ideate`**
`/create-stories`, `/solution` and `/ideas plan` need the project scaffold.
Run `/ideate` (new project) or `/bootstrap` (existing code) first.
`/ideas add` is the exception — it works anywhere.

**Commands fail with "python3: command not found"**
The helper scripts need Python 3 available as `python3`. Install Python 3 and
make sure `python3 --version` works in the same terminal Claude Code runs in.

**Commands fail with "not a git repository"**
Solution Factory uses git for branches and merges. Run `git init` and make an
initial commit, then try again.

**`/bootstrap` produced a wrong decision or missed one**
Tell it during the review step; it updates the files and regenerates the
summaries. Later, edit the file under `.solution-factory/decisions/` or
`constraints/` directly.

**`/bootstrap` says the codebase is empty**
Use `/ideate` instead — bootstrap needs code to analyze.

## Stories

**"All stories completed or blocked" but work remains**
A story is ready only when all its dependencies are done. Run
`/solution status` and `/solution list` to see what is waiting on what. A
blocked or half-finished story upstream is the usual cause.

**A story keeps getting split**
Its complexity is above `complexity.threshold`. This is by design — smaller
stories succeed more often. If the splits are genuinely too small to be
useful, raise the threshold to 4 in `config.json`.

**Most stories score at the maximum**
That usually means over-scoring, not hard work. Ask `/create-stories` to
re-examine the Implementation and Change Surface scores; a healthy epic has a
mix of 1s, 2s and a few 3s.

**I need to change a story after it was created**
Before it starts: edit its JSON under `epics/<epic>/stories/backlog/`, or run
`/create-stories` and describe the change. After it is done:
`/solution rollback <id>` reopens it.

**I want to add stories to an epic already under way**
Run `/create-stories` and describe the work; it inserts into the existing
epic at the right position.

## Working a story

**The plan includes things I did not ask for, or leaves things out**
Reject the plan at the approval step and say what to change. It revises and
shows it again. Nothing is coded before you approve.

**Tests fail and the story will not complete**
That is the gate working. Fix the failures (or ask Claude to), then run
`/solution complete <id>` again. A story is never merged with failing tests.

**Code review or security review says "needs rework"**
The findings are addressed, tests re-run and the review repeated until it
passes. In interactive mode you see the findings; in an epic run the worker
is sent back automatically.

**I closed Claude in the middle of a story**
Run `/solution resume`. It reloads the story, reads `plan.md` to see which
steps are checked off, and continues.

**I want to undo a completed story**
`/solution rollback <id>` reopens the story. It does not revert the merged
code — use git for that.

## Epic runs

**The run stopped part-way**
A story was blocked: contradictory acceptance criteria, behavior it could not
determine, complexity above the threshold, or tests it could not get green.
The reason is in the summary and in the story's `local.md`. Resolve it —
often by working that one story interactively with `/solution start <id>` —
then `/solution next` to continue.

**It asked me a question in the middle of an autonomous run**
An epic run has one confirmation at the start, plus one per merge when you
pass `--review-merges`. Otherwise it only stops for a real blocker. If
borderline discoveries are prompting, check that
`stories.auto_accept_recommendations` is `true`.

**Stories run one at a time even though `max_concurrent` is 3**
Stories run together only when their declared `outputs` share no file.
Common causes:
- stories have no `outputs` declared (they then run alone);
- every story touches the same file, such as a lockfile, route table or
  `CLAUDE.md` — add those to `epic_run.shared_paths`;
- you passed `--sequential` or `--review-merges`, which both force one at a
  time.

**Tests fail in worktrees but pass in the main checkout**
A fresh worktree has no installed packages and no untracked files. Set
`epic_run.worktree_setup`, for example `"npm ci && cp ../../.env ."`. If tests
need an exclusive resource (a shared database, a fixed port), set
`epic_run.max_concurrent` to `1`.

**`.sf-worktrees/` was left behind after an interrupted run**
Resume with `/solution next`; finished branches in the slots are picked up.
To clean up by hand: `git worktree list`, then `git worktree remove` each
slot and `git worktree prune`.

**Merge conflicts during a concurrent run**
The worker is sent back to merge the latest merge branch into its feature
branch and fix the conflict. Repeated conflicts mean stories overlap more
than their declared `outputs` say — run that epic with `--sequential`.

**Merges are landing on `main` and I did not want that**
Set `stories.merge_branch` to your staging branch and use `--review-merges`.

## Context quality

**Too many decisions and constraints, many overlapping**
Run `/solution consolidate`. It proposes merge groups for you to approve.
To slow the growth, raise `relevance.auto_create`.

**Claude ignores a rule I care about**
Make sure it exists as a constraint under `.solution-factory/constraints/`.
Rules that live only in your head or in chat are not checked.

## Still stuck?

Add `help` to any command for its full reference, or ask `/guide` — for
example "why is my epic running sequentially?".
