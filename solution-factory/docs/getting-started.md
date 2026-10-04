# Getting started with Solution Factory

Solution Factory turns "build this" into a repeatable pipeline:

1. **Capture context** — the decisions and constraints that shape the project.
2. **Break work into stories** — small, scored, dependency-ordered.
3. **Implement stories** — each one planned, tested, reviewed and merged.

Everything it knows about your project lives in a `.solution-factory/` folder
at the project root, as plain files you can read, edit and commit.

## What you need

| Requirement | Why |
|---|---|
| Claude Code | Runs the skills and agents |
| A git repository | Each story gets its own feature branch and is merged when done |
| `python3` on your PATH | Helper scripts do the bookkeeping (standard library only — nothing to install) |
| A way to run your tests | Stories cannot complete until tests pass (unless you turn that off) |

Run Claude Code from the root of the project you want to work on.

## Step 1 — Give it context

Pick the one that matches your situation:

| Your situation | Run | What happens |
|---|---|---|
| New project or a brand-new product area | `/ideate` | A guided Q&A, one question at a time. It challenges your thinking, then writes decisions, constraints and docs. |
| Existing codebase | `/bootstrap` | Scans the code, infers the decisions and constraints already baked in, and asks you to confirm or correct them. |
| You just have an idea and don't want to stop what you're doing | `/ideas add <text>` | Saves the idea in seconds. Come back later to triage and plan it. |

`/ideate` and `/bootstrap` both create `.solution-factory/` with:

- `decisions/` — architecture decision records (ADRs), one per choice
- `constraints/` — hard limits: technology, compliance, integrations
- `docs/` — requirements and architecture summaries
- `context/capsules/` — short topic summaries generated from the above
- `config.json` — your settings (see [configuration.md](configuration.md))

You only do this once per project. Later sessions add to it.

## Step 2 — Create stories

Run `/create-stories` and describe the epic (a body of work — a feature, a
subsystem, a milestone). It will:

- draft thin, end-to-end stories rather than layer-by-layer tasks
- score each story's complexity and split any that are too big
- order them by dependency
- list the files each story expects to touch
- show you the epic and wait for you to add, remove, split or reorder

Nothing is written to your codebase at this stage — only story files under
`.solution-factory/epics/`.

## Step 3 — Implement

Two ways to work, same quality gates either way:

| Mode | Run | Use when |
|---|---|---|
| Interactive, one story at a time | `/solution` | Scope is still fuzzy, or you want to approve each plan |
| Autonomous, a whole epic | `/solution epic epic-01` | Stories are well-formed and you want to walk away |

For each story Solution Factory:

1. explores the code and writes a plan, trimming anything not needed (YAGNI)
2. creates a `feature/<story-id>-<slug>` branch
3. implements the plan in small commits
4. runs tests scoped to the change, then the full suite
5. runs an independent code review and a security review
6. updates any existing docs the change made stale
7. merges into your merge branch and records anything it learned

In interactive mode you approve the plan (step 1) and run
`/solution complete <id>` to finish (step 7). In epic mode you confirm once at
the start and it does the rest.

## A typical first session

```
/bootstrap                 scan the codebase, confirm the findings
/create-stories            describe the first epic, approve the story list
/solution status           see what is ready
/solution                  work the first story interactively
/solution complete 01.001  test, merge and close it
/solution epic epic-01     run the rest of the epic unattended
```

## Good habits

- **Commit `.solution-factory/`.** It is the project's memory. Solution Factory
  commits its own changes there as it goes.
- **Run `/clear` between stories** in interactive mode for a clean context.
- **Check `/solution status`** whenever you are unsure where things stand.
- **Add `help` to any command** (`/solution help`, `/ideas help`, ...) for its
  full reference.
- Solution Factory commits and merges **locally**. It never pushes to a remote;
  that stays under your control.

## Where to go next

- [workflows.md](workflows.md) — which path fits which goal
- [configuration.md](configuration.md) — every setting, with recommended setups
- [commands.md](commands.md) — full command reference
- [agents.md](agents.md) — the specialist agents and when they run
- [project-layout.md](project-layout.md) — what is inside `.solution-factory/`
- [troubleshooting.md](troubleshooting.md) — common problems and fixes
