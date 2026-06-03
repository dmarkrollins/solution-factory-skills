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
  re-assessment, two-tier testing, code review, discovery tracking). `epic` only
  converts the human gates into autonomous decisions; on a genuine blocker it
  stops and asks rather than guessing.

  --review-merges gives you per-merge approval for a single run without changing
  config — the on-demand equivalent of automerge=false. Only the merge is gated;
  everything else still runs unattended.

CONFIG (.solution-factory/config.json — stories block):
  automerge, generate_demo_scripts, require_tests, complexity threshold, and
  discovery relevance thresholds all apply in BOTH modes.

TYPICAL FLOW
  /solution status          see what's ready
  /solution epic epic-03    run the epic; or `/solution next` to go story-by-story
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
   cd $(git rev-parse --show-toplevel) && python3 -c "
   import json, glob, sys
   files = glob.glob('.solution-factory/epics/*/epic-*.json')
   for f in files:
       d = json.load(open(f))
       run = d.get('run', {})
       if run.get('status') in ('active', 'stopped'):
           print(json.dumps({'found': True, 'epic_id': d['id'], 'title': d['title'], 'run': run}))
           sys.exit(0)
   print(json.dumps({'found': False}))
   "
   ```
   - If `found: true` → announce `[RESUMING EPIC] [epic_id]: [title]` and re-enter
     the EPIC-3 orchestration loop using the stored `epic_id` and `review_merges`
     from the `run` block. Set `run.status` back to `"active"` in the epic JSON
     before entering the loop.
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
python3 ~/.claude/skills/solution-factory/scripts/generate_sequence.py update-status --story [ID] --status active
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
- Story YAML (goal, acceptance criteria)
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

Write `plan.md` directly to `.solution-factory/epics/[EPIC_ID]/stories/active/[STORY_ID]/plan.md` using all context gathered so far (story YAML, YAGNI exclusions, complexity re-assessment, interview clarifications, exploration findings). Do NOT output the plan contents to the user — write the file silently, then proceed immediately to step 3f.

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
- [ ] Criterion 1 (from story YAML)
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
- Story acceptance criteria (from YAML)
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
- Story YAML path: `.solution-factory/epics/[EPIC_ID]/stories/active/[STORY_ID]/[STORY_ID].json`
- Plan path: `.solution-factory/epics/[EPIC_ID]/stories/active/[STORY_ID]/plan.md`
- ADR paths: all ADR files for IDs listed in the story's `decisions.refs` (under `.solution-factory/decisions/`)
- Constraint paths: all constraint files for IDs listed in the story's `constraints.refs` (under `.solution-factory/constraints/`)
- Instruction to run `git diff main..HEAD` itself to get the full diff

Review verdict:
- **APPROVED** or **APPROVED WITH NOTES** → proceed to 5b. Log any notes as discoveries in `local.md`.
- **NEEDS REWORK** → address all Critical and Important issues → re-run 5a (tests) → re-run 5a.5 (review) until APPROVED.

---

### 5b. Create Demo Scripts (optional)

Check whether demo script generation is enabled:
```bash
cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/config_loader.py . | python3 -c "import sys,json; c=json.load(sys.stdin); print(c['config']['stories'].get('generate_demo_scripts', False))"
```

**If the output is `False` → skip this step entirely and proceed to 5c.**

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
   - Prepare JSON array of scored discoveries

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
   python3 ~/.claude/skills/solution-factory/scripts/generate_sequence.py update-status --story [ID] --status done
   ```

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
python3 ~/.claude/skills/solution-factory/scripts/generate_sequence.py update-status --story [ID] --status active
```

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
   cd $(git rev-parse --show-toplevel) && python3 -c "
   import json, glob, sys
   files = glob.glob('.solution-factory/epics/*/epic-*.json')
   for f in files:
       d = json.load(open(f))
       run = d.get('run', {})
       if run.get('status') in ('active', 'stopped'):
           print(json.dumps({'found': True, 'file': f, 'epic_id': d['id'], 'title': d['title'], 'run': run, 'stories': d['stories']}))
           sys.exit(0)
   print(json.dumps({'found': False}))
   "
   ```

2. **If not found:** display "No active epic run. Use `/solution status` to see
   current state." and STOP.

3. **If found:** update the epic JSON — set `run.status = "stopped"` and
   `run.stopped_at` to current UTC timestamp:
   ```bash
   cd $(git rev-parse --show-toplevel) && python3 -c "
   import json, datetime
   f = '[PATH_FROM_STEP_1]'
   d = json.load(open(f))
   d['run']['status'] = 'stopped'
   d['run']['stopped_at'] = datetime.datetime.utcnow().isoformat() + 'Z'
   json.dump(d, open(f, 'w'), indent=2)
   print('saved')
   "
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

**Design in one sentence:** the main thread is a thin orchestrator that holds only
a progress ledger; each story is implemented by a fresh **worker subagent** whose
isolated context is discarded when the story finishes — that is how context is
kept clean between stories.

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
  cd $(git rev-parse --show-toplevel) && python3 -c "
  import json, datetime
  f = '.solution-factory/epics/[EPIC_ID]/[EPIC_ID].json'
  d = json.load(open(f))
  d['run'] = {
    'status': 'active',
    'review_merges': [True|False],
    'started_at': datetime.datetime.utcnow().isoformat() + 'Z',
    'stopped_at': None,
    'current_story': None
  }
  json.dump(d, open(f, 'w'), indent=2)
  "
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
3. **Spawn the worker subagent** (EPIC-4) and **wait** for its structured result.
4. **Record & decide:**
   - `DONE` → update `run.current_story` to the next story ID (or `null` if
     none remain) in the epic JSON, append to ledger, **loop**.
   - `MERGE_PENDING` (only possible when `--review-merges` is set) → present the
     worker's merge preview and **wait for one yes/no** (EPIC-3a). On approval the
     orchestrator performs the merge, updates `run.current_story`, marks the story
     `DONE`, and **loops**. On rejection, treat as a stop: leave the branch
     unmerged and go to EPIC-5.
   - `BLOCKED` → update `run.current_story` to the blocked story ID in the epic
     JSON, append to ledger, **stop the loop**, go to EPIC-5 and surface the
     blocker with 2–3 options. Do NOT attempt further stories (later stories
     typically depend on the blocked one).

   Update `run.current_story` after every story outcome:
   ```bash
   cd $(git rev-parse --show-toplevel) && python3 -c "
   import json
   f = '.solution-factory/epics/[EPIC_ID]/[EPIC_ID].json'
   d = json.load(open(f))
   d['run']['current_story'] = '[NEXT_OR_CURRENT_STORY_ID]'
   json.dump(d, open(f, 'w'), indent=2)
   "
   ```

**Announce only a compact line per story** in the main thread — never echo the
worker's internal exploration, diffs, or test output:
```
▶ [ID] [Title] … [DONE | MERGE_PENDING | BLOCKED]  ([one-line note])
```

### EPIC-3a: Merge review (only when `--review-merges` is set)

The worker has already validated, tested, reviewed, processed discoveries,
completed the story status, and committed `.solution-factory/` artifacts — it
stopped only at the git merge. Present its preview verbatim:
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

## EPIC-4: Worker subagent contract

Spawn **one worker per story** using the Agent tool with the **general-purpose**
agent (it has the full tool set: Read/Edit/Write/Bash/Grep/Glob), **model=sonnet**.
The worker runs the complete single-story workflow **inline in its own context**.

Pass the worker this prompt (fill in the brackets):

> You are implementing ONE story autonomously as part of an epic run. Project
> root: `[ROOT]`. Story: `[ID]` in epic `[EPIC_ID]`. Mode: `[start|resume]`.
>
> Execute the `/solution` skill's **Phases 1–5 then the `complete` command**
> exactly as written in `~/.claude/skills/solution/skill.md`, with these
> **autonomous overrides** — everything else (YAGNI pre-filter, complexity
> re-assessment, two-tier testing, code review, discovery tracking, incremental
> commits, config-driven demo scripts and automerge) is UNCHANGED and MANDATORY:
>
> 1. **Plan approval (3f):** auto-approve. Still write `plan.md` in full. Do not
>    print the approval block or wait for a human.
> 2. **Requirements interview (3d):** there is no human. Resolve every ambiguity
>    from codebase exploration and the story's acceptance criteria. If a genuine
>    blocker remains (contradictory criteria, behavior you cannot determine, a
>    missing prerequisite) — do NOT guess. Document it in `local.md` and return
>    `BLOCKED`.
> 3. **Complexity > 3 after YAGNI (3c):** do not split autonomously. Document and
>    return `BLOCKED`.
> 4. **Tests fail / code review NEEDS REWORK (5a, 5a.5):** rework inline and
>    re-run until clean — these loops are already autonomous. If you cannot reach
>    green after reasonable effort, document and return `BLOCKED`.
> 5. **You do work INLINE** — do not spawn further subagents. Do the exploration,
>    implementation, testing, and code-review pass yourself, applying the same
>    rigor the named agents would. (The skill normally delegates these to keep
>    the parent context lean; your context is already isolated and disposable, so
>    inline is correct here.)
> 6. **Discovery promotion (complete step 4):** auto-apply items at/above the
>    `auto_create` relevance threshold and discard those at/below `auto_discard`
>    (per config). For "prompt-band" items in between, do NOT block — list them in
>    your return payload under `deferred_discoveries` for end-of-run review.
> 7. **Merge:** `REVIEW_MERGES = [true|false]` for this run.
>    - If `false` → merge automatically, ignoring the `automerge` config (the user
>      opted into autonomy by entering epic mode). Use the `complete` command's
>      merge commands.
>    - If `true` → run `complete` through ALL its steps EXCEPT the final merge
>      (step 9) and the epic-complete check (step 12). Specifically: complete
>      story status, commit `.solution-factory/` artifacts, leave the feature
>      branch merge-ready, and **do NOT** check out `main` or merge. Return
>      `MERGE_PENDING` with a merge preview — the orchestrator performs the merge
>      after the user approves.
>
> Run `complete` for the story when Phases 1–5 pass. Then **return ONLY** a
> compact structured payload — no narration:
> ```
> RESULT: DONE | MERGE_PENDING | BLOCKED
> STORY: [ID] — [title]
> SUMMARY: <=2 sentences on what shipped (or why blocked)
> COMMITS: <count> on feature/[ID]-[slug], merged=<yes|no>
> DIFFSTAT: <git diff --stat main..HEAD>   # required when MERGE_PENDING
> DEFERRED_DISCOVERIES: [ {note, relevance} ... ]   # may be empty
> BLOCKER: <text>   # only if BLOCKED — what's needed from a human
> ```

After the worker returns, the orchestrator does a **cheap sanity check** before
trusting `DONE` or `MERGE_PENDING` (keeps the engine honest without re-reading the
work). Both paths run `complete` through the status update, so the story must be
`done` in sequence.json either way:
```bash
cd $(git rev-parse --show-toplevel) && python3 ~/.claude/skills/solution-factory/scripts/story_resolver.py list --epic [EPIC_ID] --status done | python3 -c "import sys,json; print([s['id'] for s in json.load(sys.stdin)['stories']])"
```
If the worker reported `DONE`/`MERGE_PENDING` but the story is not `done`, treat it
as `BLOCKED` (note: "worker reported success but status not updated") and stop.

## EPIC-5: Final summary

Mark the run complete (or stopped if blocked) in the epic JSON:
```bash
cd $(git rev-parse --show-toplevel) && python3 -c "
import json, datetime
f = '.solution-factory/epics/[EPIC_ID]/[EPIC_ID].json'
d = json.load(open(f))
d['run']['status'] = 'complete'   # use 'stopped' if ending due to a blocker
d['run']['current_story'] = None
json.dump(d, open(f, 'w'), indent=2)
"
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

**Deferred discoveries** (collected from all workers): present each one at a time,
ask yes/no, and for confirmed items run:
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

**If the epic is fully done**, the last worker's `complete` already flipped the
epic to `completed` (complete step 12). Confirm and suggest `/create-stories` for
the next epic.

## Epic-runner rules

- **Sequential only** — never run stories in parallel (dependencies + shared git
  history). One worker at a time.
- **Stop on first blocker** — predictable over "maximize throughput."
- **Thin orchestrator** — the main thread holds the ledger and compact status
  lines only; all heavy work lives in (and dies with) each worker's context.
- **No new gates, no changed processing rules** — `epic` reuses Phases 1–5 and
  `complete` verbatim; it only swaps human gates for the overrides above.

