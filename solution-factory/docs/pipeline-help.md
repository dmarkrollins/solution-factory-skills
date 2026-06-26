## SOLUTION FACTORY PIPELINE

  /ideate or /bootstrap  →  /create-stories  →  /solution

  /ideate          Greenfield: Q&A-driven brainstorming to design a project from scratch
  /bootstrap       Brownfield: scans an existing codebase and infers all context
  /create-stories  Breaks an epic into complexity-scored, dependency-tracked stories
  /solution        Implements stories with planning gates, tests, reviews, and merges

## .SOLUTION-FACTORY/ STRUCTURE

  decisions/    ADRs capturing architectural choices with context and trade-offs
  constraints/  Constraint files for tech limits, compliance, and integrations
  docs/         Architecture and requirements docs from ideation or bootstrap
  context/      Capsules auto-injected per story for architectural context
  epics/        Epic and story JSON files, plans, and completion artifacts
  tests/        Demo scripts generated per story (when generate_demo_scripts=true)
  config.json   Project-level configuration (see KEY CONFIG VALUES below)
  manifest.json Project metadata (name, description, schema version)
  sequence.json Master execution ledger — story order, status, and dependencies

## KEY CONFIG VALUES (config.json)

  stories.merge_branch           Branch stories merge to after /solution complete
                                 Default: "main" — set to "develop" for staging-based CI
                                 or to avoid collisions on shared codebases
  stories.automerge              Merge automatically on /solution complete (default: true)
                                 Set false to require manual approval per story
  stories.require_tests          Enforce tests before a story can complete (default: true)
  stories.generate_demo_scripts  Generate demo scripts per story (default: false)
  stories.max_stories_per_epic   Per-epic story cap — scope beyond the cap splits into
                                 sequential epics rather than dropping work (default: 10)
  complexity.threshold           Max complexity score per story (default: 3)
                                 Stories over threshold are split — no exceptions
  relevance.auto_create          Discovery relevance score that triggers auto-promotion
                                 to a new ADR or constraint (default: 8)
  relevance.prompt               Score range requiring manual confirmation (default: 5)
  relevance.auto_discard         Score at or below which discoveries are discarded (default: 4)
