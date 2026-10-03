# Concurrent epic processing with opportunistic slots

This document explains how an autonomous epic run works several stories at the same time, why the design uses opportunistic slots instead of lanes, and how to move a lane-based implementation to slots.

It is written to be handed to Claude Code working in a different solution-factory codebase. It describes behavior and rules, not code. Names of scripts, files and config keys are the ones used in the reference implementation; treat them as vocabulary and map them onto whatever the target codebase already has (for example YAML story files and a single `sf.py` entry point instead of JSON files and separate scripts).

## 1. The idea in brief

An epic run has a fixed number of **slots**. A slot is a git worktree that holds one story at a time. Whenever a slot is free, the orchestrator asks one question: *which stories could start right now?* A story can start when:

1. it is **ready**: still in the backlog, with every dependency done;
2. it is **disjoint**: the files it declared it will touch don't overlap the files of any story currently in flight;
3. a **slot is free**.

Every story that passes is started, in backlog order, each with a fresh worker agent in its own slot. When a story finishes it goes through a one-at-a-time merge queue, its slot is freed, and the question is asked again.

Nothing is planned ahead. There is no partition of the epic, no assignment of stories to queues, and no lane-level state. The schedule is recomputed from the ledger and the in-flight set every time something changes, which is why it is called opportunistic.

## 2. History: from lanes to slots

### The lane design

The first design for concurrency was lane-based, and another solution-factory implementation still runs that way. In outline:

- A **lane** is a set of stories that share files. A planner reads every open story's declared outputs and groups stories with union-find, so that no two lanes ever touch the same file. Lanes are numbered, then merged smallest-first down to a configured maximum.
- Each lane gets a worktree and a lane branch, and **one long-lived developer agent** works the lane's stories in order.
- A dependency that crosses lanes becomes a **gate**: the waiting lane pauses until the providing story has merged, then merges the target branch into its own.
- Lane mode is **all or nothing**. It engages only when at least two lanes exist, every open story declares outputs, at least one declares a modified file, and there is no cross-lane dependency cycle. Otherwise the whole run falls back to sequential.
- Lane agents write the ledger and merge on their own, so two file locks coordinate them: a short one for ledger and git-index writes, and a long exclusive one for commands that need a singleton resource such as a port or a database.
- Supporting machinery: per-lane persisted status and a marker file in each worktree, a conflict resolver agent with two separate counters, an outputs reconciler, and staggered agent start-up.

### Why it was replaced

Before building it, the dependency graphs and merged branches of a real project were measured (21 epics, 99 merged stories). The findings:

- **Epics are wide and shallow.** In 17 of 21 epics the longest dependency chain was one or two stories. Several epics had seven or eight stories with no dependencies between them.
- **Independent stories rarely share files.** Overlap came almost entirely from a handful of coordination files that nearly every story touches (lockfiles, package manifests, the project instructions file) plus a few genuinely hot files.
- **Stories are small.** The median story changed 2 files, so predicting a story's files when it is written is realistic.

Against that workload, a static partition has three problems:

1. **It packs slots badly.** Reducing seven independent stories to three lanes puts them in three fixed queues. One slow story holds up its queue-mates while another lane sits idle.
2. **It serializes more than it needs to.** Union-find groups by *transitive* file sharing. If story A shares a file with B, and B shares a different file with C, all three land in one lane, even though A and C could run together. A check made at start time only looks at what is actually running.
3. **It is all or nothing.** One story without declared outputs sends the whole epic back to sequential. With slots, that one story runs alone and the rest still run together.

The partition only existed to serve the long-lived agent per lane. Once each story gets a fresh worker, there is nothing for a lane to own, and the planner, lane numbering, lane reduction, gates, eligibility rules and per-lane state all disappear. Making the orchestrator the only writer removes both locks.

What the lane design had that slots give up: a lane agent carries context from one related story to the next. The slot design deliberately trades that for a clean context per story and a simpler worker contract.

## 3. Vocabulary

| Term | Meaning |
|---|---|
| Orchestrator | The main agent thread that runs the epic. It schedules, spawns workers and reviewers, merges, and writes the ledger. |
| Worker | A fresh agent that implements exactly one story in one slot and returns `IMPLEMENTED` or `BLOCKED`. |
| Slot | A reusable git worktree (`.sf-worktrees/slot-N`). Holds one story's feature branch at a time; detached when free. |
| Main root | The original checkout. Stays on the merge branch for the whole run. |
| Merge branch | The branch stories merge into (`main` by default, configurable). |
| Ledger | The tracking files: the master sequence file, the epic file, and the story folders that move between backlog, active and done. |
| Outputs | A story's declared files: `create` (new) and `modify` (existing), repo-relative, test files included. |
| Scheduling files | A story's outputs minus shared paths. This is what the overlap check compares. |
| Shared paths | Glob patterns for coordination files every story touches. Ignored by the overlap check. |
| In flight | A story with a running worker or an unfinished review or merge. |
| Quarantine | A blocked story is set aside; the run continues without it. |
| Tier 1 / Tier 2 | Tests scoped to the changed files / the full suite. |

## 4. The rules that make it safe

These five rules are the design. Everything else is detail.

1. **Single writer.** Only the orchestrator writes the ledger, and only from the main root. Workers may write just their own story's plan and discovery notes, on their own feature branch. Because nothing else writes, no locks are needed.
2. **The main root never leaves the merge branch.** No feature branch is ever checked out there. All story work, review and testing happens in slots. Merges into the merge branch therefore need no checkout.
3. **Stories overlap in time only when their declared files don't overlap.** This is a prediction, not a guarantee, so rule 4 backs it up.
4. **One serial merge queue, with the full suite run on the integrated result.** Before a story merges, the latest merge branch is merged into its branch and the full suite runs there. Because the queue is strictly one story at a time, nothing can land between that test run and the merge, so what was tested is exactly what merges.
5. **A blocked story never stops the others.** It is quarantined, and only stories that depend on it are held back.

## 5. Inputs

### Declared outputs

Each story carries an `outputs` block with two lists, `create` and `modify`. They are written when stories are created, at the same point where complexity is scored, since both come from estimating the change surface. The story validator checks the shape (an object with only those two keys, lists of non-empty repo-relative path strings).

A wrong declaration is not fatal. An undeclared write shows up as a merge conflict or a full-suite failure in the merge queue and is reworked. The declaration is still only useful when it is honest.

### Shared paths

Files that almost every story touches would make every pair of stories "overlapping" and turn the whole epic sequential. Shared paths are glob patterns removed from each story's outputs before the overlap check. The default covers the solution-factory tracking tree; projects add their lockfiles, package manifests and similar. Conflicts in these files are still real, and are caught in the merge queue like any other.

The reference implementation uses simple glob matching in which `*` also crosses directory separators.

### Config

| Key | Default | Meaning |
|---|---|---|
| `epic_run.max_concurrent` | 3 | Number of slots. 1 means sequential. |
| `epic_run.shared_paths` | the tracking tree | Globs ignored by the overlap check. |
| `epic_run.worktree_setup` | none | Shell command run once in each new slot (dependency install, copying env files). A fresh worktree has none of that. |

Concurrent mode is used automatically when `max_concurrent` is above 1. A `--sequential` flag forces the one-at-a-time loop, and so does the per-merge review flag, because a human approving each merge makes the run serial anyway. The sequential loop is left exactly as it was.

## 6. The scheduler

The scheduler is a pure function: given the ledger, the config and the list of in-flight story ids, it returns which stories to start now and why each other story is being held. It has no memory between calls. That is what keeps it easy to test and makes resume trivial.

```
scheduling_files(story):
    files = (outputs.create + outputs.modify) with shared paths removed
    if the story declares no outputs, or nothing is left after removal:
        return EVERYTHING
    return files

schedule(epic, in_flight):
    claimed    = [(id, scheduling_files(id)) for id in in_flight]
    free_slots = max_concurrent - len(in_flight)

    for story in epic stories, in ledger order:
        skip unless status is backlog and it is not already in flight
        if any dependency is not done      -> hold: "waits for <deps>"
        if free_slots <= 0                 -> hold: "no free slot"
        if it overlaps any claimed entry   -> hold: names the file and the other story
        otherwise                          -> start it; add it to claimed; free_slots -= 1

    return startable, held, plus a row per open story for the pre-flight table
```

Points worth getting right:

- **EVERYTHING overlaps everything.** A story with no outputs starts only when nothing is in flight, and nothing else starts while it runs. In practice such a story tends to wait until the stories around it drain.
- **Claims accumulate within one call.** A story picked earlier in the same call counts as in flight for the stories after it, so two overlapping stories are never started together.
- **A held story doesn't block the ones behind it.** The loop keeps going down the list. This is the opportunistic part.
- **Dependency status is looked up globally**, because a story may depend on a story in an earlier epic.
- **The orchestrator always passes the in-flight list explicitly.** If it is omitted, the scheduler defaults to every story marked active, which is right for a first look at a resumed run but wrong mid-run, where a quarantined story is still marked active but is not running.
- **The order is deterministic** for a given ledger and in-flight set.

The hold reasons are returned as text so the orchestrator can show them.

## 7. Slots

- Created once before the first story: `max_concurrent` worktrees, each added **detached** at the merge branch. The worktree directory is added to the repository's local exclude file so it never shows up as untracked.
- The setup command runs once per new slot. If it fails, the run stops, since every slot would fail the same way.
- A slot is **assigned** by creating the story's feature branch in it, and **freed** by detaching it again. The worktree itself is reused for the next story.
- Each story still gets its own `feature/<id>-<slug>` branch, the same naming as sequential mode. There are no lane branches, and merges are per story.
- Tests always run from inside the slot.
- Slots are kept across epic boundaries in an all-epics run and removed at the end of the run. Branches of quarantined stories are kept so they can be picked up later.

## 8. The orchestration loop

```
            +-----------------------------------------------+
            |  0. backstops (repair anything half-finished) |
            +-----------------------+-----------------------+
                                    v
            +-----------------------------------------------+
     +----->|  1. schedule (ledger + in-flight list)        |
     |      +-----------------------+-----------------------+
     |                              v
     |      +-----------------------------------------------+
     |      |  2. start every startable story:              |
     |      |     activate + commit in the main root,       |
     |      |     cut the branch in a free slot,            |
     |      |     spawn a worker in the background          |
     |      +-----------------------+-----------------------+
     |                              v
     |      +-----------------------------------------------+
     |      |  3. wait for the next worker to finish        |
     |      +-----------------------+-----------------------+
     |                              v
     |      +-----------------------------------------------+
     |      |  4. BLOCKED -> quarantine, free the slot      |
     |      |     IMPLEMENTED -> review in the slot         |
     |      +-----------------------+-----------------------+
     |                              v
     |      +-----------------------------------------------+
     |      |  5. merge queue (strictly one at a time)      |
     |      +-----------------------+-----------------------+
     |                              |
     +------------------------------+
        exit when nothing is in flight and nothing is startable
```

Step by step:

**0. Backstops.** Run at the start of every pass so the loop heals itself after an interruption. See section 12.

**1. Schedule.** Call the scheduler with the current in-flight list.

**2. Start.** For each startable story, in order and one at a time: activate it in the main root, commit the activation on the merge branch, then create its feature branch in a free slot from the merge branch. Cutting the branch after the activation commit means the slot sees the story as active and already contains every earlier merge, including the story's dependencies. Then spawn all the new workers together so they run in the background at the same time.

**3. Wait.** When nothing is startable and something is in flight, wait for a worker to report. Don't poll.

**4. Handle a result**, one story at a time in arrival order. First a cheap check that the branch has commits and a clean tree. A blocked story is quarantined. An implemented story goes to review: the same independent reviewers as sequential mode, told to work from the slot path. A review that asks for changes sends the story back to a fresh worker in the same slot.

**5. Merge queue.** See section 10.

**6. Exit.** When nothing is in flight and nothing is startable, the epic is drained. Any story still held at that point is waiting on a quarantined story and is reported as not started.

## 9. The worker in slot mode

The worker is the same agent used for sequential runs, with a slot mode that changes five things:

1. **Works only inside the slot.** The slot path is its project root for every command. It never touches the main root or another slot.
2. **Skips resolving and activating the story.** The orchestrator already did both and created the branch. If the branch is missing or wrong, the worker reports blocked; it does not create branches.
3. **Stays off the ledger.** Inside the tracking tree it may write only its own story's plan and discovery notes. The plan is still the first commit on the branch.
4. **Stays inside its declared outputs.** If it truly needs another file, it writes a short note saying which file and why, so a later merge conflict can be explained.
5. **Runs Tier 1 only.** The full suite runs once, in the merge queue, on the integrated branch.

Everything else is unchanged: scope trimming, complexity re-check, incremental commits, discovery logging, no human gates, and stopping at a green branch without reviewing or merging.

The worker returns a short structured result (implemented or blocked, branch, commit count, test status, blocker text). A fresh worker is spawned for each story and for each rework cycle; workers are stopped as soon as their result is read and are never resumed.

There is one extra rework variant. When the merge queue hits a conflict, the worker is told which files conflict and is allowed to merge the merge branch into its own branch, resolve the conflict keeping both stories' intent, and re-test. It never merges in the other direction.

## 10. The merge queue

Strictly one story at a time. Never interleave two stories' steps.

1. **Update.** In the slot, merge the current merge branch into the story branch. On conflict: record the conflicting files, abort the merge, and send the story to a worker in conflict-rework mode.
2. **Full suite.** Run Tier 2 in the slot, in the foreground with a bounded timeout. This is the only full-suite run for the story, and it runs against the combined result, so it catches breakage between stories that were built at the same time. Failure sends the story back for rework with the failures as findings.
3. **Validate.** Run the usual completion checks (story complete, plan fully ticked) against the slot. Failure quarantines the story.
4. **Merge.** In the main root, merge the story branch with a merge commit. No checkout is needed.
5. **Free the slot** by detaching it, and take the story out of the in-flight list. Do this before the bookkeeping so the next schedule can use the slot. Keep the branch for now.
6. **Complete.** In the main root, on the merge branch: promote discoveries, mark the story done, commit the tracking files in one commit, run the epic-complete check. Then delete the story branch.

The branch is kept until step 6 finishes on purpose: a branch that is already merged but belongs to a story still marked active is how the backstop spots a completion that never ran.

Conflicts and full-suite failures in the queue draw on the **same rework budget** as review findings (3 cycles per story). When it runs out, the story is quarantined.

If the full suite is slow enough for the queue to become the bottleneck, the next step is to hand the test run to a background agent and keep only the merge and completion serial. That has not been needed so far.

## 11. Quarantine

When a worker reports blocked, or a story's rework budget runs out:

- record the reason in the run's summary list;
- take the story out of the in-flight list and detach its slot;
- leave the story marked active and leave its branch in place;
- go back to scheduling.

Nothing extra is persisted. Stories that depend on the quarantined one never become ready, so they are skipped without any special handling. Its files are no longer claimed, so other stories may use them. The final summary lists each blocked story with what it needs, and each story that never started with the story it was waiting on.

In an all-epics run, epics still go one at a time. The run moves to the next epic only when the current one drained with nothing quarantined; otherwise it ends at the summary.

## 12. State and resume

Only one field is stored for the run: its mode, `concurrent` or `sequential`, so a paused run resumes the way it started. Resuming flips the stored run back to active without rewriting it; starting a run afresh would reset the mode.

Everything else is worked out at resume time:

- the in-flight stories are the ones the ledger marks active;
- each story's slot is found by looking for its branch in the worktree list.

The backstops at the top of every loop pass handle whatever an interruption left behind:

| Situation found | Repair |
|---|---|
| Story is done but its branch never merged | Finish the merge. |
| Story is active but its branch is already merged | Run the completion bookkeeping. |
| Story is active with no running worker | Find its worktree by branch; otherwise check the branch out in a free slot (creating it from the merge branch if missing). Spawn a worker in resume mode. |

A quarantined story is in the third situation on resume, which is how it gets retried.

Stopping a run only marks it stopped. Workers already running in the background may finish afterwards; their branches stay in their slots and the next resume picks them up.

## 13. What the user sees

**Pre-flight gate.** Still the single approval for the run. In concurrent mode the story list becomes a schedule table: each open story with its scheduling files (or "none declared, runs alone") and the dependencies it waits on, plus the slot count and the setup command. If every story lacks outputs, the gate says plainly that the run will behave sequentially and why. The mode is not switched silently.

**Progress.** One compact line per story, prefixed with its slot, for example `▶ S2 01.004 Add export route … DONE`.

**Story creation.** The validator emits two warnings that surface in the story-creation summary: stories that declare no outputs, and **hot files**, meaning a file several stories intend to modify. Stories sharing a hot file can never run together whatever the scheduler does, so the user can split the work by file or accept that those stories run one after another.

## 14. Moving a lane implementation to slots

### What happens to each lane concept

| Lane implementation | With slots |
|---|---|
| Lane planner: union-find over outputs, lane numbering, reduction to a maximum lane count | **Remove.** Replace with the stateless scheduler in section 6. |
| Maximum-lanes setting | **Rename** to a maximum-concurrent setting. Same meaning: number of worktrees. |
| One long-lived developer agent per lane | **Replace** with a fresh worker per story, in slot mode. |
| Lane worktrees and lane branches | **Replace** with numbered slot worktrees, detached when idle, and one feature branch per story. |
| Cross-lane gates | **Remove.** A dependency that hasn't merged just means "not ready". The branch is cut after its dependencies merged, so there is nothing to merge in at a gate. |
| All-or-nothing eligibility rules | **Remove.** Degradation is per story: no outputs means it runs alone. Keep an honest message at the gate. |
| Coordination lock on ledger and git index | **Remove**, after moving every ledger write and merge into the orchestrator. |
| Exclusive lock for singleton resources | **Remove**, provided workers only run scoped tests in slots and the full suite only runs in the serial merge queue. See the caution below. |
| Lane agents completing and merging their own stories | **Move** activation, completion and merging into the orchestrator at the main root. |
| Merge of a lane branch without checkout | **Keep the technique**, per story branch instead of per lane branch. |
| Conflict resolver agent with two counters | **Replace** with the conflict-rework worker and the single shared rework budget. |
| Per-lane status, lane marker file in each worktree, lane fields in the epic run record | **Remove.** Keep only the run mode. Derive the rest from the ledger and the worktree list. |
| Run mode values `lanes` / `sequential` | **Rename** to `concurrent` / `sequential`; treat a stored `lanes` value as `concurrent` when reading old records. |
| Leftover-branch flush command | **Replace** with the backstops in section 12 and the worktree removal at the end of a run. |
| Staggered agent start-up | **Remove** unless the target environment needs it. |
| Pre-flight lane table | **Replace** with the schedule table in section 13. |
| Declared outputs on stories | **Keep.** Same input, used at start time instead of plan time. |
| Shared or coordination path list | **Keep.** Now excluded from the overlap check instead of from lane ownership. |

### Features that are independent of lanes

These exist in the lane implementation and were left out of the reference slot implementation as not yet needed. They neither depend on lanes nor conflict with slots. Decide each one on its merits; don't remove them just because the reference lacks them.

- **Outputs reconciler** (adds files a story actually changed to its declared outputs after the fact). Optional with slots, since under-declared outputs surface as merge-queue conflicts. If kept, it must run in the orchestrator's completion step, and its "never shrink" rule can go, because nothing owns files any more.
- **Authentication and transient-failure classifier** for agent spawns. Useful wherever logins expire mid-run. Translate "mark the lane blocked on auth" into "stop scheduling new stories, let in-flight ones finish, leave the affected story active for resume".
- **The "at least one story must declare a modified file" check.** In the lane design this guarded against epics that declared only new files and so hid their integration points. With slots that mistake is caught in the merge queue, but a warning at the gate is cheap if the pattern is common.

### Caution on the exclusive lock

The exclusive lock exists because some commands need a resource only one process can hold. The slot design covers this by running the full suite in the serial merge queue. That only holds if the tests workers run inside slots don't need such a resource. If scoped tests in the target project start servers on fixed ports or share a database, either restrict slot-mode tests to unit tests or keep an exclusive wrapper around just those commands. Check this before deleting the lock.

### Suggested order of work

1. **Finish or flush any lane run in progress.** Lane branches and lane state have no slot equivalent, and writing a converter isn't worth it.
2. **Add the scheduler** as a pure function with tests (list below), alongside the lane planner. Nothing calls it yet.
3. **Add slot mode to the worker**, including the conflict-rework variant.
4. **Move ledger writes and merges into the orchestrator.** This is the largest behavioral change and the one that makes the locks unnecessary.
5. **Rewrite the epic loop** as in section 8, with the merge queue from section 10 and the backstops from section 12.
6. **Switch the pre-flight gate and progress lines** to the slot versions.
7. **Delete** the lane planner, gates, eligibility rules, per-lane state, lane marker files and the locks, then the config keys and help text that mention lanes.
8. **Pilot** on one real epic with two slots and compare wall-clock time with a sequential run.

Leave the sequential loop untouched throughout, so there is always a known-good fallback.

### Behavior to cover with tests

Scheduler:

- stories start in ledger order and stop at the slot limit;
- in-flight stories use up slots and block stories that share a file with them;
- two overlapping stories are never both started in one call;
- a held story does not prevent a later disjoint story from starting;
- a story with unmet dependencies is held, including a dependency in another epic;
- a story with no outputs starts only when nothing is in flight, and blocks everything else while it runs;
- shared paths are ignored by the overlap check, and the default ignores the tracking tree;
- a story whose outputs consist only of shared paths is treated as declaring none;
- a slot limit of 1 reports sequential mode;
- an explicit empty in-flight list is respected, so active-but-quarantined stories don't count as running.

Run state and validation:

- starting a run records the mode; an unknown mode is rejected;
- resuming keeps the stored mode and review setting, and fills in a default for records written before the mode existed;
- the outputs shape is validated; missing outputs and hot files produce warnings, not errors.

## 15. Known limits

- **Merge-queue throughput.** The full suite runs once per story either way, so the cost moves rather than grows, but a long suite caps the speedup.
- **Scoped-test collisions.** Parallel scoped tests that bind fixed ports can clash across slots (see the caution above).
- **Under-declared outputs.** Caught as conflicts and reworked. If it happens often, add the reconciler.
- **Rate limits.** Several workers plus their reviewers run at once.
- **Stale context.** A running worker doesn't see context regenerated from another story's discoveries until the next story. Accepted.
- **Duplicate discoveries.** Two workers may log the same decision. The existing consolidation check at completion merges them.
- **Existing backlogs.** Stories written before outputs were declared run one at a time. There is no backfill command.
