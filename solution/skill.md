---
description: Implement stories with structured planning, mandatory gates, discovery tracking, and incremental delivery
argument-hint: <status|next|list|start|resume|complete|rollback|plan> [story-id]
allowed-tools: [Read, Glob, Grep, Bash, Edit, Write, Task]
---

# Mode of Operation

Implement stories from `.solution-factory/` one at a time with mandatory quality gates. Each story follows: resolve → activate → plan → implement → complete.

**Pipeline position:** `/ideate` → `/create-stories` → **`/solution`**

Parse arguments to determine subcommand. Default to `next` if no arguments.

---

# Subcommand Routing

```
/solution              → next (default)
/solution status       → Show progress overview
/solution next         → Find next ready story
/solution list [--status] → List stories with optional filter
/solution start <id>   → Start a story (planning → implementation)
/solution resume       → Resume in-progress story
/solution complete <id> → Complete a story
/solution rollback <id> → Reopen completed story
/solution plan <id>    → Create/review plan only
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

1. **Resolve next story:**
   ```bash
   python3 ~/.claude/skills/solution-factory/scripts/story_resolver.py next
   ```

2. **Parse result:**
   - `status: "active"` → story in progress, ask "Continue working on [id]?" If yes → execute `resume`
   - `status: "ready"` → display story details, ask "Start working on [id]?" If yes → execute `start`
   - `status: "complete"` → display "All stories completed or blocked"

3. **Display story info** from the story YAML data returned by resolver.

---

# Command: list

```bash
python3 ~/.claude/skills/solution-factory/scripts/story_resolver.py list [--status <filter>]
```

Display formatted list of stories with IDs, titles, statuses.

---

# Command: start

## GATE 0: Context Cleanliness

First, read `.solution-factory/config.json` to determine gate behavior:
```bash
# Check gates config — default is "warn" if not present
cat .solution-factory/config.json
```
The `gates.context_cleanliness` field controls behavior: `"warn"` (default) or `"stop"` (hard block).

```bash
python3 ~/.claude/skills/solution-factory/scripts/check_context.py
```

- If not clean AND gate is `"warn"` → **WARN**: "Consider running /clear for a clean context before starting a new story." Continue.
- If not clean AND gate is `"stop"` → **STOP**: "Context is not clean. Run /clear before starting a new story. (Configured as hard stop in .solution-factory/config.json `gates.context_cleanliness`)"

## GATE 1: Environment Check

The `gates.venv_check` field in `.solution-factory/config.json` controls behavior: `"warn"` (default) or `"stop"` (hard block).

```bash
python3 ~/.claude/skills/solution-factory/scripts/check_venv.py
```

- If no venv AND gate is `"warn"` → **WARN** (not block)
- If no venv AND gate is `"stop"` → **STOP**: "No active virtual environment detected. Activate one before starting. (Configured as hard stop in .solution-factory/config.json `gates.venv_check`)"

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

### 3c. Requirements Interview

**ONE QUESTION AT A TIME — this is a mandatory gate.**

Exception: max 3 tightly coupled questions about the same subsystem.

Identify and resolve:
- Ambiguous terminology
- Missing implementation details
- Unclear scope or edge cases
- Technical approach questions
- Testing expectations

Continue until you can articulate:
- Exact problem to solve
- Scope boundaries
- Constraints/preferences
- Testing strategy

### 3d. Create Plan

Write plan to `.solution-factory/epics/[EPIC_ID]/stories/active/[STORY_ID]/plan.md`:

```markdown
# Story [ID]: [Title]

**Complexity:** [N]

## Objective
[Clear statement of what this story delivers]

## Clarifications
[Q&A from requirements interview]

## Approach
[Technical approach chosen]

## Files to Create/Modify
[List of files]

## Implementation Steps

### Step 1: [Name]
- [ ] Action item 1
- [ ] Action item 2

### Step 2: [Name]
- [ ] Action item 1
...

## Testing Strategy
[How this will be tested]

## NOT Doing (YAGNI)
[Explicitly out of scope]

## Acceptance Criteria Validation
- [ ] Criterion 1 (from story YAML)
- [ ] Criterion 2
...
```

### 3e. Complexity Re-Assessment

**MANDATORY — must show this block:**
```
Complexity Re-Assessment:
  Original: [N]
  After Planning: [M]
  Change Surface: [score]
  Implementation: [score]
  Uncertainty: [score]
  Scope: [score]
```

- If changed → update story YAML, document in local.md
- If > threshold → **MUST offer to split** — do not proceed without resolution

### 3f. User Approval

Present the **complete plan.md contents** to the user verbatim — do NOT summarize, abbreviate, or omit any sections. Every section of the plan template must be visible to the user, including `## NOT Doing (YAGNI)`. Then **WAIT for explicit approval**.

- If rejected → revise based on feedback, re-present
- If approved → **save plan.md (MANDATORY before any code)**

## PHASE 4: Implementation

**Only after plan approval.**

### 4a. Create Feature Branch
```bash
git checkout -b feature/[STORY_ID]-[slug]
```
- Example: `feature/01.003-user-registration`

### 4b. Implement Per Plan

For each step:

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

### 4c. Implementation Rules

- **Stay on feature branch** — never checkout main during implementation
- **Incremental commits** — not just at end (mandatory gate)
- **Track blockers** in local.md
- **If blocked**: document in local.md, present to user with 2-3 options, wait for decision
- **No over-engineering** — implement exactly what the plan says

## PHASE 5: Pre-Completion

**Still on feature branch.**

### 5a. Two-Tier Testing

**MANDATORY — both tiers must pass.**

**Tier 1: Affected tests** — run tests related to changed files (fast feedback):
```bash
git diff --name-only main | head -20
# Then run relevant test subset
```

**Tier 2: Full test suite** — run complete project tests (safety net):
```bash
# Run project's test command (npm test, pytest, etc.)
```

If either tier fails → fix before proceeding. Do NOT move to completion.

### 5b. Create Demo Scripts

**MANDATORY — all 3 scripts + runner.**

Use Agent tool with **model=haiku** to generate demo scripts. Provide the agent with:
- Story acceptance criteria
- Files changed (from git diff)
- Story title and description

Prompt: "Generate demo test scripts for story [ID]: [title]. Acceptance criteria: [list]. Files changed: [list]. Create 4 files in `.solution-factory/tests/[EPIC_ID]/[STORY_ID]/`: demo_happy_path.py, demo_edge_cases.py, demo_error_handling.py, run_all_demos.py"

Haiku is sufficient for templated test generation from structured inputs.

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

6. **Update summary.md** — use Agent tool with **model=haiku** to write a concise summary of what this story delivered. Provide it the plan.md and git diff. Haiku is sufficient for summarizing completed work.

7. **Complete the story:**
   ```bash
   python3 ~/.claude/skills/solution-factory/scripts/story_completer.py complete --story [ID] --epic [EPIC_ID]
   python3 ~/.claude/skills/solution-factory/scripts/generate_sequence.py update-status --story [ID] --status done
   ```

8. **Commit .solution-factory/ artifacts:**
   ```bash
   git add .solution-factory/
   git commit -m "Complete story [ID]: [title]"
   ```

9. **Ask user for merge approval**

10. **If approved:**
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

# Mandatory Gates Summary

| Gate | Rule | Violation = |
|------|------|-------------|
| Context | Configurable via `config.json` `gates.context_cleanliness` — default `warn`, set `stop` to hard block | **Warn** or **STOP** |
| Venv | Configurable via `config.json` `gates.venv_check` — default `warn`, set `stop` to hard block | **Warn** or **STOP** |
| Planning | No code before user-approved plan | **STOP** |
| Complexity | Must show re-assessment block | **STOP** |
| Plan.md | Must save before creating branch | **STOP** |
| Branching | Feature branch before any code | **STOP** |
| Commits | Incremental, not just at end | **STOP** |
| Testing | Two-tier, both must pass | **STOP** |
| Demos | All 3 + runner script | **STOP** |
| Completion | Only via `/solution complete` | **STOP** |
| Merge | Only after user approval | **STOP** |
| Questions | One at a time, never batched | **STOP** |
| Story IDs | Numeric only (never letter suffixes) | **STOP** |

---

# Error Handling

| Condition | Action |
|-----------|--------|
| No `.solution-factory/` | Tell user to run `/ideate`, STOP |
| No sequence.json | Tell user to run `/create-stories`, STOP |
| Story not found | Show available stories, STOP |
| Dependencies not met | Show blocking deps, STOP |
| Dirty working directory | Ask user to commit or stash |
| Not on expected branch | Guide user to correct branch |
| Tests failing | Add to local.md blockers, fix before proceeding |
| Merge conflicts | Guide user through resolution |

---

# Token Efficiency

**Three-tier model strategy:**
- **Scripts** (zero tokens): Gates 0-1, Phases 1-2, Phase 6 file operations
- **Haiku subagents** (low tokens): Codebase exploration, demo script generation, summary.md writing
- **Sonnet/Opus** (full tokens): Planning, implementation, requirements interview, discovery scoring

**Context compression:**
- Load context via `context_loader.py` — loads only what's referenced, not everything
- Dependency summaries via `summary.md` — compressed context, not full story re-reads
- Capsules instead of raw ADRs — compressed architectural context
