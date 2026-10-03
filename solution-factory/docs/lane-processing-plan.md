# Plan: concurrent story processing for `/solution epic`

Status: implemented. This is the original design record; see `concurrent-slot-processing.md` for how the built system works and how to migrate a lane-based implementation.
Reference: `lane epic processing.jpeg`, a lane-based design from another codebase. This plan adapts the concept; it does not port the code. The original static-lane version of this plan was replaced by dynamic scheduling after measuring a real project (see Evidence).

## Decisions

| Question | Decision |
|---|---|
| Source of the design | Reference only: adapt the concept and improve on it for this JSON-based solution-factory |
| Where each story's file list comes from | Declared in `/create-stories` as `outputs: {create, modify}`; a story without it runs alone |
| Scheduling | Dynamic: at each loop iteration start any ready story whose declared files don't overlap an in-flight story's, up to `max_concurrent`; a fresh `story-worker` per story |
| Full test suite (Tier 2) | Runs one story at a time in the merge queue, on the story branch after the latest merge branch is merged into it |
| When a story blocks | Quarantine that story and anything depending on it; every other story runs to completion |
| How it turns on | Automatically when `max_concurrent > 1`; `--sequential` forces the old behavior; `epic_run.max_concurrent` defaults to 3 |
| `epic all` | Kept: each epic runs concurrently within itself, one epic at a time |
| Existing backlogs without `outputs` | No backfill command; those stories run one at a time. Revisit after the pilot |

## Goal

Run stories that touch different files at the same time. Every existing safeguard stays: plan committed first, the YAGNI filter, independent code and security review, the full test suite (Tier 2) before every merge, discovery promotion, and the single pre-flight approval.

## Evidence

Measured on `app-meteor3-migration` (21 epics, 99 merged stories) from `sequence.json` and the merged story branches in git.

- **Dependency graphs are wide.** In 17 of 21 epics the critical path is 1–2 stories deep. Epic-13 has 7 stories with no dependencies between them; epic-16 has 8 of 10 at level 1; epic-07 has 7 of 8 behind one foundation story. Only epic-04 (critical path 5 of 7) is chain-shaped.
- **Independent stories rarely share files.** Across every pair of dependency-independent stories, overlaps come from two sources: coordination files almost every story touches (`.meteor/versions`, `.meteor/packages`, `CLAUDE.md`, `package.js`), and a few genuine hot files (`utilityMethods.js` in epic-13, `tournament.server.tests.js` in epic-17). Elsewhere overlap is zero.
- **Diffs are small.** Median story changes 2 files (p90: 10), so declaring `outputs` at creation time is a tractable prediction.
- **Per-story time.** Median activate→merge is 22 minutes. A clean 8-story epic is about 3 hours sequential; with 3 slots and this dependency shape, roughly 1–1.5 hours.
- **Tests are cheap and concurrency-safe there.** `npm test` finishes in under a minute and auto-allocates a free port. The merge-queue Tier 2 is not a bottleneck for that project.
- **No story declares `outputs` today**, so the benefit starts with newly created epics.

Conclusion: concurrency across file-disjoint stories is the right lever for this workload. No cheaper approach gives a comparable speedup; per-story overhead cuts (risk-tiering the security review, cheaper docs cleanup) stack with it but don't replace it.

## Where the time savings come from

Today every step of every story runs one after another. With concurrent slots, the worker's planning, implementation and Tier 1 tests run in parallel across stories, and so do the reviews. Only the per-story merge step runs one at a time: bring in the latest merge branch, run Tier 2, merge, complete.

## Design

### 1. Single writer, so no locks

The main-thread orchestrator is the only thing that writes to the `.solution-factory/` ledger (`sequence.json`, epic JSON, story folders) and the only thing that merges. It does all of this from the main project root, which stays on `MERGE_BRANCH` for the whole run.

`story_activator.py`, `story_completer.py` and `generate_sequence.update_status` never run inside a worktree. The one exception is each story's own `plan.md` and `local.md`, which its worker writes on its feature branch. That keeps `plan.md` as the first commit on the branch.

This removes both locks from the reference design.

### 2. Dynamic scheduling

At every loop iteration the orchestrator computes the set of startable stories:

- **ready**: status `backlog` and every dependency `done` (the existing `story_resolver` rule);
- **disjoint**: the story's scheduling files don't intersect any in-flight story's scheduling files;
- **a slot is free**: fewer than `max_concurrent` stories are in flight.

Scheduling files are `outputs.create ∪ outputs.modify` minus `epic_run.shared_paths`. A story with no `outputs` is treated as touching everything: it starts only when nothing is in flight, and nothing starts while it runs. Startable stories are taken in `sequence.json` order.

There is no lane planner, no lane numbering, no reduction step and no cross-lane gate: a dependency on an unmerged story is just "not ready yet". This replaces the reference design's static partition, which existed to serve a long-lived agent per lane that we don't have. On the measured epics a static partition capped at 3 lanes would also pack 7 independent stories into 3 fixed queues, letting one slow story hold its queue-mates while other slots sit free.

### 3. Shared paths

`epic_run.shared_paths` is a list of glob patterns excluded from the disjointness check. Default: `[".solution-factory/**"]`. Projects add their coordination files (for the measured project: `.meteor/versions`, `.meteor/packages`, `CLAUDE.md`). Without this list, files that every story touches would make every pair "overlapping" and serialize the epic. Conflicts in shared paths are real and are caught at merge like any other conflict (design item 7).

### 4. When concurrency is used

Concurrent mode is used unless `--sequential` or `--review-merges` was passed, or `max_concurrent` is 1. The pre-flight gate shows, for each story: its scheduling files, which stories it waits on, and whether it lacks `outputs` (and so will run alone). The gate makes clear when a run will be effectively sequential and why (for example "4 of 6 stories lack outputs").

### 5. Worktree slots

- `max_concurrent` worktrees at `.sf-worktrees/slot-N`, created on first use, excluded from git through `.git/info/exclude`, and reused across stories within the run.
- Each story gets its own `feature/[ID]-[slug]` branch, checked out in the slot it was assigned. That keeps today's branch names and the existing unmerged-branch check at loop start (EPIC-3 step 0).
- Tests always run from the slot root, so test runners never pick up other slots.
- `epic_run.worktree_setup` (for example `npm ci && cp ../../.env .`) runs once per slot when it's created. If it's missing when a project needs it, Tier 1 fails on the first command and the story blocks; no separate detection is built.

### 6. Order of steps for each story

1. **Activate.** In the main root, the orchestrator activates the story and commits. Activations are done one at a time.
2. **Branch.** The story's feature branch is cut in a free slot from the current `MERGE_BRANCH`, so it includes the activation commit and every earlier merge.
3. **Implement.** A fresh `story-worker` runs in the background in new `slot` mode. It skips Phases 1–2, runs Phases 3–4 plus Tier 1 only, and works inside the slot.
4. **Review.** The same reviewers as today (`code-reviewer` and `security-engineer` in parallel, plus `test-engineer` when the story is high-risk) are pointed at the slot path. The main root never checks out a feature branch. The rework budget stays at 3.
5. **Merge queue, one story at a time.**
   - In the slot, merge in the latest `MERGE_BRANCH`, then run Tier 2.
   - Run `validate` and `check_plan_complete`.
   - Merge with `merge --no-ff` into `MERGE_BRANCH`.
   - Run the existing completion logic (EPIC-4c) in the main root: discoveries, `story_completer`, artifact commit, epic-complete check.
   - Free the slot and go back to scheduling.
6. **Conflict or Tier 2 failure.** Abort the merge and send the story back to its worker in rework mode, with the conflicting files or the test failures. These attempts count against the same rework budget of 3 that review findings use; when it runs out, the story is quarantined.

Progress is reported one compact line per story, prefixed with the slot: `▶ S2 01.004 [Title] … DONE`.

### 7. Quarantine

When a story blocks (worker `BLOCKED`, or rework budget exhausted), it stays `active` and its slot is freed. Stories that depend on it never become ready, so they are skipped naturally. Every other story runs to completion. The final summary lists each blocked story and what it needs. Nothing extra is persisted: a blocked story stays `active`, so `/solution next` retries it on resume.

With `epic all`, epics still run one at a time. The next epic starts only after the current epic has no startable and no in-flight stories and nothing quarantined; otherwise the run ends at the final summary (EPIC-5).

### 8. State and resume

The run block gains one field, `mode: concurrent|sequential`, so a `--sequential` run resumes as sequential. `current_story` is a single value and can't represent several stories in progress, so concurrent mode doesn't use it. Resume works it out:

- in-flight stories are the ones marked `active` in `sequence.json`;
- each story's slot is found by its branch name through `git worktree list`; an active story with no slot gets a fresh one and its worker is spawned in `resume` mode.

A new safety check at loop start also finishes completion for any active story whose branch has already merged. Slots are removed at the end of a run, but branches of blocked stories are kept.

### 9. Concurrent discoveries

Two workers exploring the same area may log a similar decision in their `local.md`. The consolidation check in EPIC-4c (`action: amend`) already handles that; no change needed, noted so it isn't mistaken for a bug during the pilot.

## Changes to `/create-stories`

- Steps 4a/4b fill in `outputs: {create: [...], modify: [...]}` per story: repo-relative paths, test files included. The complexity scoring already estimates change surface, so this is the same reasoning written down.
- The Step 6 summary flags **hot files**: when several stories declare the same `modify` file, list the file and the stories. Those stories can never run concurrently, whatever the scheduler does; the user can split by file instead of by handler, or accept that they serialize. Measured example: epic-13's `utilityMethods.js`, edited by 6 of 7 stories. No new script, just a line in the summary.

## Build order

1. **Story schema.** `outputs: {create:[], modify:[]}` in `story_templates.py` (currently an untyped list), a shape check in `validate_stories.py`, and `/create-stories` steps 4a/4b filling it in plus the hot-file line in Step 6.
2. **Config.** `epic_run: {max_concurrent: 3, shared_paths: [".solution-factory/**"], worktree_setup: null}` in `config_loader.py`, plus the matching entries in `pipeline-help.md`.
3. **`schedule_stories.py`** with unit tests: given an epic, the in-flight set and config, return the startable stories in sequence order, each with its scheduling files and the reason any ready story was held (overlap with which story, or missing outputs). Also produces the pre-flight table.
4. **`epic_run_manager.py`:** the `mode` field.
5. **`story-worker.md`:** the new `slot` mode (worktree as working directory, Tier 1 only, no ledger writes) and a conflict-rework variant that is allowed to merge `MERGE_BRANCH` into its own branch.
6. **`solution/skill.md`:**
   - new sections covering scheduling, the pre-flight table, the concurrent loop, the merge queue, quarantine and resume;
   - updating the "Sequential only" rule in Epic-runner rules;
   - help text.
7. **Pilot** on a real epic with `max_concurrent: 2`, comparing wall-clock time against a previous sequential run. Watch the merge queue: if Tier 2 there becomes the bottleneck, hand the test run to a background `test-engineer` and only serialize the `git merge` + completion.

Sequential mode (and `--review-merges`) stays exactly as it is today, including the worker's own Tier 2 run and the conditional full-suite backstop in EPIC-4c.

## Cut from the reference design (YAGNI)

| Reference | Why it's cut |
|---|---|
| Static lane partition (`lane_planner.py`, union-find, lane numbering, reduction to `max_lanes`, cross-lane gates) | Only needed for a long-lived agent per lane; dynamic scheduling is simpler and packs slots better |
| Long-lived `incremental-developer` per lane | Fresh worker per story keeps context clean and matches the existing worker contract |
| `.sf.lock` and `.sf-exclusive.lock` flocks | A single writer, plus Tier 2 running one story at a time in the merge queue, covers both |
| Per-lane persisted state (`.sf-lane.json`, lane statuses) | Worked out from `sequence.json` and `git worktree list` |
| `outputs_reconciler.py` auto-editing declared outputs | Merge conflicts already catch under-declared outputs; add it later only if that happens often |
| `auth_interrupt.py` failure classifier | The existing rule of showing a rejected spawn verbatim already covers this |
| Separate conflict-event counter | Conflicts and Tier 2 failures share the existing rework budget of 3 |
| Staggered fan-out, running epics in parallel | Low value at 3 slots |

## Cut from our own additions (YAGNI audit)

| Addition | Why it's cut |
|---|---|
| `blocked: [ids]` in the run block and a `block` command | Nothing reads them: the summary is printed in the same session, and blocked stories stay `active`, so resume retries them anyway |
| Separate retry budget of 2 for merge conflicts and Tier 2 failures | The existing rework budget of 3 covers them |
| Pre-flight warning that looks for dependency files when `worktree_setup` is unset | A missing setup makes Tier 1 fail on the first command, which gives the same signal |
| `/create-stories outputs <epic-id>` backfill command | The benefit starts with new epics; old stories run alone. Revisit if the pilot shows old backlogs are worth unlocking |
| All-or-nothing lane eligibility | Dynamic scheduling gives partial concurrency without it |

Kept after the audit: concurrency during `epic all`, since that is the main way autonomous runs are started; `shared_paths`, which the measured data showed is required.

## Improvements over the reference

- **Dynamic scheduling instead of static lanes.** Better slot packing on wide, shallow epics, and less code.
- **A fresh worker per story instead of one long-lived lane agent.**
- **Tier 2 runs on the combined result.** It catches breakage between concurrently-built stories that separate file ownership can't see.
- **No locks by design.** One writer means nothing to coordinate.
- **No deadlock analysis needed.** Readiness is the existing dependency rule; there are no lane-level waits.
- **Outputs declared up front and reviewable**, with hot files flagged at story-creation time.

## Risks to check during the pilot

- **Merge-queue bottleneck.** Tier 2 already runs once per story today, so the cost moves rather than grows, but a long suite limits the speedup. Cheap on the measured project.
- **Tier 1 collisions.** If a project's changed-file tests start servers on a fixed port, parallel Tier 1 runs can clash. The worker will be told to keep Tier 1 to unit tests, and the pre-flight gate notes `worktree_setup`.
- **Under-declared outputs.** Caught as merge conflicts and reworked; if frequent, revisit the reconciler.
- **Rate limits** with 3 workers and their reviewers running at once.
- **Stale capsules.** Running workers won't see capsules regenerated after another story's discoveries until the next story. Acceptable.
