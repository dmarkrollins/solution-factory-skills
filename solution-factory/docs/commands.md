# Command reference

Five commands make up the pipeline. Add `help` to any of them for the full
built-in reference.

```
/ideate or /bootstrap  →  /create-stories  →  /solution
                /ideas  →  /create-stories --from-idea
```

## /ideate — design a new project

| Command | What it does |
|---|---|
| `/ideate` | Start or resume ideation in the current directory |
| `/ideate <project-name>` | Start with the project name filled in |
| `/ideate help` | Show the reference |

A guided Q&A — one question at a time — covering the problem, architecture
and constraints. Writes decisions, constraints, requirements and architecture
docs, context capsules, `config.json` and `manifest.json`. If
`.solution-factory/` already exists it asks whether to add to it or start
fresh.

## /bootstrap — analyze an existing codebase

| Command | What it does |
|---|---|
| `/bootstrap` | Analyze the current directory |
| `/bootstrap --root=path` | Analyze a specific path |
| `/bootstrap help` | Show the reference |

Scans the code with three read-only agents, infers decisions and constraints,
and presents them for review. You can approve, correct a wrong inference, or
add something it missed. If `.solution-factory/` already exists it offers to
merge rather than overwrite.

## /ideas — a lightweight idea backlog

| Command | What it does |
|---|---|
| `/ideas` or `/ideas list` | List ideas. Add `--state raw` (or `triaged`, `planning`, `planned`, `promoted`, `discarded`) to filter |
| `/ideas add [text]` | Capture an idea. Asks one question if no text is given |
| `/ideas show <id>` | Show an idea in full, including its plan |
| `/ideas triage` | Review raw ideas one at a time: keep, discard or merge |
| `/ideas plan <id>` | Interview, then draft a technical approach into the idea's `plan.md` |
| `/ideas plan-check <id>` | Re-check a plan's format. Warns only, never blocks |
| `/ideas discard <id>` | Discard an idea |
| `/ideas help` | Show the reference |

`add` works in any project, even before `.solution-factory/` exists. `plan`
needs the full scaffold from `/ideate` or `/bootstrap`.

## /create-stories — break an epic into stories

| Command | What it does |
|---|---|
| `/create-stories` | Start a new epic interactively |
| `/create-stories --epic-title="title"` | Provide the epic title up front |
| `/create-stories --from-idea="IDEA-NNN"` | Promote a planned idea into an epic |
| `/create-stories help` | Show the reference |

Requires `.solution-factory/` (run `/ideate` or `/bootstrap` first). Drafts
vertically sliced stories, scores and splits them, declares the files each
will touch, orders them by dependency, and waits for your approval. You can
add, remove, split, merge or reorder before approving.

**Complexity scoring.** `complexity = 1 + points`, where points come from:

| Dimension | Points | Scale |
|---|---|---|
| Change surface | 0–3 | one file · one layer · one stack · cross-stack |
| Implementation | 0–3 | copy existing · familiar · new pattern · new architecture |
| Uncertainty | 0–2 | clear · minor unknowns · significant unknowns |
| Scope | 0–2 | 1–2 acceptance criteria · 3–4 · 5 or more |

A story scoring above `complexity.threshold` (default 3) is always split.

## /solution — implement stories

### One story at a time (interactive)

| Command | What it does |
|---|---|
| `/solution` or `/solution next` | Resume a paused epic run if there is one, otherwise start the next ready story |
| `/solution start <id>` | Start a specific story, e.g. `/solution start 03.002` |
| `/solution plan <id>` | Write or refine the plan only — no branch, no code |
| `/solution resume` | Resume a paused epic run, otherwise the in-progress story |
| `/solution complete <id>` | Validate, test, process discoveries, merge and close a story |
| `/solution rollback <id>` | Reopen a completed story as active |

### A whole epic (autonomous)

| Command | What it does |
|---|---|
| `/solution epic <id>` | Run every ready story in the epic after one confirmation |
| `/solution epic <id> --review-merges` | Same, but ask yes/no before each merge. Runs one story at a time |
| `/solution epic <id> --sequential` | Force one story at a time for this run |
| `/solution epic all` | Run every ready epic in order. Always merges automatically |
| `/solution stop` | Pause the active epic run and save its state |

### Seeing where things stand

| Command | What it does |
|---|---|
| `/solution status` | Progress across all epics |
| `/solution list [--status X]` | List stories, optionally filtered by status |
| `/solution consolidate` | Review decisions and constraints for overlap and merge duplicates. Always interactive |
| `/solution help` | Show the reference |

### What happens to each story

1. **Resolve and activate** — confirm dependencies are done, mark the story
   active.
2. **Plan** — explore the code, remove what is not needed (YAGNI), re-check
   complexity, ask about anything unclear, write `plan.md`. Interactive mode
   waits for your approval here.
3. **Implement** — on a `feature/<id>-<slug>` branch, with `plan.md` as the
   first commit, then small commits per step.
4. **Test** — tests scoped to the changed files, then the full suite. Both
   must pass.
5. **Code review** — an independent reviewer checks the change against the
   acceptance criteria, decisions and constraints.
6. **Security review** — skipped automatically when the change touches no
   attack surface.
7. **Documentation cleanup** — existing docs made stale by the change are
   updated. No new docs are generated unless a story asks for them.
8. **Complete** — discoveries are scored and promoted, the branch is merged
   with a merge commit, and the story moves to done.

## Asking for help

`/guide` answers questions about using and configuring Solution Factory. You
can also just ask in plain language — "how should I set up Solution Factory
for this repo?" — and Claude will use the guide.
