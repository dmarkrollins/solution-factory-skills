# Choosing a workflow

Start from what you are trying to achieve. Each recipe lists the commands in
order and why that path fits.

## Quick chooser

| Goal | Path |
|---|---|
| Start a new project from nothing | `/ideate` → `/create-stories` → `/solution` |
| Add structure to an existing codebase | `/bootstrap` → `/create-stories` → `/solution` |
| Build one feature in a project already set up | `/create-stories` → `/solution` |
| Park an idea without losing focus | `/ideas add` → later `/ideas triage` → `/ideas plan` → `/create-stories --from-idea` |
| Clear a backlog of ready stories hands-off | `/solution epic <id>` or `/solution epic all` |
| Stay closely involved in each change | `/solution` (interactive) |
| Fix a small bug | `/ideas add` → `/ideas plan` → `/create-stories --from-idea` (usually one or two stories) |
| Tidy up overlapping decisions and constraints | `/solution consolidate` |

## New project (greenfield)

1. `/ideate` — answer questions about the problem, architecture and
   constraints. It pushes back on scope creep and stops when there is enough
   to build on.
2. `/create-stories` — describe the first epic. Foundation stories (models,
   schema, core) are sequenced first, then thin end-to-end feature slices.
3. `/solution` for the first story or two so you can steer early conventions,
   then `/solution epic <id>` once the pattern is set.

## Existing codebase (brownfield)

1. `/bootstrap` — three read-only agents scan the stack, architecture and
   boundaries. You get 5–15 inferred decisions and 3–8 constraints to review.
   **Correct anything wrong here** — every later story is checked against them.
2. `/create-stories` — describe the change you want. New stories are evaluated
   against the inferred decisions so they follow the patterns already in use.
3. `/solution` or `/solution epic <id>`.

If `.solution-factory/` already exists, `/bootstrap` offers to merge new
findings rather than overwrite.

## A single idea (lightweight backlog)

Use this when an idea shows up mid-task, or for small features and bugs that
do not deserve a design session.

1. `/ideas add fix the flaky retry logic in the uploader` — captured as
   `IDEA-NNN`. Works even before `/ideate` or `/bootstrap` has been run.
2. `/ideas triage` — walk through raw ideas: keep, discard or merge.
3. `/ideas plan IDEA-NNN` — a short interview, then the `technical-architect`
   agent drafts a technical approach: feasibility, what to build, what to
   leave out. Needs a scaffolded `.solution-factory/` (run `/ideate` or
   `/bootstrap` first).
4. `/create-stories --from-idea="IDEA-NNN"` — turns the plan into an epic with
   properly sized stories, skipping the interview.

An idea moves through: `raw → triaged → planning → planned → promoted`.

## Interactive or autonomous?

Both run the identical gates: YAGNI filter, complexity re-check, two-tier
testing, code review, security review, documentation cleanup, discovery
tracking. The difference is who answers the questions.

| | Interactive (`/solution`, `next`, `start`) | Autonomous (`/solution epic`) |
|---|---|---|
| Plan approval | You approve each plan | Auto-approved, still written to `plan.md` |
| Unclear requirements | Asks you, one question at a time | Resolves from the code and acceptance criteria; stops and reports a blocker if it cannot |
| Finishing a story | You run `/solution complete <id>` | Done automatically |
| Merging | Follows `stories.automerge` | Merges automatically; add `--review-merges` to approve each merge |
| Human input | Throughout | One yes/no at the start |

**Choose interactive when** requirements are fuzzy, the story sets a pattern
others will copy, or you want to learn how the tool behaves.

**Choose autonomous when** stories came out of `/create-stories` well-formed
and you trust your test suite to catch mistakes.

A sensible middle ground: `/solution epic <id> --review-merges`. Everything
runs unattended, but nothing lands on your merge branch without a yes.

## Running stories at the same time

`/solution epic` can work several stories at once when
`epic_run.max_concurrent` is above 1 (default 3).

- Each in-flight story gets its own git worktree under `.sf-worktrees/`.
- Two stories run together only if the files they declared (their `outputs`,
  written by `/create-stories`) do not overlap. A story with no declared
  outputs runs alone.
- Merges still happen one at a time, and the full test suite runs on each
  story's branch right before it merges.
- If a story is blocked it is set aside; everything that does not depend on
  it keeps going.

Use `--sequential` for a single run, or set `epic_run.max_concurrent` to `1`,
when your tests cannot run in two checkouts at once (shared database, fixed
ports) or you want a simpler transcript.

If worktrees need setup — installing packages, copying a `.env` — set
`epic_run.worktree_setup` (see [configuration.md](configuration.md)).

## Stopping and resuming

- Press Escape, then `/solution stop` — saves the run state and commits it.
  Safe to close Claude.
- `/solution next` (or `/solution resume`) — picks up the paused epic run, or
  the in-progress story if there is no epic run.
- After an interrupted `/solution epic all`, `/solution next` finishes the
  epic that was running; run `/solution epic all` again to continue into the
  next epic.

## Adding work later

- **More stories for an epic in progress:** run `/create-stories` and describe
  the work. It detects that it belongs to an existing epic and inserts the
  stories at the right position.
- **A new epic:** run `/create-stories` again. Epics are capped at
  `stories.max_stories_per_epic` (default 10); bigger scope is split into
  sequential epics.
- **More context:** run `/ideate` again to add decisions for a new area.

## Getting the most out of it

- **Invest in Step 1.** Stories are checked against your decisions and
  constraints. Wrong or missing ones produce wrong plans.
- **Keep stories small.** The complexity threshold (default 3) is deliberately
  low. Small stories plan better, review better and fail cheaper.
- **Let discoveries flow back.** When a story uncovers a new constraint or
  decision, it is recorded and — if broadly relevant — promoted so later
  stories benefit.
- **Use a staging branch on shared codebases.** Set `stories.merge_branch` to
  `develop` (or similar) so autonomous merges never land directly on `main`.
- **Mind your token budget.** Scripts do the bookkeeping at zero token cost;
  scanning uses the smallest model. The biggest lever you control is story
  size and how many stories run concurrently.
