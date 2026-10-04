# Agents

Solution Factory ships ten specialist agents. The commands call them for you —
you never need to invoke one directly, though you can.

## Who does what

| Agent | Role | Called by | Can edit code |
|---|---|---|---|
| `technical-architect` | Assesses feasibility of one idea against existing decisions and constraints, trims scope, drafts the technical approach | `/ideas plan` | No |
| `backend-developer` | Implements APIs, services, models, workers, jobs | `/solution` (implementation) | Yes |
| `frontend-developer` | Implements components, pages, styles, hooks | `/solution` (implementation) | Yes |
| `database-engineer` | Implements schema files and migrations | `/solution` (implementation) | Yes |
| `devops-engineer` | Implements CI config, Dockerfiles, infrastructure | `/solution` (implementation) | Yes |
| `test-engineer` | Finds the project's test commands, runs changed-file tests then the full suite, diagnoses failures | `/solution` (testing) | Yes |
| `code-reviewer` | Reviews the story's diff against acceptance criteria, decisions, constraints and code quality | `/solution` (review) | No |
| `security-engineer` | Reviews the diff for vulnerabilities; returns "not applicable" when no attack surface is touched | `/solution` (review) | No |
| `documentation-writer` | Writes the initial decisions and docs; later updates existing docs made stale by a story | `/ideate`, `/solution` (docs cleanup) | Yes |
| `story-worker` | Implements one whole story unattended — plan, code, tests — and hands back a green branch | `/solution epic` | Yes |

## How implementation is routed

In interactive mode, `/solution` picks the implementer from the kinds of files
in the plan:

| Mostly these files | Agent |
|---|---|
| API routes, services, models, workers, jobs | `backend-developer` |
| Components, pages, styles, hooks, UI utilities | `frontend-developer` |
| Schema files and migrations only | `database-engineer` |
| CI config, Dockerfiles, infrastructure | `devops-engineer` |
| A real mix of UI and API work | No agent — implemented inline in the main session |

## How epic runs divide the work

In `/solution epic`, each story is handled by two parties:

- A **`story-worker`** implements and tests the story in its own separate
  context, then returns a short result: implemented or blocked. Its working
  context is thrown away, which keeps long runs from filling up.
- The **main session** then runs the independent reviewers —
  `code-reviewer`, `security-engineer`, and `documentation-writer` — and
  completes and merges the story.

This split means the code is never reviewed by the same agent that wrote it.
If a reviewer asks for rework, the worker is sent back to the same branch with
the findings.

## Other agents used

`/bootstrap` and parts of `/solution` use Claude Code's built-in read-only
`Explore` agent for codebase scanning, and `/create-stories` uses the built-in
`Plan` agent to draft stories. These are part of Claude Code, not this plugin.

## Models

Agents run on Sonnet by default. Read-only codebase scanning uses Haiku to
save tokens. Bookkeeping — status, sequencing, validation, moving story
folders — is done by scripts and costs no tokens at all.

## Name clashes

Installed as a plugin, every agent name carries the plugin's prefix, so these
agents never collide with agents of your own that happen to share a name (a
personal code reviewer, say). Solution Factory always uses its own.
