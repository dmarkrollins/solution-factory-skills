# Solution Factory

Structured software delivery for Claude Code.

Solution Factory gives Claude a repeatable way to build software: capture the
decisions and constraints that shape a project, break work into small scored
stories, then implement each story through planning, testing, code review and
security review — one at a time with you, or a whole epic unattended.

```
/ideate or /bootstrap  →  /create-stories  →  /solution
                /ideas  →  /create-stories --from-idea
```

## Install

In Claude Code:

```
/plugin marketplace add 6thcents/claude-plugins
/plugin install solution-factory@6thcents
```

Or from a terminal:

```
claude plugin marketplace add 6thcents/claude-plugins
claude plugin install solution-factory@6thcents
```

**Requirements:** a git repository, and Python 3 available as `python3`
(standard library only — nothing else to install).

## Quick start

Open Claude Code in your project and run:

| Step | New project | Existing codebase |
|---|---|---|
| 1. Capture context | `/ideate` | `/bootstrap` |
| 2. Create stories | `/create-stories` | `/create-stories` |
| 3. Implement | `/solution` | `/solution` |

Then, once you trust the flow, run a whole epic unattended:

```
/solution epic epic-01
```

Not sure where to begin? Ask:

```
/guide setup
```

or just ask Claude in plain language — "how should I set up Solution Factory
for this repo?" The guide reads your project and recommends a path.

## Commands

| Command | Purpose |
|---|---|
| `/ideate` | Guided Q&A to design a new project and record its decisions and constraints |
| `/bootstrap` | Scan an existing codebase and infer its decisions and constraints |
| `/ideas` | Capture, triage and plan single ideas before they become an epic |
| `/create-stories` | Break an epic into small, scored, dependency-ordered stories |
| `/solution` | Implement stories with planning, testing and review gates; `epic` runs a whole epic unattended |
| `/guide` | Answers questions and walks you through setup and configuration |

Add `help` to any command for its full reference.

## What you get

- **Project memory.** Decisions, constraints and docs live in
  `.solution-factory/` as plain files, committed with your code. Every story
  is planned and reviewed against them.
- **Small stories by design.** Each story is scored for complexity and split
  if it is too big.
- **Quality gates on every story.** A written plan, tests scoped to the change
  and the full suite, an independent code review and a security review.
- **Autonomous epic runs.** One confirmation, then stories are implemented,
  reviewed and merged unattended — several at a time when they touch
  different files.
- **Learning as it goes.** Decisions and constraints uncovered during
  implementation are recorded and fed into later stories.
- **Low token overhead.** Bookkeeping is done by scripts, not by the model.

Solution Factory commits and merges locally on feature branches. It never
pushes to a remote.

## Configuration

Settings are per project, in `.solution-factory/config.json`. The defaults
work for most projects; the ones most worth knowing:

| Setting | Default | Meaning |
|---|---|---|
| `stories.merge_branch` | `main` | Branch stories are merged into |
| `stories.automerge` | `true` | Merge without asking on completion |
| `epic_run.max_concurrent` | `3` | Stories an epic run works on at once |
| `epic_run.worktree_setup` | none | Command to prepare each worktree, e.g. `npm ci` |
| `complexity.threshold` | `3` | Largest story allowed before it is split |

Run `/guide configure` for a walkthrough, or see
[docs/configuration.md](docs/configuration.md).

## Documentation

- [Getting started](docs/getting-started.md)
- [Choosing a workflow](docs/workflows.md)
- [Configuration](docs/configuration.md)
- [Command reference](docs/commands.md)
- [Agents](docs/agents.md)
- [The .solution-factory folder](docs/project-layout.md)
- [Troubleshooting](docs/troubleshooting.md)

## What is in the plugin

| Folder | Contents |
|---|---|
| `skills/` | The six commands above |
| `agents/` | Ten specialist agents: implementers, reviewers, a story worker and a technical architect |
| `scripts/` | Python helpers for status, sequencing, validation and story bookkeeping |
| `docs/` | The reference documentation |

## License

MIT — see [LICENSE](LICENSE).
