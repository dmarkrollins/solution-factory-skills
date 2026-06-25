---
description: Implement stories with structured planning, mandatory gates, discovery tracking, and incremental delivery
argument-hint: <status|next|list|start|resume|complete|rollback|plan|epic> [story-id|epic-id]
allowed-tools: [Read, Glob, Grep, Bash, Edit, Write, Task]
---

# Mode of Operation

Implement stories from `.solution-factory/` one at a time with mandatory quality gates. Each story follows: resolve → activate → plan → implement → complete.

**Pipeline position:** `/ideate` → `/create-stories` → **`/solution`**

Parse arguments to determine subcommand. Default to `next` if no arguments.

## Working Directory Rule

**CRITICAL — applies to every command in every phase:**

All `python3 ~/.claude/skills/solution-factory/scripts/...` invocations **must** be prefixed with the project root:
```bash
cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/...
```
Never assume the cwd is correct after running package-level commands (e.g. `npm test`, `npx tsc`, `cd packages/...`). Always anchor to the project root before invoking solution-factory scripts.

---

# Subcommand Routing

```
/solution help         → Show this command reference
/solution              → next (default)
/solution status       → Show progress overview
/solution next         → Resume active epic if one exists, else find next ready story
/solution list [--status] → List stories with optional filter
/solution start <id>   → Start a story (planning → implementation)
/solution resume       → Resume in-progress single story
/solution complete <id> → Complete a story
/solution rollback <id> → Reopen completed story
/solution plan <id>    → Create/review plan only
/solution stop         → Pause an active epic run; state saved to epic JSON
/solution epic <id>    → Autonomously run all ready stories in an epic
/solution epic <id> --review-merges → Same, but pause for approval before each merge
```

> **Interactive vs autonomous:** `next`/`start`/`resume`/`complete` are the
> interactive single-story commands — they stop at the plan-approval gate and
> ask questions one at a time. `epic` is the autonomous runner: one upfront
> confirmation, then it works the whole epic backlog unattended. The two share
> the exact same Phases 1–5 processing rules; `epic` only converts the human
> gates into autonomous decisions (see that command for the override table).

---

# Command: help

Print the reference below **verbatim** — it is self-contained, so no code or
script reading is needed to learn how to drive the skill. Do not run any scripts
for this command.

```
/solution — implement stories from .solution-factory/ with quality gates.
Pipeline: /ideate → /create-stories → /solution

WORKING A SINGLE STORY (interactive — you approve the plan, answer questions):
  /solution                 Resume active epic if one exists, else find next ready story
  /solution next            Same as above (explicit)
  /solution start <id>      Start a specific story (e.g. /solution start 03.002)
  /solution resume          Pick up the in-progress single story where it left off
  /solution plan <id>       Write/refine a plan only — no branch, no code
  /solution complete <id>   Validate, test, merge, and close a finished story
  /solution rollback <id>   Reopen a completed story as active

RUNNING A WHOLE EPIC (autonomous — one confirmation, then unattended):
  /solution epic <id>                  Run every ready backlog story in the epic
  /solution epic <id> --review-merges  Same, but pause for yes/no before each merge
  /solution stop                       Pause the active epic run; resume later with /solution next

SEEING WHERE THINGS STAND:
  /solution status              Progress overview across all epics
  /solution list [--status X]   List stories (optionally filter by status)
  /solution help                This reference

INTERACTIVE vs AUTONOMOUS
  Interactive commands stop at the plan-approval gate and ask questions one at a
  time — use them when scope is still fuzzy or you want to steer each story.
  `epic` is the engine: it confirms the run once, then plans, implements, tests,
  reviews, and merges each story unattended, cleaning context between stories.
  Use it when stories are already well-formed from /create-stories.

  Both modes run the IDENTICAL Phases 1–5 quality gates (YAGNI filter, complexity
  re-assessment, two-tier testing, code review, security review, documentation
  cleanup, discovery tracking). `epic` only converts the human gates into
  autonomous decisions; on a genuine blocker it stops and asks rather than guessing.

  --review-merges gives you per-merge approval for a single run without changing
  config — the on-demand equivalent of automerge=false. Only the merge is gated;
  everything else still runs unattended.

CONFIG (.solution-factory/config.json — stories block):
  automerge, generate_demo_scripts, require_tests, complexity threshold, and
  discovery relevance thresholds all apply in BOTH modes.

STOP / RESUME AN EPIC RUN
  Hit Escape to interrupt, then:
    /solution stop     saves run state to the epic JSON (via epic_run_manager.py)
                       and commits it — safe to close Claude
    /solution next     detects the paused run and resumes the EPIC-3 loop
                       automatically; falls back to next single story if no run found

  State is stored in the `run` block of .solution-factory/epics/<id>/<id>.json:
    status: active | stopped | complete
    current_story, review_merges, started_at, stopped_at

CONFIG (.solution-factory/config.json — stories block):
  automerge, generate_demo_scripts, require_tests, complexity threshold, and
  discovery relevance thresholds all apply in BOTH modes.

TYPICAL FLOW
  /solution status          see what's ready
  /solution epic epic-03    run the epic unattended
  /solution stop            pause mid-epic; close Claude
  /solution next            resume where you left off
```

---

# Command: status

```bash
python3 ~/.claude/skills/solution-factory/scripts/get_status.py
```

Display formatted output:
```
Progress: [done]/[total] stories ([active] active, [backlog] backlog, [deferred] deferred)
Epics: [total_epics]

[Per-epic breakdown]

[If active story:] Currently working on: [story_id] in [epic_id]
```

---

# Command: next

First checks for an active or paused epic run. If one exists, resumes the epic
loop. Otherwise resolves the next single story and flows into planning.

1. **Check for active epic run:**
   ```bash
   cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/epic_run_manager.py find --root .
   ```
   - If `found: true` → announce `[RESUMING EPIC] [epic_id]: [title]`, run
     `start` to flip status back to `active`, then re-enter the EPIC-3
     orchestration loop using the stored `epic_id` and `review_merges`:
     ```bash
     cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/epic_run_manager.py start --epic [epic_id] --root .
     ```
   - If `found: false` → continue to step 2.

2. **Resolve next story:**
   ```bash
   python3 ~/.claude/skills/solution-factory/scripts/story_resolver.py next
   ```

3. **Parse result:**
   - `status: "active"` → story in progress, execute `resume` immediately
   - `status: "ready"` → execute the `start` command (Gates → Activation →
     Planning through step 3f) with no confirmation prompt. The user invoked
     `/solution next` — that IS the intent to proceed. The first stop point
     is the plan approval in step 3f.
   - `status: "complete"` → display "All stories completed or blocked"

> Tip: run `/clear` before starting a new story for a clean context.

---

# Command: list

```bash
python3 ~/.claude/skills/solution-factory/scripts/story_resolver.py list [--status <filter>]
```

Display formatted list of stories with IDs, titles, statuses.

---

# Command: start

## PHASE 1: Story Resolution

Parse story ID from arguments. Determine epic ID from story ID prefix.

```bash
python3 ~/.claude/skills/solution-factory/scripts/story_resolver.py next
```

Verify the requested story is ready (deps met). If not, show blocking dependencies.

## PHASE 2: Activation

```bash
python3 ~/.claude/skills/solution-factory/scripts/story_activator.py --story [ID] --epic [EPIC_ID]
```

This single call moves the story folder to `active/` **and** syncs its
`sequence.json` status in the same operation — there is no separate
status-update step, so the folder location and the recorded status can never
drift apart (not even across an interruption mid-activation; re-running it
self-heals any prior drift).

Commit this immediately, before planning begins, so it never sits uncommitted
waiting to be swept into a later, unrelated commit:
```bash
git add .solution-factory/
git commit -m "Activate story [ID]: [title]"
```

Load story context:
```bash
python3 ~/.claude/skills/solution-factory/scripts/context_loader.py full --story [ID] --epic [EPIC_ID]
```

**ANNOUNCE story header immediately:**
```
══════════════════════════════════════
Story [ID]: [Title]
Epic: [EPIC_ID]
Complexity: [N]
══════════════════════════════════════
```

## PHASE 3: Planning

**NO CODE YET — this is a mandatory gate.**

### 3a. Understand Requirements

Read from context_loader output:
- Story JSON (goal, acceptance criteria)
- Referenced ADRs, constraints, capsules
- Dependency summaries

If UX story with wireframe reference → read wireframe file.

### 3b. Explore Codebase

Use Agent tool with subagent_type=Explore, **model=haiku**:
- Thoroughness: "medium"
- Haiku is sufficient for read-only codebase reconnaissance

The exploration prompt **MUST** instruct the agent to:
1. Read all files directly named or referenced in the story
2. Search for **related patterns across the entire codebase** — e.g., if the story fixes a bug in one file, search for the same bug pattern in sibling files
3. Run TypeScript/lint checks if applicable to surface any pre-existing errors
4. Identify all files that will need to change to fully satisfy the acceptance criteria

**The goal is a holistic picture, not just the named file.** The plan must reflect the full scope of changes needed — not just the obvious entry point. If related files have the same issue, they belong in the plan.

> **Explore limitation:** The Explore agent reads file excerpts and will miss content past its read window. After exploration, for any critical file identified as needing changes that is >300 lines, use Read directly on the relevant sections — do not rely solely on what the agent surfaced.

### 3b.5. YAGNI Pre-Filter

**MANDATORY — must complete before requirements interview or plan creation.**

Using the acceptance criteria (from 3a) AND the codebase findings (from 3b), explicitly determine what will NOT be built. This step runs after exploration so exclusions are informed by what already exists and what can be reused.

For each acceptance criterion, ask:
- What is the absolute minimum implementation that satisfies this criterion?
- Is there an existing pattern or utility in the codebase that can be reused as-is?
- Would a reasonable engineer question whether this belongs in this story?

Then produce a **YAGNI Exclusion List** and output this block before proceeding:

```
YAGNI Pre-Filter:
  Story: [ID] — [Title]
  Exclusions:
    - [Thing NOT being built] — [reason: no acceptance criterion requires it / belongs in future story / existing code handles it]
    ...
  Minimum Viable Scope:
    [1-3 sentence statement of the smallest implementation that satisfies ALL acceptance criteria]
```

**Rules:**
- The exclusion list must be non-empty. If you cannot identify anything to exclude, think harder — common exclusions include: error handling beyond what's tested, configuration options not required by any criterion, abstractions for hypothetical reuse, logging/metrics not in acceptance criteria, UI polish not specified, and features "that would be nice."
- Do NOT add any excluded item to the plan in step 3d.
- If an item in the exclusion list maps to an acceptance criterion → it is not an exclusion, remove it from the list.
- The Minimum Viable Scope statement becomes the north star for the plan — every implementation step must trace back to it.
- **The YAGNI exclusions from this step MUST populate `## NOT Doing (YAGNI)` in plan.md verbatim.**

### 3c. Complexity Re-Assessment (Post-YAGNI)

**MANDATORY — must run immediately after YAGNI, before plan creation.**

Re-score the story based on the YAGNI-filtered scope (not the original story text). The exclusion list may have removed significant work — the re-assessed score must reflect that.

```
Complexity Re-Assessment:
  Original: [N]
  After YAGNI: [M]
  Change Surface: [score]  ← files/systems actually touched after exclusions
  Implementation: [score]  ← effort for what remains
  Uncertainty: [score]     ← unknowns in the remaining scope only
  Scope: [score]           ← breadth of the YAGNI-filtered work
  Note: [what YAGNI removed that drove the score down/up]
```

- If score unchanged → document why exclusions didn't affect complexity
- If score dropped → this is expected; proceed with confidence
- If score > 3 after YAGNI → **MUST offer to split** — do not proceed without resolution

### 3d. Requirements Interview

**ONE QUESTION AT A TIME — this is a mandatory gate.**

Exception: max 3 tightly coupled questions about the same subsystem.

Identify and resolve only gaps that cannot be answered from the codebase exploration:
- Ambiguous terminology
- Missing implementation details not visible in code
- Unclear scope edge cases

If codebase exploration answered all questions → state that explicitly and skip interview.

Continue until you can articulate:
- Exact problem to solve
- Scope boundaries
- Testing strategy

### 3e. Create Plan

Write `plan.md` directly to `.solution-factory/epics/[EPIC_ID]/stories/active/[STORY_ID]/plan.md` using all context gathered so far (story JSON, YAGNI exclusions, complexity re-assessment, interview clarifications, exploration findings). Do NOT output the plan contents to the user — write the file silently, then proceed immediately to step 3f.

Use this structure:

```markdown
# Story [ID]: [Title]

**Complexity:** [original score] → [post-YAGNI score]  (delta: [+N / -N / unchanged])

## Objective
[Clear statement of what this story delivers — must match Minimum Viable Scope from YAGNI pre-filter]

## NOT Doing (YAGNI)
<!-- Populated verbatim from the YAGNI Pre-Filter exclusion list in step 3b.5 -->
- [Thing NOT being built] — [reason]
- ...

## Clarifications
[Q&A from requirements interview]

## Approach
[Technical approach chosen]

## Files to Create/Modify
[List of files]

## Implementation Steps
<!-- Each step must name the acceptance criterion it satisfies. Steps with no criterion mapping are CUT. -->

### Step 1: [Name] — satisfies AC: [criterion #]
- [ ] Action item 1
- [ ] Action item 2

### Step 2: [Name] — satisfies AC: [criterion #]
- [ ] Action item 1
...

## Testing Strategy
[How this will be tested]

## Acceptance Criteria Validation
- [ ] Criterion 1 (from story JSON)
- [ ] Criterion 2
...
```

### 3f. User Approval

Present ONLY these four items — nothing else:

```
---
**Story [ID]: [Title]**

**Complexity:** [original] → [post-YAGNI] (delta: [unchanged / +N / -N])

**Objective**
[one paragraph from plan.md Objective section]

**NOT Doing (YAGNI)**
[bullet list from plan.md NOT Doing section]
```

Then **WAIT for explicit approval**.

- If rejected → revise based on feedback, re-present
- If approved → **save plan.md (MANDATORY before any code)**

## PHASE 4: Implementation

**Only after plan approval.**

### 4a. Create Feature Branch
```bash
git checkout -b feature/[STORY_ID]-[slug]
```
- Example: `feature/01.003-user-registration`

**Then commit `plan.md` as the FIRST commit on the branch — before any code:**
```bash
git add .solution-factory/epics/[EPIC_ID]/stories/active/[STORY_ID]/plan.md
git commit -m "Plan story [STORY_ID]: [title]"
```
This makes "plan precedes code" a visible git fact. No implementation commit may
precede the plan commit.

### 4b. Route to Implementation Agent

Determine story type from the plan's **Files to Create/Modify** list:

| Dominant file types | Agent |
|---|---|
| API routes, services, models, workers, jobs | `backend-developer` |
| Components, pages, CSS/styles, hooks, UI utilities | `frontend-developer` |
| Schema files, migrations only | `database-engineer` |
| CI config, Dockerfiles, infra | `devops-engineer` |
| Mixed (significant UI + API work) | Implement inline (step 4c) |

Spawn the appropriate agent (**model=sonnet**) with:
- Full plan.md contents
- Story acceptance criteria (from JSON)
- Feature branch name and current git status
- List of files to create/modify

**Include these mandatory rules in the agent prompt verbatim:**
> - Update plan.md checkboxes as each step completes: `- [ ]` → `- [x]`
> - Commit atomically after each major step: `git add [files] && git commit -m "Step N: [step name] - [brief context]"` — no Claude Code footer, no single mega-commit at the end
> - Log any new architectural discoveries (unexpected constraints, patterns, decisions made) to `.solution-factory/epics/[EPIC_ID]/stories/active/[STORY_ID]/local.md`
> - If blocked at any point, document the blocker in local.md and return a blocker summary — do not guess past it

After the agent completes, verify:
```bash
git log --oneline main..HEAD    # confirms incremental commits exist
git status                      # confirms no uncommitted changes remain
```
Check that plan.md step checkboxes are updated. If the agent hit a blocker, present it to the user with 2–3 options before proceeding.

### 4c. Per-Step Workflow (inline implementation)

For mixed stories or any story implemented inline:

1. **Execute** — write code, make changes
2. **Write unit tests alongside** — follow existing project test patterns
3. **Track discoveries** — if you identify new architectural decisions or constraints, add them to `local.md`
4. **Mark checkboxes** — update plan.md as steps complete
5. **Commit incrementally** — after each major file/checkpoint:
   ```bash
   git add [relevant files]
   git commit -m "Step N: [step name] - [brief context]"
   ```
   No Claude Code footer. Atomic commits per step.

### 4d. Implementation Rules

- **Stay on feature branch** — never checkout main during implementation
- **plan.md is commit #1** — it must be the first commit on the feature branch; no implementation commit may precede it (4a)
- **Incremental commits** — not just at end (mandatory gate)
- **Track blockers** in local.md
- **If blocked**: document in local.md, present to user with 2-3 options, wait for decision
- **No over-engineering** — implement exactly what the plan says

## PHASE 5: Pre-Completion

**Still on feature branch.**

### 5a. Two-Tier Testing

**MANDATORY — both tiers must pass.**

Spawn `test-engineer` agent (**model=sonnet**) with:
- Changed files list: output of `git diff --name-only main..HEAD`
- Full diff: output of `git diff main..HEAD`
- Project root path
- Request: (1) identify the project's test commands from package.json/Makefile/pyproject.toml, (2) run **Tier 1** — tests scoped to changed files for fast feedback, (3) run **Tier 2** — full test suite as safety net, (4) report pass/fail per tier with specific failure messages and fix suggestions

If the agent reports failures → review the failures → fix (inline or by re-spawning the agent targeted at failing tests) → re-run until both tiers pass. Do NOT move to 5a.5 until clean.

### 5a.5. Code Review

**MANDATORY — runs after tests pass, before demo scripts.**

Spawn `code-reviewer` agent (**model=sonnet**) with:
- Story JSON path: `.solution-factory/epics/[EPIC_ID]/stories/active/[STORY_ID]/[STORY_ID].json`
- Plan path: `.solution-factory/epics/[EPIC_ID]/stories/active/[STORY_ID]/plan.md`
- ADR paths: all ADR files for IDs listed in the story's `decisions.refs` (under `.solution-factory/decisions/`)
- Constraint paths: all constraint files for IDs listed in the story's `constraints.refs` (under `.solution-factory/constraints/`)
- Instruction to run `git diff main..HEAD` itself to get the full diff

Review verdict:
- **APPROVED** or **APPROVED WITH NOTES** → proceed to 5a.6. Log any notes as discoveries in `local.md`.
- **NEEDS REWORK** → address all Critical and Important issues → re-run 5a (tests) → re-run 5a.5 (review) until APPROVED.

### 5a.6. Security Review

**MANDATORY — runs after code review passes, before demo scripts.**

Spawn `security-engineer` agent (**model=sonnet**) with:
- Instruction to run `git diff --name-only main..HEAD` and `git diff main..HEAD` itself
- Story title and description

The agent applies an internal fast-pass rule — if no attack surface is touched (no API routes, auth, data access, external I/O, or user-facing inputs), it returns "SECURITY: N/A" and the step is automatically satisfied.

Security review verdict:
- **APPROVED** or **APPROVED WITH NOTES** → proceed to 5b. Log any medium-severity notes as discoveries in `local.md`.
- **NEEDS REWORK** → address all Critical and High findings → re-run 5a (tests) → re-run 5a.5 (code review) → re-run 5a.6 (security review) until APPROVED.

---

### 5b. Create Demo Scripts (optional)

Check whether demo script generation is enabled:
```bash
cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/config_loader.py . | python3 -c "import sys,json; c=json.load(sys.stdin); print(c['config']['stories'].get('generate_demo_scripts', False))"
```

**If the output is `False` → skip this step entirely and proceed to 5b.5.**

**If the output is `True` → generate all 3 scripts + runner:**

Use Agent tool with **model=sonnet** to generate demo scripts. Provide the agent with:
- Story acceptance criteria
- Files changed (from git diff)
- Story title and description

Prompt: "Generate demo test scripts for story [ID]: [title]. Acceptance criteria: [list]. Files changed: [list]. Create EXACTLY 4 files in `.solution-factory/tests/[EPIC_ID]/[STORY_ID]/`: demo_happy_path.py, demo_edge_cases.py, demo_error_handling.py, run_all_demos.py. DO NOT create any README, index, manifest, output log, or any other files beyond these 4."

Sonnet is required here for precise instruction-following and accurate file path/assertion generation.

After generation:
```bash
chmod +x .solution-factory/tests/[EPIC_ID]/**/run_all_demos.py
```

Run demos to verify:
```bash
python3 .solution-factory/tests/[EPIC_ID]/[STORY_ID]/run_all_demos.py
```

### 5b.5. Documentation Cleanup

Spawn `documentation-writer` agent (**model=sonnet**) with:
- Instruction to run `git diff --name-only main..HEAD` and `git diff main..HEAD` itself
- Story title and description

The agent scans existing project documentation for stale references to changed areas and updates them. If no existing docs reference the changed area, it returns "DOC: N/A" and no action is taken. Do not generate new documentation beyond what already exists unless an acceptance criterion explicitly requires it.

After the agent completes, if any files were updated:
```bash
git add [updated doc files]
git commit -m "Step docs: update documentation for story [STORY_ID]"
```

### 5c. Stop

Tell user: **"Run `/solution complete [ID]` when ready."**

**STOP — do not proceed to completion inline.**

---

# Command: resume

1. Find active story:
   ```bash
   python3 ~/.claude/skills/solution-factory/scripts/story_resolver.py next
   ```
   Should return `status: "active"`.

2. Announce **[RESUMING]**

3. Load context:
   ```bash
   python3 ~/.claude/skills/solution-factory/scripts/context_loader.py full --story [ID] --epic [EPIC_ID]
   ```

4. Read `plan.md` — check which steps are complete (checked boxes)

5. Check git status — understand current branch state

6. Continue implementation from where it left off

---

# Command: complete

1. **Parse story ID** from arguments. Determine epic ID.

2. **Validate completion:**
   ```bash
   python3 ~/.claude/skills/solution-factory/scripts/story_completer.py validate --story [ID] --epic [EPIC_ID]
   python3 ~/.claude/skills/solution-factory/scripts/check_plan_complete.py --story [ID] --epic [EPIC_ID]
   ```
   If not valid → show errors, **STOP**

3. **Run full test suite** — MANDATORY
   If tests fail → **STOP**, do not merge

4. **Process discoveries from local.md:**

   Read `local.md` from the active story folder. For each discovery:
   - Assess relevance score (1-10) based on how broadly applicable it is
   - Prepare JSON array of scored discoveries using **exactly these field names** (the script raises `KeyError` otherwise):

   ```json
   [
     {
       "title": "Short descriptive title",
       "content": "Full explanation of the discovery",
       "type": "decision | constraint",
       "relevance": 8,
       "source_story": "04.001"
     }
   ]
   ```

   > **Field names are strict:** use `content` (not `body`/`description`), and always include `source_story`.

   ```bash
   python3 ~/.claude/skills/solution-factory/scripts/discovery_promoter.py auto \
     --discoveries '[...]'
   ```

   For items needing confirmation → present to user one at a time, ask yes/no.
   For confirmed items:
   ```bash
   python3 ~/.claude/skills/solution-factory/scripts/discovery_promoter.py confirm \
     --discoveries '[...]'
   ```

5. **Regenerate capsules** (if any discoveries promoted):
   ```bash
   python3 ~/.claude/skills/solution-factory/scripts/capsule_generator.py
   ```

6. **Complete the story:**
   ```bash
   python3 ~/.claude/skills/solution-factory/scripts/story_completer.py complete --story [ID] --epic [EPIC_ID]
   ```
   This single call moves the story folder to `done/` **and** syncs its
   `sequence.json` status (plus `completed` timestamp) in the same operation —
   no separate status-update step, so folder location and status can't drift.

8. **Commit .solution-factory/ artifacts:**
   ```bash
   git add .solution-factory/
   git commit -m "Complete story [ID]: [title]"
   ```

9. **Merge — check automerge config:**
   ```bash
   cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/config_loader.py . | python3 -c "import sys,json; c=json.load(sys.stdin); print(c['config']['stories'].get('automerge', True))"
   ```
   - **If `True`** → merge immediately without asking:
     ```bash
     git checkout main
     git merge --no-ff feature/[STORY_ID]-[slug] -m "Merge story [ID]: [title]"
     git branch -d feature/[STORY_ID]-[slug]
     ```
   - **If `False`** → ask user for approval, then merge if approved:
     ```bash
     git checkout main
     git merge --no-ff feature/[STORY_ID]-[slug] -m "Merge story [ID]: [title]"
     git branch -d feature/[STORY_ID]-[slug]
     ```

11. **Push .solution-factory/ artifacts:**
    ```bash
    git add .solution-factory/
    git commit -m "Update solution-factory artifacts for story [ID]"
    ```

12. **Check if epic is complete:**
    Check sequence.json — if all stories in this epic are `done`:
    ```bash
    python3 ~/.claude/skills/solution-factory/scripts/generate_sequence.py update-epic-status --epic [EPIC_ID] --status completed
    ```

    Display:
    ```
    Epic [EPIC_ID] Complete!
    All [N] stories implemented and merged.

    Next: Run /create-stories to define the next epic, or /solution next to continue.
    ```

---

# Command: rollback

```bash
python3 ~/.claude/skills/solution-factory/scripts/story_completer.py rollback --story [ID] --epic [EPIC_ID]
```

This single call moves the story folder back to `active/` **and** syncs its
`sequence.json` status in the same operation — no separate status-update step,
so folder location and status can't drift.

Inform user the story is reopened and active.

---

# Command: plan

Create/review a plan for a story without starting implementation.

1. Run Phase 2 (activation) and Phase 3 (planning) from the `start` workflow
2. Save plan.md
3. **STOP** — do not create branch or begin implementation

---

# Command: stop

Pause an active epic run so the user can close Claude and resume later with
`/solution next`.

1. **Find the active epic run:**
   ```bash
   cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/epic_run_manager.py find --root .
   ```

2. **If not found:** display "No active epic run. Use `/solution status` to see
   current state." and STOP.

3. **If found:** stop the run:
   ```bash
   cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/epic_run_manager.py stop --epic [epic_id] --root .
   ```

4. **Display a summary:**
   ```
   Epic [ID] paused — [Title]
   Completed: [list of done story IDs and titles]
   In progress: [current_story ID and title, or "none"]
   Remaining: [count of backlog stories]

   Run `/solution next` to resume.
   ```

5. **Commit the updated epic JSON:**
   ```bash
   git add .solution-factory/epics/[EPIC_ID]/[EPIC_ID].json
   git commit -m "Pause epic [EPIC_ID] run"
   ```

---

# Command: epic

Autonomously implement **every ready backlog story in a target epic**, one after
another, with a single upfront confirmation. This is the "engine" mode: the user
and Claude do the thinking up front (`/ideate` → `/create-stories`); `epic` then
works the approved backlog with minimal human engagement.

**Design in one sentence:** each story is *implemented* by a fresh **worker
subagent** whose heavy context (exploration, diffs, test loops) is discarded when
it returns a green branch; the **main-thread orchestrator** then runs the
*independent* quality gauntlet (code review, security review, docs) and completion
using the real specialized agents — so reviews keep their specialization AND get
author≠reviewer independence, while the orchestrator's own context stays light
(ledger + compact verdicts only).

> **Why the split (harness nesting limit):** this harness caps agent nesting at
> depth 1 — only the main thread can spawn agents; a spawned worker cannot spawn
> its own. So the specialized review agents (`code-reviewer`, `security-engineer`,
> `documentation-writer`) MUST run from the main-thread orchestrator, not from
> inside the worker. The worker therefore owns implementation + testing only; the
> orchestrator owns review + completion. This is what makes autonomous mode the
> equivalent of interactive mode rather than a degraded inline-everything version.

Parse the epic id from arguments (e.g. `epic-03`). If none is given, run
`get_status.py` and ask the user which epic to run (one question).

**Flags:**
- `--review-merges` — pause before every story's merge and show the user exactly
  what is about to land on `main`, requiring a yes/no per merge. This is the
  on-demand equivalent of `automerge=false` for a single run; everything else
  stays autonomous (planning, implementation, tests, review all run unattended —
  only the merge is gated). Without this flag the run merges automatically (the
  user opted into autonomy by entering epic mode).

Capture `REVIEW_MERGES = true|false` from the flag and thread it to every worker.

## EPIC-1: Build the run manifest

```bash
cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/story_resolver.py list --epic [EPIC_ID]
```

Determine the active config (used in the manifest and by every worker):
```bash
cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/config_loader.py . | python3 -c "import sys,json; c=json.load(sys.stdin)['config']['stories']; print('automerge=%s demo_scripts=%s require_tests=%s' % (c.get('automerge',True), c.get('generate_demo_scripts',False), c.get('require_tests',True)))"
```

If the epic has no `backlog` stories → report "Nothing to run in [EPIC_ID]" and STOP.

## EPIC-2: Pre-flight confirmation (the ONLY human gate)

Present the manifest and the config, then **wait for one yes/no**:

```
Autonomous run — [EPIC_ID]: [Epic title]
Stories to execute (sequence order):
  [ID]  [Title]   complexity [N]   deps: [list|none]
  ...
Config: automerge=[..] · demo_scripts=[..] · require_tests=[..]
Merges: [auto | review each merge (--review-merges)]

Run all [N] ready stories autonomously? (yes / no)
```

- If **no** → STOP.
- If **yes** → write the `run` block to the epic JSON, then proceed to the loop.
  Do not ask anything else until the run ends or a story blocks.

  ```bash
  cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/epic_run_manager.py start --epic [EPIC_ID] [--review-merges] --root .
  ```

## EPIC-3: Orchestration loop

Maintain a ledger in the main thread: `[{id, title, result, note}]`. Repeat:

1. **Resolve the next ready story IN THIS EPIC:**
   ```bash
   cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/story_resolver.py next --epic [EPIC_ID]
   ```
2. **Branch on status:**
   - `status: "complete"` → epic backlog exhausted → go to EPIC-5 (final summary).
   - `status: "active"` → a story is mid-flight (e.g. a prior interrupted run).
     Hand it to a worker in **resume** mode (see worker contract).
   - `status: "ready"` → hand it to a worker in **start** mode.
3. **Implement (EPIC-4):** spawn the worker subagent and **wait** for its
   `IMPLEMENTED | BLOCKED` result.
   - `BLOCKED` → record, update `run.current_story` to this story, **stop the
     loop**, go to EPIC-5 and surface the blocker. Do NOT attempt further stories.
   - `IMPLEMENTED` → proceed to step 4.
4. **Quality gauntlet (EPIC-4b):** the orchestrator runs the independent
   review/security/docs gauntlet against the worker's branch. If it forces rework
   beyond the retry budget → treat as `BLOCKED` (step 3 blocked path).
5. **Complete (EPIC-4c):** the orchestrator runs the `complete` logic
   (discoveries, status, artifact commit, merge per `REVIEW_MERGES`). When
   `--review-merges` is set, this is where the per-merge gate fires (EPIC-3a).
6. **Record & decide:**
   - Story merged & `done` → update `run.current_story` to the next story ID (or
     `null`), append `DONE` to ledger, **loop**.
   - Merge rejected at EPIC-3a → leave branch unmerged, record as held, go to EPIC-5.

   Update `run.current_story` after every story outcome:
   ```bash
   cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/epic_run_manager.py update --epic [EPIC_ID] --story [NEXT_OR_CURRENT_STORY_ID] --root .
   ```

**Announce only a compact line per story** in the main thread — never echo the
worker's internal exploration, diffs, or test output:
```
▶ [ID] [Title] … [DONE | MERGE_PENDING | BLOCKED]  ([one-line note])
```

### EPIC-3a: Merge review (only when `--review-merges` is set)

By this point the orchestrator has already run the worker (implementation +
tests), the quality gauntlet (code review, security review, docs), and the
`complete` logic through discovery promotion, status update, and the
`.solution-factory/` artifact commit — everything except the git merge. Present
the preview:
```
Merge review — [ID] [Title]
  Branch:  feature/[ID]-[slug] → main
  Commits: [N]
  Changes: [git diff --stat summary from the worker]

Merge to main? (yes / no)
```
- **yes** → the orchestrator runs the merge (the same commands `complete` step 9
  uses), then continues the loop:
  ```bash
  cd $(git rev-parse --show-toplevel) && git checkout main \
    && git merge --no-ff feature/[ID]-[slug] -m "Merge story [ID]: [title]" \
    && git branch -d feature/[ID]-[slug]
  ```
  Then run the epic-complete check (`complete` step 12) before looping.
- **no** → leave the branch unmerged for the user, record the story as held, and
  go to EPIC-5. Do not start the next story.

## EPIC-4: Worker subagent contract (implementation + testing only)

Spawn **one worker per story** using the Agent tool with the **story-worker**
agent (**model=sonnet**). The worker runs **Phases 1–4 + 5a (testing)** inline in
its own disposable context and STOPS at a green, merge-ready branch — it does NOT
review, complete, or merge. Its autonomous overrides (plan auto-approval, no-human
interview resolution, inline implementation/testing) are pre-baked in its agent
definition.

Pass the worker this prompt (fill in the brackets):

> You are implementing ONE story autonomously as part of an epic run.
> Project root: `[ROOT]`. Story: `[ID]` in epic `[EPIC_ID]`. Mode: `[start|resume]`.
>
> Execute the `/solution` skill's **Phases 1 through 5a (Two-Tier Testing)** exactly
> as written in `~/.claude/skills/solution/skill.md`, then STOP. Do NOT run code
> review, security review, demo scripts, docs cleanup, or `complete`, and do NOT
> merge — the orchestrator does those. Your autonomous override rules are in your
> agent definition. Do not wait for human input at any gate.
>
> Return ONLY a compact structured payload — no narration:
> ```
> RESULT: IMPLEMENTED | BLOCKED
> STORY: [ID] — [title]
> SUMMARY: <=2 sentences on what shipped (or why blocked)
> BRANCH: feature/[ID]-[slug]
> COMMITS: <count> on the feature branch
> DIFFSTAT: <git diff --stat main..HEAD>
> TESTS: tier1=<pass|fail> tier2=<pass|fail>
> DISCOVERIES: <count logged to local.md>
> BLOCKER: <text>   # only if BLOCKED — what's needed from a human
> ```

> **If the Agent tool call itself is rejected or blocked** — the tool result
> says the user declined the tool use, or the auto-mode permission classifier
> denied it (often with a `Reason:` line) — this is NOT the same as the worker
> returning `BLOCKED`; the worker never ran. Do not silently retry, skip the
> story, or jump straight to a generic question. First **surface the rejection
> verbatim** to the user — quote the full tool-result text, including any
> classifier `Reason:`. Then ask how to proceed (e.g. retry the spawn, run the
> story's phases inline in the main thread instead of via a sub-agent, or pause
> the epic run with `/solution stop`). This applies to every Agent spawn in the
> epic loop — the worker here, and the EPIC-4b review/security/docs agents.

After the worker returns `IMPLEMENTED`, do a **cheap sanity check** before
trusting it: confirm the feature branch exists with commits and a clean tree.
```bash
cd $(git rev-parse --show-toplevel) && git rev-parse --verify feature/[ID]-[slug] >/dev/null 2>&1 && git log --oneline main..feature/[ID]-[slug] | head && git status --porcelain
```
If the branch is missing, has no commits, or the worker reported `IMPLEMENTED` but
tests as `fail`, treat it as `BLOCKED` (note: "worker reported success but branch
not ready") and stop the loop.

## EPIC-4b: Quality gauntlet (orchestrator-run, independent agents)

The branch is green but **unreviewed**. The orchestrator now runs the independent
review passes from the main thread — these are the specialized agents the worker
cannot spawn itself. Run them against `git diff main..feature/[ID]-[slug]` exactly
as Phases **5a (independent test review — risk-tiered, below)**, **5a.5 (code
review)**, **5a.6 (security review)**, **5b (demo scripts, config-gated)**, and
**5b.5 (documentation cleanup)** specify. Check out the feature branch first so the
agents see the changes:
```bash
cd $(git rev-parse --show-toplevel) && git checkout feature/[ID]-[slug]
```

- **Independent test review (risk-tiered, optional).** The worker already wrote and
  ran tier-1 + tier-2 tests, and EPIC-4c re-runs the full suite as a backstop — so
  for routine stories that is enough. Spawn `test-engineer` (**model=sonnet**) here
  for an *independent* coverage/quality judgment **only when the story is high-risk**,
  i.e. EITHER condition holds:
  - post-YAGNI complexity (from `plan.md`) is **at or above** the configured
    complexity threshold (the top bucket of allowed stories), OR
  - the diff touches a **critical surface** — auth, data access/migrations,
    payments/money, or external I/O.

  When spawned, `test-engineer` runs Phase 5a as written and additionally judges
  whether coverage is adequate for the acceptance criteria. For routine stories
  below both triggers, **skip it** — do not spawn (keeps trivial stories cheap).
- **Spawn `code-reviewer` (5a.5) and `security-engineer` (5a.6) IN PARALLEL** —
  both **model=sonnet**, both in a single message (two Agent calls). They are
  independent and read-only against the same frozen `main..feature/[ID]-[slug]`
  diff, so there is no reason to serialize them. Collect both verdicts before
  deciding.
- **If any of the spawned reviewers returns NEEDS REWORK** (test-engineer included,
  when run) → re-spawn the **story-worker in `rework` mode** on the same branch,
  passing the combined Critical/Important/High findings verbatim. The worker fixes,
  re-runs tests, and returns `IMPLEMENTED`. Then re-run the gauntlet. **Retry
  budget: 3 rework cycles.** If still not clean after 3 → treat as `BLOCKED` (note:
  "gauntlet could not reach clean after 3 rework cycles") and stop the loop.
  **Set `REWORKED = true` for this story if ≥1 rework cycle ran** — EPIC-4c uses
  this to decide whether the full-suite backstop is needed.
- Once code review AND security review are clean → run 5b (if enabled) and 5b.5.

This gives reviews their specialization **and** author≠reviewer independence — the
reviewer never sees the worker's reasoning, only the committed diff.

## EPIC-4c: Completion (orchestrator-run)

With the branch green and reviewed, the orchestrator runs the **`complete`
command** logic from the main thread (the worker did NOT do this):

- Steps 1–3: validate completion + `check_plan_complete`, then the full-suite
  backstop **conditionally**: re-run the full suite **only if `REWORKED == true`**
  (the gauntlet forced ≥1 rework cycle) **or any commit changed source since the
  worker returned**. Otherwise the working tree is byte-identical to the worker's
  already-green Tier 2, so the re-run is a guaranteed-pass repeat — **skip it and
  trust the worker's recorded `tier2=pass`**. Always run the cheap
  `validate_completion` + `check_plan_complete` checks regardless.
- Step 4: read `local.md` and **auto-promote** discoveries at/above the
  `auto_create` relevance threshold; **discard** those at/below `auto_discard`;
  collect in-between items into the run's deferred list for EPIC-5. Use the
  same strict JSON schema as the `complete` command step 4 (`content` field,
  not `body`; `source_story` required) — see that section for the exact shape.
- Steps 5–8, 11–12: regenerate capsules if needed, flip story status to `done`,
  commit `.solution-factory/` artifacts, run the epic-complete check.
- **Step 9 (merge) — honor `REVIEW_MERGES`:**
  - `false` → merge automatically (the `complete` step 9 commands).
  - `true` → STOP before merge and present the preview at **EPIC-3a**; merge only
    on approval.

After completion, sanity-check the story is actually `done` before looping:
```bash
cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/story_resolver.py list --epic [EPIC_ID] --status done | python3 -c "import sys,json; print([s['id'] for s in json.load(sys.stdin)['stories']])"
```
If the story is not `done`, treat as `BLOCKED` (note: "completion did not update
status") and stop.

## EPIC-5: Final summary

Mark the run complete (or stopped if blocked) in the epic JSON:
```bash
# On clean finish:
cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/epic_run_manager.py complete --epic [EPIC_ID] --root .
# On blocker (leaves status=stopped so /solution next can resume):
cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/epic_run_manager.py stop --epic [EPIC_ID] --root .
git add .solution-factory/epics/[EPIC_ID]/[EPIC_ID].json
git commit -m "Finalize epic [EPIC_ID] run status"
```

Print a table and next steps:
```
Autonomous run complete — [EPIC_ID]
  ✓ [ID] [Title]
  ✓ [ID] [Title]
  ✗ [ID] [Title] — BLOCKED: [reason]   (if any)

Done: [X]/[N]   Blocked: [Y]   Remaining backlog: [Z]
```

**Deferred discoveries** (collected by the orchestrator during each story's
EPIC-4c completion): present each one at a time, ask yes/no, and for confirmed
items run (same strict JSON schema as the `complete` command step 4 — `content`
field, not `body`; `source_story` required):
```bash
cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/discovery_promoter.py confirm --discoveries '[...]'
```
Then regenerate capsules if any were promoted:
```bash
cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/capsule_generator.py
```

**If a story blocked:** show its `BLOCKER` text and offer 2–3 options (e.g. answer
the open question and re-run `/solution epic [EPIC_ID]`; split the story via
`/create-stories`; or implement it interactively with `/solution start [ID]`).

**If the epic is fully done**, the last story's EPIC-4c completion already flipped
the epic to `completed` (complete step 12). Confirm and suggest `/create-stories`
for the next epic.

## Epic-runner rules

- **Sequential only** — never run stories in parallel (dependencies + shared git
  history). One worker at a time.
- **Stop on first blocker** — predictable over "maximize throughput."
- **Split of duties** — the worker owns implementation + testing (its heavy
  exploration/diff context dies with it); the orchestrator owns the independent
  review/security/docs gauntlet and completion, holding only the ledger and
  compact verdicts. This is forced by the depth-1 nesting limit and is what keeps
  reviews specialized + independent rather than self-reviewed inline.
- **No new gates, no changed processing rules** — `epic` reuses Phases 1–5 and
  `complete` verbatim; it only relocates the review/completion phases to the
  orchestrator and swaps human gates for the overrides above.
- **Spawn rejections are surfaced, not swallowed** — if any Agent tool call in
  the loop is rejected or denied before the agent runs, show the user the raw
  rejection/denial text (including any classifier `Reason:`) before asking how
  to proceed. See EPIC-4 for the exact handling.

