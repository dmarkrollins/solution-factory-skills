---
description: Guided brainstorming and solution ideation — scaffolds .solution-factory/ with decisions, constraints, and docs
argument-hint: [help | project-name]
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit]
---

# Mode of Operation

Guide the user through structured ideation for a project or feature. Challenge their thinking, capture decisions and constraints, then scaffold `.solution-factory/` with everything needed for `/create-stories` to generate epics.

**Pipeline position:** `/ideate` → `/create-stories` → `/solution`

---

# Argument Routing

Parse arguments before doing anything else:
- `help` → print the reference in **Command: help** below and **STOP**. Do not run any scripts.
- anything else (or no arguments) → run the ideation workflow.

---

# Command: help

Print the reference below **verbatim** — it is self-contained, so no scripts or file reads are needed. Do not run any scripts for this command.

```
/ideate — guided brainstorming that scaffolds .solution-factory/ for a new project.
Pipeline: /ideate → /create-stories → /solution

USAGE
  /ideate                Start or resume ideation in the current directory
  /ideate [project-name] Start with a project name pre-filled
  /ideate help           Show this reference

WHAT IT DOES
  Leads you through a structured Q&A — one question at a time — to surface
  decisions, constraints, and requirements, then:
    1. Writes ADRs                → .solution-factory/decisions/
    2. Writes constraints         → .solution-factory/constraints/
    3. Writes docs                → .solution-factory/docs/requirements.md + architecture.md
    4. Generates context capsules → .solution-factory/context/capsules/
    5. Writes config.json         → automerge, merge_branch, complexity threshold, UX stack
    6. Writes manifest.json       → project name, description, schema version

  If .solution-factory/ already exists, ideate asks whether to add a new
  epic's worth of context or start fresh.

WHEN TO USE
  /ideate    — greenfield project or feature, starting from scratch
  /bootstrap — existing codebase you want to analyze and harness automatically

BRAINSTORMING FLOW
  Step 1  Understand the problem (what, who, success criteria)
  Step 2  Explore architecture (runtime, data, API, auth, frontend, testing)
  Step 3  Identify constraints (tech, performance, compliance, integrations)
  Step 4  Confirm scope — ideate challenges assumptions and pushes back on
          scope creep before declaring "enough to scaffold"

WHAT YOU GET
  decisions/    ADRs capturing each architectural choice with context and trade-offs
  constraints/  Constraint files covering tech limits, compliance, integrations
  docs/         requirements.md and architecture.md from the brainstorming session
  context/      capsules used by /solution for automatic context injection per story
  config.json   merge_branch, automerge, complexity threshold, require_tests, UX stack
  manifest.json project metadata (name, description, schema version)

KEY CONFIG VALUES (config.json → stories block)
  merge_branch  branch stories merge back to (default: "main"; set to "develop" for
                staging-based CI or to avoid collisions on shared codebases)
  automerge     merge automatically after /solution complete (default: true)
  require_tests enforce test presence before completion (default: true)

NEXT STEP
  /create-stories — break your first epic into sequenced, dependency-tracked stories
```

---

# Workflow

## Step 1: Initialize or Resume

1. Check if `.solution-factory/` exists in the current project root:
   ```bash
   python3 ~/.claude/skills/solution-factory/scripts/config_loader.py
   ```
   - If exists: inform user that a solution factory already exists. Ask if they want to add a new epic's worth of ideation or start fresh.
   - If not exists: proceed to scaffold.

2. If scaffolding needed:
   ```bash
   python3 ~/.claude/skills/solution-factory/scripts/scaffold_structure.py init
   ```

---

## Step 2: Guided Brainstorming

CRITICAL: Ask questions **ONE AT A TIME**. Never batch questions.

### 2a. Understand the Problem

Start with the big picture:
- "What problem are you solving?"
- "Who is the user/consumer of this?"
- "What does success look like?"

**Challenge the user's assumptions.** Push back on:
- Scope creep ("Do you need that for v1?")
- Premature optimization ("Is that complexity justified?")
- Missing constraints ("What about X?")
- Unclear requirements ("Can you be more specific about Y?")

### 2b. Explore Architecture

Once the problem is clear, dig into technical decisions:
- Runtime architecture (serverless, containers, monolith, etc.)
- Data persistence (database choice, schema approach)
- API design (REST, GraphQL, patterns)
- Authentication/authorization approach
- Frontend stack and UX approach
- Observability and error handling
- Testing strategy

For each topic, discuss trade-offs and capture the decision.

### 2c. Identify Constraints

Surface constraints throughout the conversation:
- Technology constraints (must use X, can't use Y)
- Performance requirements (latency, throughput)
- Compliance/security requirements
- Team/skill constraints
- Timeline/budget constraints
- Integration requirements (existing systems, APIs)

### 2d. Know When to Stop

Continue brainstorming until you can articulate:
- Clear problem statement
- Key architectural decisions (at least 3-5 ADRs)
- Known constraints (at least 2-3)
- Enough context to break work into epics

Tell the user: "I think we have enough to scaffold. Here's what I captured:" and present a summary. Ask for confirmation before proceeding.

---

## Step 3: Create Artifacts

Delegate all artifact writing to the `documentation-writer` agent (**model=haiku** — this is formulaic writing). Provide the agent with:
- Complete list of decisions captured in brainstorming (title, context, decision, consequences for each)
- Complete list of constraints captured (title, type, constraint text, impact, mitigation for each)
- Requirements summary and architecture overview from the conversation
- Starting ADR number (count existing files: `ls .solution-factory/decisions/*.md 2>/dev/null | wc -l`)
- Starting constraint number (same pattern)
- The exact file formats specified below

The agent creates all ADR files (`.solution-factory/decisions/adr-NNN.md`), constraint files (`.solution-factory/constraints/const-NNN.md`), and doc files (`.solution-factory/docs/`).

After the agent returns, verify files were created:
```bash
ls .solution-factory/decisions/ .solution-factory/constraints/ .solution-factory/docs/
```

Then proceed directly to step 3d (capsule generation). Write config.json (3e) and manifest.json (3f) yourself — do not delegate these to the agent since they depend on config values the user will provide.

**ADR format** (files in `.solution-factory/decisions/adr-NNN.md`):

### 3a. ADR Format

For each architectural decision identified, create a file in `.solution-factory/decisions/`:

**Format:** `adr-NNN.md`
```markdown
# adr-NNN: [Decision Title]

**Status:** Accepted
**Date:** [YYYY-MM-DD]

## Context
[Why this decision was needed]

## Decision
[What was decided]

## Consequences
[Trade-offs, implications]
```

### 3b. Constraint Format

For each constraint identified, create a file in `.solution-factory/constraints/`:

**Format:** `const-NNN.md`
```markdown
# const-NNN: [Constraint Title]

**Type:** [technology | performance | compliance | integration | timeline]
**Date:** [YYYY-MM-DD]

## Constraint
[What the constraint is]

## Impact
[How this affects the solution]

## Mitigation
[How to work within this constraint]
```

### 3c. Documentation Format

Create relevant docs in `.solution-factory/docs/`:
- `requirements.md` — captured requirements from brainstorming
- `architecture.md` — high-level architecture overview
- Additional docs as needed based on conversation

### 3d. Generate Capsules

After writing ADRs and constraints:
```bash
python3 ~/.claude/skills/solution-factory/scripts/capsule_generator.py
```

### 3e. Create config.json

Ask the user for project-specific configuration values:
- Complexity threshold (default: 3)
- Whether tests are required (default: true)
- Wireframe path (if UX work is involved)
- Default stack (framework, bundler, design system)

Write `.solution-factory/config.json`:
```json
{
    "complexity": {
        "threshold": 3
    },
    "relevance": {
        "auto_create": 8,
        "prompt": 5,
        "auto_discard": 4
    },
    "stories": {
        "require_tests": true,
        "generate_demo_scripts": false,
        "automerge": true,
        "merge_branch": "main",
        "max_stories_per_epic": 10
    },
    "ux": {
        "wireframe_path": null,
        "default_stack": {
            "framework": "react",
            "bundler": "vite",
            "design_system": "chakra ui"
        }
    }
}
```

Only include `ux` block if the user has UX work. Adjust defaults based on conversation.

### 3f. Create manifest.json

```json
{
    "schema_version": "1.0.0",
    "plugin_name": "solution-factory",
    "plugin_version": "1.0.0",
    "created_at": "[timestamp]",
    "updated_at": "[timestamp]",
    "compatible_claude_code": ">=2.0.0",
    "project_name": "[from user]",
    "description": "[from brainstorming]"
}
```

---

## Step 4: Present Summary

Display what was created:

```
Solution Factory initialized for: [Project Name]

Decisions (ADRs):
- adr-001: [title]
- adr-002: [title]
...

Constraints:
- const-001: [title]
- const-002: [title]
...

Context Capsules Generated:
- [topic-1]
- [topic-2]
...

Documentation:
- docs/requirements.md
- docs/architecture.md

Next step: Run /create-stories to break your first epic into stories.
```

---

# Best Practices

## Brainstorming Quality
- **Challenge, don't accept** — push back on vague requirements
- **One question at a time** — never overwhelm with multiple questions
- **Summarize before moving on** — "So what I'm hearing is..." before shifting topics
- **Capture as you go** — don't wait until the end to write things down mentally
- **Know your exit** — stop when you have enough for epics, don't boil the ocean

## ADR Quality
- Decisions should be **specific and actionable** ("Use PostgreSQL for user data" not "Pick a database")
- Always include **consequences** — every decision has trade-offs
- Keep them **concise** — 5-10 sentences total, not essays

## Token Efficiency
- Use scripts for all file I/O
- Don't re-read files you just wrote
- Summarize rather than echo full content back to user
