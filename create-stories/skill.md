---
description: Break an epic into sequenced, complexity-scored stories with JSON definitions and dependency tracking
argument-hint: [--epic-title="title"]
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit]
---

# Mode of Operation

Break down a brainstormed epic into sequenced stories stored as JSON files in `.solution-factory/`. Each story is complexity-scored, dependency-tracked, and evaluated against existing ADRs/constraints/capsules.

**Pipeline position:** `/ideate` → **`/create-stories`** → `/solution`

**Key principles:**
- Stories MUST have complexity ≤ threshold from `config.json` (default: 3)
- Each epic MUST have ≤ `stories.max_stories_per_epic` from `config.json` (default: 10) — larger scope splits into sequential epics, never one oversized epic
- Vertical slicing — not horizontal layers. This includes the **"build it, then test it" pairing**: never draft a standalone "write/verify tests for `<feature X>`" story for a feature whose tests a dependency story is already obligated to ship (see `stories.require_tests` in `config.json` and the cross-story duplication pre-filter in step 4a.6). Tests for a feature's own behaviors belong inside that feature's story — a downstream twin restates the same AC and is structurally redundant, not added coverage (see adr-014).
- Story execution order = array position in `sequence.json`, NOT numerical sort
- Story IDs are numeric only (never letter suffixes)

> **Why the per-epic cap:** epics run autonomously via `/solution epic`, where the main-thread orchestrator accumulates a small ledger entry per story. Capping the count keeps that growth bounded, keeps the blocker blast-radius small (the run stops on the first blocker), and keeps the EPIC-2 confirmation manifest reviewable.

---

# Workflow

## Step 1: Validate Prerequisites

```bash
python3 ~/.claude/skills/solution-factory/scripts/config_loader.py
```

- If `.solution-factory/` doesn't exist → tell user to run `/ideate` first, STOP
- Extract complexity threshold AND `stories.max_stories_per_epic` (default 10) from config

Check that decisions and/or constraints exist:
```bash
ls .solution-factory/decisions/ .solution-factory/constraints/ 2>/dev/null | head -20
```

- If both empty → warn user that no architectural context exists, suggest running `/ideate`

---

## Step 2: Build Reference Inventory

Load existing context efficiently:

```bash
python3 ~/.claude/skills/solution-factory/scripts/read_docs.py
```

Read ADR and constraint summaries (just titles/IDs, not full content):
```bash
for f in .solution-factory/decisions/*.md; do head -1 "$f" 2>/dev/null; done
for f in .solution-factory/constraints/*.md; do head -1 "$f" 2>/dev/null; done
ls .solution-factory/context/capsules/ 2>/dev/null
```

Keep this as a lookup table — do NOT load full file contents yet.

---

## Step 3: Determine Epic Scope

Read `sequence.json` to understand what epics already exist:
```bash
python3 ~/.claude/skills/solution-factory/scripts/get_status.py
```

### 3a. Detect insertion mode

**If the user's request references an existing in-progress epic** (e.g. mentions specific files, bugs, or topics already covered by a backlog epic), check whether the new stories belong in that epic rather than a new one.

- If adding to an **existing epic** → skip "What is the focus?" question, proceed with the known scope. Set `insertion_mode: true`.
- If creating a **new epic** → ask: **"What is the focus of this epic?"** (one question)

### 3b. Define scope

Based on their answer + documentation + existing context:
- Define epic theme and objective
- Determine epic number (next available, or existing if `insertion_mode`)
- Identify functional boundaries

---

## Step 4: Generate Stories

### 4a. Draft Stories with Plan Agent

Use Agent tool with subagent_type=Plan, **model=sonnet** to generate the initial story draft. Provide:
- Epic theme and objective (from Step 3)
- Full ADR and constraint reference inventory (IDs + titles from Step 2)
- Existing epic count and the next epic number
- Complexity threshold (from config.json, default 3)
- Scoring rubric: Change Surface (0–3), Implementation (0–3), Uncertainty (0–2, max), Scope (0–2, max) — sum must be ≤ threshold

Prompt the agent to draft vertically-sliced stories — **no more than `max_stories_per_epic` (default 10) per epic** — following these principles:
- **Foundation first** — models, schemas, core setup
- **Vertical slices** — thin working features end-to-end
- **Tests travel with their feature** — never draft a separate downstream "test `<feature>`" story; the feature's own AC (and its `require_tests` obligation) already cover its behaviors. A dedicated test story is only legitimate when it targets a genuine gap the feature story's AC doesn't name (e.g. integration wiring across components, regression suites, edge cases nobody specified) — and its AC must be phrased against that gap, not as a restatement of the feature story's AC.
- **Progressive enhancement** — happy path → validation → error handling → edge cases
- Score each story on all 4 dimensions; flag any that exceed threshold for splitting
- List dependencies between stories (which stories must complete first)
- Suggest which ADR/constraint IDs apply to each story

Review the agent's draft — challenge complexity scores, split any over-threshold stories, reorder dependencies as needed. Use this draft as input for steps 4b–4e rather than drafting from scratch.

### 4a.5. Enforce the Per-Epic Cap (split into sequential epics)

**MANDATORY — runs after drafting, before scoring.**

If the draft (or, in `insertion_mode`, the existing epic plus the new stories) exceeds `max_stories_per_epic`, do NOT shrink scope by dropping work. Instead **split the work across sequential epics**:

1. Group the stories along the natural dependency seam — foundational/earlier slices in `epic-NN`, later enhancements in `epic-NN+1` (and so on), each ≤ the cap.
2. Cross-epic dependencies are fine: a story in `epic-NN+1` may depend on a story in `epic-NN` (dependencies are global story IDs; epics run sequentially).
3. Scaffold and write each epic separately in Step 5, and surface the split in the Step 6 summary so the user sees it.

State the split reasoning (which seam, which stories land in which epic, and why) before writing any files. The goal is the same total scope delivered as two right-sized epics, never one oversized one.

### 4a.6. Cross-Story Duplication Pre-Filter

**MANDATORY — runs after drafting (and any epic-cap split), before complexity scoring.**

For every draft story that has at least one dependency, diff its draft acceptance criteria against the **full acceptance-criteria list** of each story it depends on — read the actual AC text, not just the dependency's title or goal. Look specifically for the **"build it, then test it" anti-pattern**: a later story whose AC are restatements of an earlier story's AC, just reframed as "Test: `<earlier AC>`" or "Verify `<earlier behavior>`".

This matters most when `stories.require_tests: true` (check `config.json`) — under that config every implementation story is *already* obligated to ship with tests proving its own acceptance criteria. A standalone "write/verify tests for `<behavior X>`" story, where `X` is the literal AC of a dependency, is then **structurally redundant by construction, not by accident** — the dependency's own implementation will already deliver that exact coverage. (See `adr-014`, which documents this exact failure mode from epic-04: story 04.007 restated story 04.005's AC nearly verbatim as "Test: ...", and the implementing worker found 04.005 had already shipped all 9 scenarios under a different filename.)

For each suspected duplicate pair, classify and act:
- **>~50% of the later story's AC are restatements of the dependency's AC** → merge the later story into the dependency (fold its AC into the dependency's acceptance list / testing strategy) or drop it from the draft entirely. Do not carry it forward as a separate backlog story.
- **Some AC restate, some target genuinely distinct behavior** (integration wiring across components, edge cases the original AC never named, regression/visual suites) → discard the restated AC and keep only the distinct ones, rewritten so each is phrased against the **gap** — what the dependency's AC does *not* already cover — never as an echo of what it does.
- **No overlap found** → no action; move on.

State your duplication analysis (which dependency pairs were checked, what overlap was found, what was merged / rewritten / dropped / kept as-is) before proceeding to scoring. This is the cross-story analogue of `/solution`'s per-story YAGNI pre-filter (3b.5) — same rigor, one level up: across the draft set instead of within a single story.

### 4b. Score Complexity

Score each story on 4 dimensions (0–3 each): **Change Surface** (file → layer → stack), **Implementation** (copy → familiar → new pattern → new architecture), **Uncertainty** (clear=0, minor=1, significant=2; max 2), **Scope** (1-2 criteria=0, 3-4=1, 5+=2; max 2). Sum must be ≤ threshold (default 3).

### 4c. Split Over-Threshold Stories

For any story exceeding threshold, split along the highest-scoring dimension. Re-score after splitting. Repeat until all stories ≤ threshold.

### 4d. Sequence with Dependencies

1. Identify foundation stories (no dependencies)
2. Create first vertical slice (depends on foundation)
3. Plan progressive enhancements (depends on vertical slice)
4. Add integration stories last

For each story, list ALL prerequisite story IDs.

### 4d-insert. Insertion point analysis (insertion_mode only)

**MANDATORY when adding stories to an existing in-progress epic.**

Before choosing where to insert, reason through noise impact (will unresolved state break other stories' quality gates?), unblocking (does this fix something other stories depend on?), and safety (is it purely additive?). State your insertion reasoning before writing files, then use `--insert-before` when calling `generate_sequence.py add-story`:
```bash
python3 ~/.claude/skills/solution-factory/scripts/generate_sequence.py add-story \
  --epic epic-NN --story NN.NNN --insert-before NN.NNN
```

### 4e. Evaluate Against Context

For each story, check the reference inventory:
- Which ADRs apply? → populate `decisions.refs` in story JSON
- Which constraints apply? → populate `constraints.refs`
- Which capsules are relevant? → populate `context.capsules`

Mark `evaluated: true` on each block.

### 4f. Link Wireframes (UX Stories)

If the story is UX-related, check for wireframes:
```bash
python3 ~/.claude/skills/solution-factory/scripts/wireframe_linker.py
```

Present available wireframes and ask user to select one for the story.

---

## Step 5: Scaffold and Write Files

### 5a. Create Epic Directory
```bash
python3 ~/.claude/skills/solution-factory/scripts/scaffold_structure.py epic --epic [N]
```

### 5b. Create Story Directories
For each story:
```bash
python3 ~/.claude/skills/solution-factory/scripts/scaffold_structure.py story --epic [N] --story [NNN]
```

### 5c. Write Story JSON Files

For each story, prepare JSON and generate the story file:
```bash
python3 ~/.claude/skills/solution-factory/scripts/story_templates.py generate-yaml \
  --data '{"id":"NN.NNN","title":"...","epic":"epic-NN","goal":"...","acceptance":[...],"complexity":N,"dependencies":[...],"decisions":[...],"constraints":[...],"context":[...]}' \
  --output '.solution-factory/epics/epic-NN/stories/backlog/NN.NNN/NN.NNN.json'
```

### 5d. Write Epic JSON
```bash
python3 ~/.claude/skills/solution-factory/scripts/story_templates.py generate-epic-yaml \
  --data '{"epic_num":N,"title":"...","description":"...","stories":[...]}' \
  --output '.solution-factory/epics/epic-NN/epic-NN.json'
```

### 5e. Update Sequence
For each story:
```bash
python3 ~/.claude/skills/solution-factory/scripts/generate_sequence.py add-epic --epic epic-NN
python3 ~/.claude/skills/solution-factory/scripts/generate_sequence.py add-story \
  --epic epic-NN --story NN.NNN --dependencies [dep1 dep2]
```

### 5f. Validate
```bash
python3 ~/.claude/skills/solution-factory/scripts/validate_stories.py --epic epic-NN
```

If validation fails, fix issues and re-validate.

---

## Step 6: Present Summary

Display:
```
Epic [NN]: [Title]

Stories: [X]
Total Complexity: [Y]
Per-Story Range: [min]-[max] (threshold: [Z])

Stories:
  NN.001: [Title] (Complexity: N, Deps: None)
  NN.002: [Title] (Complexity: N, Deps: NN.001)
  ...

Context References:
  Decisions: [list of ADR IDs referenced]
  Constraints: [list of constraint IDs referenced]
  Capsules: [list of capsule topics referenced]

Validation: PASSED
```

Ask: **"Review this epic. Approve, or request changes?"**

---

## Step 7: Collaborative Refinement

If user requests changes (add, remove, split, merge, resequence, clarify), apply the change, then:
- Update story JSON files
- Update epic JSON
- Update sequence.json
- Re-validate
- Re-present summary

Repeat until user approves.

---

## Step 8: Interjection Support

To insert a story before an existing story in the sequence:
```bash
python3 ~/.claude/skills/solution-factory/scripts/generate_sequence.py add-story \
  --epic epic-NN --story NN.NNN --dependencies [...] --insert-before NN.NNN
```

The new story gets the **next available ID** (not renumbered). Array position determines execution order.

---

# Error Handling

| Condition | Action |
|-----------|--------|
| No `.solution-factory/` | Tell user to run `/ideate`, STOP |
| No docs/ADRs/constraints | Warn, suggest `/ideate`, allow override |
| Complexity > threshold | MUST split, no exceptions |
| Validation fails | Show errors, fix, re-validate |
| Duplicate story ID | Error from script, assign different ID |
| Dependency cycle | Error from validation, fix deps |
| Draft story's AC restate a dependency's AC (the "test it twin" pattern) | Apply 4a.6 — merge into the dependency or rewrite to target the uncovered gap; never carry forward as a separate story |

---

# Token Efficiency

**Model strategy:**
- **Scripts** (zero tokens): Steps 1, 2, 5 (validate, inventory, scaffold, write files)
- **Sonnet/Opus** (full tokens): Steps 3, 4, 7 (scope analysis, story generation, refinement)

**Context compression:**
- Do NOT load full ADR/constraint content during story generation — just IDs and titles
- Only load full context when evaluating specific story-to-ADR relevance
