# Configuration

Settings live in `.solution-factory/config.json` at the project root. The file
is created by `/ideate` or `/bootstrap`.

- **Every key is optional.** Anything you leave out uses the default below.
- **Edit it by hand** at any time; changes take effect on the next command.
- Settings are per project. There is no global configuration.

## Full file with defaults

```json
{
  "complexity": { "threshold": 3 },
  "relevance": { "auto_create": 8, "prompt": 5, "auto_discard": 4 },
  "stories": {
    "require_tests": true,
    "generate_demo_scripts": false,
    "automerge": true,
    "merge_branch": "main",
    "max_stories_per_epic": 10,
    "auto_accept_recommendations": true
  },
  "epic_run": {
    "max_concurrent": 3,
    "shared_paths": [".solution-factory/**"],
    "worktree_setup": null
  },
  "ux": {
    "wireframe_path": null,
    "default_stack": { "framework": "react", "bundler": "vite", "design_system": "chakra ui" }
  }
}
```

## Settings reference

### Stories

| Setting | Default | What it does | Change it when |
|---|---|---|---|
| `stories.merge_branch` | `"main"` | Branch that feature branches are created from and merged into | You use a staging branch (`develop`), or want to keep autonomous work off `main` |
| `stories.automerge` | `true` | Merge automatically on `/solution complete` | Set `false` to be asked before each merge in interactive mode. Epic runs always merge on their own — use `--review-merges` there |
| `stories.require_tests` | `true` | Every story ships the tests for its own behavior, so `/create-stories` never drafts separate "write the tests" stories | Rarely |
| `stories.generate_demo_scripts` | `false` | Generate runnable demo scripts per story under `.solution-factory/tests/` | You want scripted walkthroughs of each story for demos or manual checks |
| `stories.max_stories_per_epic` | `10` | Cap on stories per epic; larger scope becomes several sequential epics | Lower it for tighter review of each epic's plan |
| `stories.auto_accept_recommendations` | `true` | During `/solution epic`, apply the recommended yes/no for borderline discoveries instead of asking | Set `false` if you want to decide each one yourself. Does not affect `/solution complete`, which always asks |

### Epic runs

| Setting | Default | What it does | Change it when |
|---|---|---|---|
| `epic_run.max_concurrent` | `3` | How many stories `/solution epic` works at once, each in its own worktree | Set `1` if tests cannot run in two checkouts at once, or to reduce token use per hour |
| `epic_run.shared_paths` | `[".solution-factory/**"]` | Glob patterns for files every story touches; ignored when checking whether two stories overlap | Add lockfiles, `CLAUDE.md`, changelogs, generated files — otherwise they force stories to run one at a time |
| `epic_run.worktree_setup` | `null` | Shell command run once in each new worktree | A fresh worktree needs installs or untracked files, e.g. `"npm ci && cp ../../.env ."` |

### Complexity

| Setting | Default | What it does | Change it when |
|---|---|---|---|
| `complexity.threshold` | `3` | Highest complexity a story may have. Scores start at 1; anything above the threshold must be split | Raise to 4 only if stories are being split into pieces too small to be useful. Lower values mean smaller, safer stories |

### Discoveries

While implementing, Solution Factory notes new decisions and constraints it
uncovers. On completion each is scored 1–10 for how broadly it applies.

| Setting | Default | What it does |
|---|---|---|
| `relevance.auto_create` | `8` | Score at or above which a discovery is promoted to a decision or constraint automatically |
| `relevance.prompt` | `5` | Score from which you are asked to confirm |
| `relevance.auto_discard` | `4` | Score at or below which a discovery is dropped |

Raise `auto_create` if too many minor findings become permanent records.
Lower it if useful findings keep getting lost.

### UX

Only relevant for projects with a user interface.

| Setting | Default | What it does |
|---|---|---|
| `ux.wireframe_path` | `null` | Folder of wireframes or mockups. When set, `/create-stories` offers to link one to each UI story |
| `ux.default_stack` | react / vite / chakra ui | Front-end framework, bundler and design system. `/bootstrap` detects these; `/ideate` asks |

## Recommended setups

### Solo developer, small project

Defaults work. Consider only:

```json
{ "epic_run": { "max_concurrent": 1 } }
```

if you prefer to watch one story at a time.

### Team with a staging branch and pull-request review

Keep autonomous work off `main` and review before it merges:

```json
{
  "stories": { "merge_branch": "develop", "automerge": false }
}
```

For epic runs add `--review-merges` to approve each merge.

### Shared or production codebase, cautious rollout

```json
{
  "stories": {
    "merge_branch": "develop",
    "automerge": false,
    "auto_accept_recommendations": false
  },
  "epic_run": { "max_concurrent": 1 }
}
```

### JavaScript/TypeScript project running stories concurrently

Fresh worktrees have no `node_modules` and no untracked `.env`:

```json
{
  "epic_run": {
    "max_concurrent": 3,
    "worktree_setup": "npm ci && cp ../../.env .",
    "shared_paths": [".solution-factory/**", "package-lock.json", "CLAUDE.md"]
  }
}
```

The setup command runs inside `.sf-worktrees/slot-N`, so `../../` is the
project root.

### Tests that need exclusive resources

A shared database, fixed ports or a single device:

```json
{ "epic_run": { "max_concurrent": 1 } }
```

### Limited token budget

```json
{
  "stories": { "generate_demo_scripts": false },
  "epic_run": { "max_concurrent": 1 }
}
```

Concurrency does not change the total work, but it spends tokens faster. Keep
`complexity.threshold` at 3 — small stories waste less when something goes
wrong.

### No tests yet

No setting to change. The testing gates run on every story, so make "set up
the test runner" the first story of your first epic — every later story
benefits from it.

## Checking what is in effect

Open `.solution-factory/config.json`. Anything missing from it uses the
default from the table above. The pre-flight summary of `/solution epic` also
prints the settings that matter for the run before asking you to confirm.
