---
description: Capture, triage, and plan a lightweight backlog of feature/bug ideas before they become an epic
argument-hint: <add|list|show|discard|triage|plan|plan-check|help> [idea-id]
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit]
---

# Mode of Operation

Own the pre-epic idea backlog: capture a raw idea the moment it occurs to you, triage it later, and when you're ready to act on it, turn it into a `plan.md` with a defined technical approach that `/create-stories` can promote straight into a real epic.

**Pipeline position:** `/ideas` (capture → triage → plan) → `/create-stories --from-idea` → `/solution`

This sits alongside, not instead of, the existing `/ideate → /create-stories → /solution` flow — `/ideate` is for scaffolding a whole project's worth of context up front; `/ideas` is for jotting a single feature/bug as it comes to you and fleshing it out later, once you actually want to build it.

Parse arguments to determine subcommand. Default to `list` if no arguments.

---

# Subcommand Routing

```
/ideas help                → Show this command reference
/ideas                     → list (default)
/ideas add [text]          → Capture a new idea
/ideas list [--state]      → List ideas with optional state filter
/ideas show <id>           → Show an idea's full detail (and plan, if it has one)
/ideas discard <id>        → Discard an idea
/ideas triage              → Review raw ideas one at a time: keep, discard, or merge
/ideas plan <id>           → Interview + draft a technical-approach plan for one idea
/ideas plan-check <id>     → Re-run the plan lint standalone
```

---

# Command: help

1. Print the skill-specific block below verbatim.
2. Read `~/.claude/skills/solution-factory/docs/pipeline-help.md` using the Read tool and print its full contents verbatim immediately after, with no gap between the two blocks.

Do not run any scripts. Do not summarize or paraphrase either block.

```
/ideas — capture, triage, and plan a lightweight backlog of ideas.

USAGE
  /ideas add [text]     Capture an idea (asks one question if text omitted)
  /ideas list           List ideas (add --state raw|triaged|planning|planned|
                        promoted|discarded to filter)
  /ideas show <id>      Show an idea's full detail, including its plan if planned
  /ideas discard <id>   Discard an idea
  /ideas triage         Batch-review raw ideas: keep, discard, or merge
  /ideas plan <id>      Interview + draft a technical-approach plan.md for one idea
  /ideas plan-check <id> Re-run the plan lint standalone (no state change)
  /ideas help           Show this reference

WHAT IT DOES
  add        Allocates IDEA-NNN under .solution-factory/ideas/ and writes a
             raw idea.md. Works even before .solution-factory/ has been
             scaffolded — this is meant to be fast, not a design session.
  triage     Walks raw ideas one at a time. Keep -> state becomes triaged.
             Discard -> state becomes discarded. Merge -> folds into another
             idea and discards the source.
  plan       Requires a fully scaffolded .solution-factory/ (run /ideate or
             /bootstrap first if it isn't). Interviews you about the idea,
             delegates technical-approach drafting to the technical-architect
             agent (feasibility, design decisions, YAGNI trimming — not
             stories), then writes the confirmed draft into plan.md's
             Technical Approach section.
  plan-check Checks plan.md has a non-empty '## Technical Approach' section and
             warns on phasing / size-estimate / ship-order language (that is
             /create-stories's job). Pure lint, never blocks — you decide
             whether to act on warnings.

IDEA STATE MACHINE
  raw -> triaged -> planning -> planned -> promoted
  discarded is reachable from any state except promoted.
  Only idea_store.py ever writes idea.md's frontmatter (single writer) —
  /create-stories trusts state == planned without re-checking anything.

PLAN.MD TECHNICAL APPROACH FORMAT (hand-edited, freeform prose)
  ## Technical Approach

  Feasibility notes, what to build (named against real files/patterns in
  this codebase), what to deliberately leave out (YAGNI), key design
  decisions, and open risks/questions.

  This is NOT a story list — /create-stories --from-idea runs its own
  Plan-agent drafting step using this section as grounding context, then
  applies its normal vertical-slicing, complexity-scoring, and dependency-
  sequencing rubric to produce the actual stories.

NEXT STEP
  /create-stories --from-idea IDEA-NNN   promote a planned idea into a real
                                          epic (once /ideas plan has set its
                                          state to planned)
```

---

# Command: add

1. If idea text was passed as an argument, use it directly. Otherwise ask **one question**: "What's the idea?" Do not interview further — capture is meant to be fast.
2. Split the answer into a short title (first sentence or first ~8 words) and the rest as body, if there's more than a one-liner.
3. ```bash
   python3 ~/.claude/skills/solution-factory/scripts/idea_store.py add --title "<title>" --body "<body>" --root .
   ```
4. Capture the idea as the user described it — do not add "suggested phasing", size estimates, or a delivery order to the body. Splitting work is `/create-stories`'s job.
5. Report the allocated ID: "Captured as IDEA-NNN."

---

# Command: list

```bash
python3 ~/.claude/skills/solution-factory/scripts/idea_store.py list --root . [--state <state>]
```

Present as a table: ID, title, state, last updated.

---

# Command: show

```bash
python3 ~/.claude/skills/solution-factory/scripts/idea_store.py show <id> --root .
```

Print the idea's title, state, body, and plan.md contents if present.

---

# Command: discard

```bash
python3 ~/.claude/skills/solution-factory/scripts/idea_store.py discard <id> --root . [--reason "..."]
```

If the idea is already `promoted`, the script errors — report that plainly; a promoted idea's epic is the source of truth now, not the idea backlog.

---

# Command: triage

1. ```bash
   python3 ~/.claude/skills/solution-factory/scripts/idea_store.py list --root . --state raw
   ```
2. For each raw idea, one at a time: show its title + body, ask **"Keep, discard, or merge?"**
   - **Keep** → `idea_store.py set-state <id> --state triaged --root .`
   - **Discard** → `idea_store.py discard <id> --root . --reason "<why, if given>"`
   - **Merge** → ask which idea to merge into, append a short merge note to the target idea's body (via Read + Edit on its `idea.md`), then discard the source with `--reason "merged into <target-id>"`.
3. Move to the next raw idea. Stop when none remain.

---

# Command: plan

## 1. Validate Prerequisites

```bash
python3 ~/.claude/skills/solution-factory/scripts/config_loader.py
```

- If `.solution-factory/` doesn't exist (only `.solution-factory/ideas/` does) → tell the user to run `/ideate` or `/bootstrap` first, STOP. Planning needs ADR/constraint/capsule context that only a scaffolded project has.
- ```bash
  python3 ~/.claude/skills/solution-factory/scripts/idea_store.py show <id> --root .
  ```
  If the idea doesn't exist, or its state is `discarded` or `promoted`, stop with a clear error (a promoted idea already has an epic; re-plan there instead).

## 2. Build Reference Inventory

Same lightweight approach as `/create-stories` step 2 — IDs and titles only, not full content:
```bash
for f in .solution-factory/decisions/*.md; do head -1 "$f" 2>/dev/null; done
for f in .solution-factory/constraints/*.md; do head -1 "$f" 2>/dev/null; done
ls .solution-factory/context/capsules/ 2>/dev/null
```

## 3. Advance State and Interview

1. ```bash
   python3 ~/.claude/skills/solution-factory/scripts/idea_store.py set-state <id> --state planning --root .
   ```
2. Interview the user **one question at a time** about this one idea — problem, scope, constraints specific to it (same discipline as `/ideate` §2, scaled to a single feature, not a whole project). Stop once you can articulate a clear goal and rough scope; don't over-interview a small idea.

## 4. Delegate Technical Approach to `technical-architect`

Use the Agent tool with `subagent_type=technical-architect`, **model=sonnet**. Provide:
- Idea title + body (the raw capture)
- The interview transcript
- The ADR/constraint/capsule reference inventory (IDs + titles)

The agent returns a feasibility read plus a technical approach writeup (what to build, what to leave out per YAGNI, key design decisions, risks/open questions). It does **not** draft stories, assign complexity scores, or write files — that sizing work belongs to `/create-stories --from-idea` later, once the epic exists.

**No delivery planning (applies to the agent's draft, to `plan.md`, and to you).** Repeat this to the agent verbatim in its prompt:

```
Describe ONE technical design as a whole. Do not split it into phases,
milestones, stages, releases, or "ships first/last". Do not estimate size
("epic-sized", "small", "large") or say how many stories or epics it needs.
Do not present build order as a sequence of deliverables. A design fact like
"the resolver must exist before handlers can call it" is fine as a note on
that component, never as a delivery order. Organize by component or concern
(data model, access checks, email, UI, docs, risks). If a heading contains
"Phase", "Step N", "Milestone" or "Sprint", rewrite it. Splitting the work
into deliverables is /create-stories's job alone.
```

## 5. Review and Write

1. Review the draft with the user — challenge scope creep, confirm the YAGNI cuts make sense, resolve any flagged risks/open questions you can resolve now. Before writing, strip any phasing, size estimates ("epic-sized"), "ships first/last" or delivery-order language from the draft. The same rule holds for any later edit to `plan.md` you make at the user's request: never introduce it.
2. Once confirmed, write (or create, if this is the idea's first plan) `.solution-factory/ideas/<id>/plan.md` with a `## Technical Approach` section containing the agent's feasibility notes and approach writeup, via the Write/Edit tool. This file stays hand-editable afterward — the user can tweak it directly before promoting.

## 6. Lint and Confirm

```bash
python3 ~/.claude/skills/solution-factory/scripts/idea_plan_check.py plan-check <id> --root .
```

- If `warnings[]` is non-empty (section missing or empty, or phasing / size-estimate / ship-order language found) or `technical_approach_present` is `false`, fix `plan.md` before proceeding — `/create-stories --from-idea` needs real content here to ground its own story-drafting step.
- Once clean, ask the user to confirm the plan is ready.
3. ```bash
   python3 ~/.claude/skills/solution-factory/scripts/idea_store.py set-state <id> --state planned --root .
   ```
4. Tell the user: "Ready — run `/create-stories --from-idea <id>` to promote this into an epic." Note that promotion will run `/create-stories`'s own story-drafting step using this technical approach as context — this plan does not itself contain final stories.

---

# Command: plan-check

```bash
python3 ~/.claude/skills/solution-factory/scripts/idea_plan_check.py plan-check <id> --root .
```

Print `technical_approach_present` and any `warnings[]`. No state change — safe to re-run any time.

---

# Error Handling

| Condition | Action |
|-----------|--------|
| `add` with no `.solution-factory/` at all | Auto-create `.solution-factory/ideas/` only, proceed normally |
| `plan` with no `.solution-factory/` (full scaffold) | Tell user to run `/ideate`/`/bootstrap`, STOP |
| `plan`/`discard` on a `promoted` idea | Error — the idea's epic is the source of truth now |
| `plan-check` reports the Technical Approach section missing/empty | Fix `plan.md` before `set-state planned` |
| `idea_store.py` command errors | Print the error, do not retry blindly |

---

# Token Efficiency

- Use scripts for all file I/O and state transitions — never hand-edit `idea.md` frontmatter directly.
- Reference inventory in `plan`: IDs and titles only, not full ADR/constraint content.
- `add`, `list`, `show`, `discard` need no subagent — they're pure script calls.
