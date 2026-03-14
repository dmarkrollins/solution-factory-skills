---
description: Analyze an existing codebase and scaffold .solution-factory/ with inferred decisions, constraints, and capsules
argument-hint: [--root=path]
allowed-tools: [Read, Glob, Grep, Bash, Write, Edit, Agent]
---

# Mode of Operation

Reverse-engineer architectural context from an existing codebase. Scan code, infer decisions and constraints, scaffold `.solution-factory/`, and present findings for user review.

**Use when:** You have an existing project and want to harness it with Solution Factory.
**Contrast with `/ideate`:** Ideate is greenfield (Q&A-driven). Bootstrap is brownfield (analysis-driven).

**Pipeline position:** **`/bootstrap`** → `/create-stories` → `/solution`

---

# Workflow

## Step 1: Pre-flight Check

Check if `.solution-factory/` already exists:
```bash
python3 ~/.claude/skills/solution-factory/scripts/config_loader.py
```

- If exists → **WARN**: ".solution-factory/ already exists. This will merge new findings into existing context. Continue?" Wait for confirmation.
- If not exists → proceed to scaffold.

Scaffold the directory structure:
```bash
python3 ~/.claude/skills/solution-factory/scripts/scaffold_structure.py init
```

---

## Step 2: Codebase Analysis

Use **3 parallel Haiku subagents** to scan the codebase efficiently. Each agent gets a focused task and returns structured findings.

### Agent 1: Stack & Infrastructure Analysis

Use Agent tool with subagent_type=Explore, **model=haiku**:

Prompt:
```
Analyze this codebase for technology stack and infrastructure decisions. Return a JSON object with:

1. "runtime": {language, version, framework, bundler}
2. "dependencies": [list of key dependencies with purpose]
3. "infrastructure": {hosting, database, caching, messaging, storage}
4. "configuration": {env vars found, config patterns}
5. "build_system": {build tool, scripts, CI/CD}

Look at: package.json, requirements.txt, go.mod, Cargo.toml, Dockerfile, docker-compose, serverless configs, CDK/SST/Terraform files, .env.example, Makefile, CI configs (.github/workflows, .gitlab-ci).

Be thorough — check all config files at the project root and in common locations.
```

### Agent 2: Architecture & Patterns Analysis

Use Agent tool with subagent_type=Explore, **model=haiku**:

Prompt:
```
Analyze this codebase for architecture patterns and design decisions. Return a JSON object with:

1. "architecture_style": monolith|microservices|serverless|hybrid
2. "api_design": {style: REST|GraphQL|gRPC, patterns: [middleware, auth, validation]}
3. "data_patterns": {orm, migrations, query patterns, data access layer}
4. "auth_pattern": {strategy, session management, token type}
5. "code_organization": {structure pattern, module boundaries, naming conventions}
6. "error_handling": {strategy, patterns found}
7. "testing_patterns": {framework, coverage approach, test organization}

Look at: src/ or app/ directory structure, route definitions, middleware, models/schemas, test files, error handling patterns.
```

### Agent 3: Constraints & Boundaries Analysis

Use Agent tool with subagent_type=Explore, **model=haiku**:

Prompt:
```
Analyze this codebase for constraints and boundaries. Return a JSON object with:

1. "language_constraints": {min version, module system (CJS/ESM), strict mode}
2. "dependency_constraints": [pinned versions, peer deps, known conflicts]
3. "platform_constraints": {OS requirements, cloud provider lock-in, browser support}
4. "security_constraints": {auth requirements, CORS config, CSP headers, secrets management}
5. "performance_constraints": {bundle size limits, lazy loading, caching strategy}
6. "integration_constraints": [external APIs, third-party services, webhooks]
7. "conventions": {linting rules, formatting, commit conventions, PR templates}

Look at: .eslintrc, .prettierrc, tsconfig.json, security configs, CORS setup, .env.example, API integrations, package.json engines field.
```

**Launch all 3 agents in parallel** — they are independent and read-only.

---

## Step 3: Synthesize Findings

Once all 3 agents return, synthesize their outputs into ADRs and constraints.

### 3a. Generate ADRs

For each significant decision inferred from the analysis, create an ADR.

**Typical ADRs from bootstrap (aim for 5-15):**

| Pattern Found | ADR Title |
|--------------|-----------|
| Express in package.json | Use Express as HTTP framework |
| PostgreSQL connection | Use PostgreSQL for primary data store |
| JWT tokens in auth middleware | Use JWT for API authentication |
| React in dependencies | Use React for frontend UI |
| TypeScript config present | Use TypeScript for type safety |
| Jest/Vitest in test config | Use [framework] for testing |
| Docker/docker-compose | Use Docker for local development |
| SST/CDK config | Use [tool] for infrastructure as code |
| ESLint + Prettier | Enforce code style with ESLint and Prettier |
| Monorepo structure | Organize as monorepo with [tool] |

Write each ADR to `.solution-factory/decisions/adr-NNN.md`:
```markdown
# adr-NNN: [Decision Title]

**Status:** Accepted (inferred from codebase)
**Date:** [today]
**Source:** Bootstrap analysis

## Context
[Why this technology/pattern was likely chosen — infer from usage patterns]

## Decision
[What is being used and how]

## Consequences
[Trade-offs, implications, lock-in]
```

### 3b. Generate Constraints

For each constraint identified, create a constraint file.

**Typical constraints from bootstrap (aim for 3-8):**

| Finding | Constraint |
|---------|-----------|
| `"engines": {"node": ">=18"}` | Node.js 18+ required |
| `"type": "module"` | ESM modules only |
| AWS SDK in deps | AWS cloud provider dependency |
| CORS config | Cross-origin access rules |
| `.env.example` vars | Required environment configuration |
| TypeScript strict mode | Strict type checking enforced |

Write each to `.solution-factory/constraints/const-NNN.md`:
```markdown
# const-NNN: [Constraint Title]

**Type:** [technology | performance | compliance | integration]
**Date:** [today]
**Source:** Bootstrap analysis

## Constraint
[What the constraint is]

## Impact
[How this affects future work]

## Mitigation
[How to work within this constraint]
```

### 3c. Write Documentation

Create `.solution-factory/docs/architecture.md` summarizing the codebase architecture:
- High-level overview
- Key components and their relationships
- Data flow
- API structure
- Technology stack summary

### 3d. Generate Capsules

```bash
python3 ~/.claude/skills/solution-factory/scripts/capsule_generator.py
```

### 3e. Create config.json

Infer configuration from the codebase analysis:

```bash
# Write config.json with inferred values
```

Populate based on findings:
- `ux.wireframe_path` — if wireframe/mockup files found
- `ux.default_stack` — from detected frontend framework
- Other fields use defaults

### 3f. Create manifest.json

```json
{
    "schema_version": "1.0.0",
    "plugin_name": "solution-factory",
    "plugin_version": "1.0.0",
    "created_at": "[timestamp]",
    "updated_at": "[timestamp]",
    "compatible_claude_code": ">=2.0.0",
    "project_name": "[inferred from package.json/config or ask user]",
    "description": "[inferred from README or ask user]"
}
```

---

## Step 4: Present Findings for Review

Display a structured summary:

```
══════════════════════════════════════════════════════
Bootstrap Complete: [Project Name]
══════════════════════════════════════════════════════

Stack Detected:
  Runtime: [language] [version] + [framework]
  Frontend: [framework] + [bundler]
  Database: [database]
  Infrastructure: [hosting/IaC]

Decisions Created ([N] ADRs):
  adr-001: [title]
  adr-002: [title]
  ...

Constraints Identified ([N]):
  const-001: [title]
  const-002: [title]
  ...

Capsules Generated ([N]):
  [topic-1]
  [topic-2]
  ...

Documentation:
  docs/architecture.md

══════════════════════════════════════════════════════

Review these findings. You can:
1. Approve as-is
2. Request corrections (wrong inferences, missing decisions)
3. Add additional decisions or constraints I missed

What would you like to adjust?
```

---

## Step 5: Corrections

If user requests changes:

- **Wrong inference** → update or delete the ADR/constraint file
- **Missing decision** → create new ADR (ask one clarifying question at a time)
- **Missing constraint** → create new constraint
- **Wrong stack detail** → update config.json and relevant ADRs

After corrections:
- Regenerate capsules:
  ```bash
  python3 ~/.claude/skills/solution-factory/scripts/capsule_generator.py
  ```
- Re-present summary
- Repeat until user approves

---

## Step 6: Finalize

Once approved:

```
.solution-factory/ initialized from existing codebase.

Next steps:
  /create-stories — break your first epic into stories
  /solution status — view project status

The architectural context is ready. All future stories will
reference these decisions and constraints automatically.
```

---

# Token Efficiency

**Heavily Haiku-driven** — this skill's primary cost is codebase scanning, which Haiku handles well:

| Phase | Model | Why |
|-------|-------|-----|
| Codebase scanning (3 agents) | **Haiku** | Read-only recon, pattern matching |
| Synthesizing into ADRs/constraints | **Sonnet/Opus** | Needs judgment to write quality ADRs |
| Capsule generation | **Script** | Zero tokens |
| User corrections | **Sonnet/Opus** | Interactive refinement |

**Estimated token budget:** ~60% Haiku, ~35% Sonnet/Opus, ~5% scripts

---

# Error Handling

| Condition | Action |
|-----------|--------|
| Empty codebase | Warn user, suggest `/ideate` instead |
| No package manager files | Infer from file extensions and directory structure |
| Unrecognizable stack | Ask user to describe the stack, fall back to manual ADR creation |
| `.solution-factory/` exists | Ask to merge or start fresh |
| Agent returns incomplete data | Fill gaps with follow-up questions to user |
