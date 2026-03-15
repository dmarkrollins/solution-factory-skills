---
description: Break an epic into sequenced, complexity-scored stories with YAML definitions and dependency tracking
argument-hint: [--epic-title="title"]
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit]
---

# Mode of Operation

Break down a brainstormed epic into sequenced stories stored as JSON files in `.solution-factory/`. Each story is complexity-scored, dependency-tracked, and evaluated against existing ADRs/constraints/capsules.

**Pipeline position:** `/ideate` → **`/create-stories`** → `/solution`

**Key principles:**
- Stories MUST have complexity ≤ threshold from `config.json` (default: 3)
- Vertical slicing — not horizontal layers
- Story execution order = array position in `sequence.json`, NOT numerical sort
- Story IDs are numeric only (never letter suffixes)

---

# Workflow

## Step 1: Validate Prerequisites

```bash
python3 ~/.claude/skills/solution-factory/scripts/config_loader.py
```

- If `.solution-factory/` doesn't exist → tell user to run `/ideate` first, STOP
- Extract complexity threshold from config

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

### 4a. Draft Stories

Break the epic into logical stories. Think:
- **Foundation first** — models, schemas, core setup
- **Vertical slices** — thin working features end-to-end
- **Progressive enhancement** — happy path → validation → error handling → edge cases

Aim for 5-15 stories per epic.

### 4b. Score Complexity

Apply the complexity rubric to each story:

| Dimension | 0 | 1 | 2 | 3 |
|-----------|---|---|---|---|
| **Change Surface** | Single file | 2-3 files, same layer | Multiple layers | Full stack |
| **Implementation** | Copy pattern | New file, familiar pattern | New patterns | New architecture |
| **Uncertainty** | Crystal clear | Minor unknowns | — | Significant unknowns |
| **Scope** | 1-2 criteria | 3-4 criteria | — | 5+ criteria |

Note: Uncertainty and Scope max at 2, not 3.

**Total = sum of all dimensions (0-10). Must be ≤ threshold (default 3).**

### 4c. Split Over-Threshold Stories

For any story exceeding threshold:

- **High Scope** → split by acceptance criteria groupings
- **High Implementation** → split by layers or phases
- **High Uncertainty** → create spike/research story first
- **High Change Surface** → split by system boundary

Re-score after splitting. Repeat until all stories ≤ threshold.

### 4d. Sequence with Dependencies

1. Identify foundation stories (no dependencies)
2. Create first vertical slice (depends on foundation)
3. Plan progressive enhancements (depends on vertical slice)
4. Add integration stories last

For each story, list ALL prerequisite story IDs.

### 4d-insert. Insertion point analysis (insertion_mode only)

**MANDATORY when adding stories to an existing in-progress epic.**

Before choosing where to insert, reason through:

1. **Noise impact** — Will the new story's unresolved state produce compiler errors, test failures, or misleading output during other stories' quality gates? If yes, it should run **before** those stories.
2. **Unblocking** — Does the new story fix something that other backlog stories depend on or assume is already working? If yes, insert before the earliest affected story.
3. **Safety** — Is it purely additive with no side effects on existing backlog work? If yes, appending last is fine.

Apply the rule:
- **Noisy or unblocking** → find the earliest backlog story that would be affected, insert before it
- **Neutral** → append after current backlog tail

Read the backlog from `sequence.json` and explicitly state your insertion reasoning before writing files. Example:
```
Insertion analysis:
  New story fixes: TypeScript compiler errors in auth/ and processors/
  Affected backlog stories: all (tsc --noEmit runs on every story)
  Earliest affected: 01.002 (next in sequence)
  Decision: insert before 01.002
```

Use `--insert-before` when calling `generate_sequence.py add-story`:
```bash
python3 ~/.claude/skills/solution-factory/scripts/generate_sequence.py add-story \
  --epic epic-NN --story NN.NNN --insert-before NN.NNN
```

### 4e. Evaluate Against Context

For each story, check the reference inventory:
- Which ADRs apply? → populate `decisions.refs` in story YAML
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

If user requests changes, support:

| Action | What Happens |
|--------|-------------|
| **Add story** | Draft, score, insert into sequence |
| **Remove story** | Remove, update downstream deps |
| **Split story** | Apply splitting strategy, re-score, re-sequence |
| **Merge stories** | Combine, re-score, verify ≤ threshold |
| **Adjust complexity** | Re-evaluate with rubric |
| **Resequence** | Rearrange, update deps |
| **Clarify** | Expand descriptions, acceptance criteria |

After each change:
- Update story YAML files
- Update epic YAML
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

---

# Token Efficiency

**Three-tier model strategy:**
- **Scripts** (zero tokens): Steps 1, 2, 5 (validate, inventory, scaffold, write files)
- **Haiku subagents** (low tokens): Codebase exploration for epic context gathering
- **Sonnet/Opus** (full tokens): Steps 3, 4, 7 (scope analysis, story generation, refinement)

**Context compression:**
- Do NOT load full ADR/constraint content during story generation — just IDs and titles
- Only load full context when evaluating specific story-to-ADR relevance
