---
description: Implement stories with local file-based tracking and progress management
argument-hint: <next|start|complete|status> [story-number]
allowed-tools: [Read, Glob, Grep, Bash, Edit, Write, Task]
---

# Mode of Operation

Parse arguments to determine command:
- **No args** or **"next"**: Find and display next story, offer to start
- **"start <story>"**: Begin work on specific story
- **"complete"**: Verify and merge current story
- **"status"**: Show progress summary

All workflow state stored in `.project-work/`:
1. **implementation-progress.json**: Source of truth for progress tracking
2. **phase-N-stories.md**: Story definitions for each phase
3. **plans/N.NNN-plan.md**: Individual plan files per story

# Command Routing

Check arguments to determine which command to execute. Default to "next" if no arguments provided.

---

# Command: next

## Purpose
Find and display the next uncompleted story, offer to start working on it.

## Workflow

1. **Run get_next_story.py script**:
   ```bash
   python3 ~/.claude/skills/implement-solution/scripts/get_next_story.py
   ```

2. **Parse result**:
   - If `error`: Display error and stop
   - If `complete: true`: Display "All stories in phase N completed!"
   - If `inProgress: true`: Display current story and ask "Continue working on story X.XXX?"
   - Otherwise: Display next story details

2.5. **Check for epic boundary** (if next story starts new epic):
   - Parse epic number from next story
   - Read last completed story from `implementation-progress.json`
   - If last completed story exists:
     - Parse epic number from last completed story
     - If epic numbers differ (crossing epic boundary):
       ```bash
       python3 ~/.claude/skills/implement-solution/scripts/detect_epic_boundary.py --story=[last-completed-story]
       ```
       - If `isLastInEpic: true`:
         - Display reminder:
           ```

           ⚠️  Epic [#] Testing Checkpoint

           Before starting Epic [next-epic], please ensure:

           ✓ Manual testing of Epic [#] is complete
           ✓ All test scenarios in .project-work/testing/epic#/ passed
           ✓ Any issues found have been documented

           Epic [#] test documentation:
           📁 .project-work/testing/epic#/

           Continue to Epic [next-epic]?
           ```
         - Wait for user confirmation (yes/no)
         - If user confirms no: STOP and remind to complete testing first
         - If user confirms yes: proceed to next story

3. **Display story information**:
   ```
   Story X.XXX: [Title]
   Complexity: N/10
   Description: [Description]
   Dependencies: [List or "None"]

   Acceptance Criteria:
   - Criterion 1
   - Criterion 2
   ```

4. **Ask user**: "Start working on this story? /implement-solution start N.NNN"

5. **If yes**: Execute the "start" command workflow

---

# Command: start

## Purpose
Begin work on a story: establish context, create feature branch, interview, plan, and implement.

## Git Branch Workflow

1. **Check git status**:
   ```bash
   git status
   ```
   - Ensure clean working directory (no uncommitted changes)
   - If dirty: Ask user to commit or stash changes first

2. **Ensure on main branch**:
   ```bash
   git branch --show-current
   ```
   - If not on `main`: Ask user to switch to main first

3. **Create and checkout feature branch**:
   ```bash
   git checkout -b feature/[story-number]
   ```
   - Example: `feature/1.001`

## Update Progress Tracking

4. **Update implementation-progress.json**:
   ```bash
   python3 ~/.claude/skills/implement-solution/scripts/update_progress.py --action=start --story=[story-number]
   ```

## Context Establishment

CRITICAL: Before beginning requirements interview, establish full context.

5. **Clear conversation context**: Start fresh for this story

6. **Read project documentation**:
   - Extract structured documentation using extract_docs.py:
     ```bash
     python3 ~/.claude/skills/implement-solution/scripts/extract_docs.py
     ```
   - Review extracted JSON containing headings, key sentences, lists, code blocks, and tables
   - Create story-specific summary focusing on aspects relevant to current story

7. **Review codebase**:
   - Use Task tool with subagent_type=Explore to understand codebase structure
   - Prompt: "Explore codebase to understand structure, key components, and relevant areas for story [X.XXX]: [story title]"
   - Set thoroughness to "medium"

8. **Read current story**:
   - Story already loaded from get_next_story.py or provided as argument
   - Have full story details: title, description, complexity, dependencies, acceptance criteria

9. **Read dependency stories and plans** (if any):
   - For each dependency listed in story:
     - Read dependency story from `phase-N-stories.md`
     - Get dependency plan summary using get_dependency_summary.py:
       ```bash
       python3 ~/.claude/skills/implement-solution/scripts/get_dependency_summary.py --story=[dep-number]
       ```
     - Review JSON containing Success Criteria, Why This Approach, and Dependencies sections only

## Requirements Interview

CRITICAL: NOT optional.

10. **Review story details**, identify ALL clarification needs:
    - Ambiguous terminology
    - Missing implementation details
    - Unclear scope or edge cases
    - Technical approach questions
    - Testing expectations
    - Integration points

## SMART Question Strategy

**General Rule**: ONE QUESTION AT A TIME

**Exception**: Tightly coupled questions (max 3) about same subsystem where answering separately creates incomplete context.

**Correct**: "What technology should I use for X?" [wait] "What are performance requirements?" [wait] "How should errors be handled?"

**Violation**: Lists of unrelated questions or asking everything at once.

Continue until ALL ambiguities resolved.

Don't proceed to planning until can articulate:
- Exact problem to solve
- What to accomplish
- Scope boundaries
- Constraints/preferences
- Testing strategy

## Create a Plan

11. **Create initial plan** with numbered steps:
    - Action items for each step
    - Expected outcomes
    - Dependencies between steps
    - Each step: smallest reasonable progress unit, builds on prior step

## MANDATORY Plan Simplification Review

CRITICAL: NOT optional. After initial plan:

12. **Challenge Assumptions**:
    - Is this necessary or gold-plating?
    - Can we use existing code/libraries?
    - Are we overengineering?

13. **Find Simpler Alternatives**:
    - Can we combine steps?
    - Is there a simpler pattern?
    - What's the 80/20 value?

14. **Eliminate Complexity**:
    - Remove premature abstractions
    - Remove unnecessary indirection
    - Remove over-engineering
    - Remove unrequired features

15. **Apply YAGNI Heuristics** - For each step ask:
    - ✓ YAGNI: Needed NOW or later?
    - ✓ Dependency: Use existing library/framework?
    - ✓ Three Rule: Implement 3+ times before abstracting?
    - ✓ Delete: Core objective still works if skipped?
    - ✓ Configuration: Can we hard-code initially?
    - ✓ Error Handling: Handle or let bubble?

16. **Rewrite plan** with simplified approach

## Plan Structure

Write plan to `.project-work/plans/[story-number]-plan.md` using this structure:

```markdown
# Story [X.XXX]: [Title]

**Complexity:** N/10

## Implementation Steps

### Step 1: [Name]
- Action item 1
- Action item 2
- Expected outcome
- Dependencies: [if any]

### Step 2: [Name]
...

## Plan Simplification Review

### What Was Simplified
- List what was removed or simplified from initial approach
- Explain the changes made

### Alternatives Considered
- Alternative 1: Why not chosen
- Alternative 2: Why not chosen

### Why This Approach
- Rationale for the chosen approach
- Trade-offs accepted

### Heuristics Applied
- YAGNI: [what was deferred]
- Dependency: [what libraries used instead of custom code]
- Configuration: [what was hard-coded]
- Other relevant heuristics

## Dependencies
- External libraries needed
- Internal modules required
- Prerequisite work (other stories)

## Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3
- [ ] All tests pass
- [ ] Code committed to feature branch
```

17. **Write plan file**:
    ```bash
    # Plan content already prepared in markdown
    # Use Write tool to create .project-work/plans/[story-number]-plan.md
    ```

## Review Plan with User

CRITICAL: Mandatory gate.

18. **Verify plan complete**:
    - Requirements interview done
    - Initial plan created
    - Simplification review performed and documented
    - Plan written to file

19. **Present plan to user**:
    - **MUST display story complexity** (e.g., "Story X.XXX - Complexity: N/10")
    - Show simplified plan
    - Show simplification review
    - Request explicit approval

20. **If user rejects**: Revise plan based on feedback, repeat review

## Execute Plan

21. **For EACH Step in the Plan**:

    **Before Step**:
    - Review step details and requirements
    - Begin step implementation

    **During Step**:
    - Execute step tasks
    - Make changes to achieve expected outcomes
    - Add implementation notes
    - **If step involves code changes, write unit tests alongside the implementation** (follow existing test patterns)

    **After Step**:

    a. **Show changes**:
       ```bash
       git diff
       ```
       Summarize in 2-3 bullets what changed

    b. **Test** (MANDATORY - NOT OPTIONAL):
       - **ALWAYS run the full test suite** after each step to identify regression problems immediately
       - Run project test command (e.g., `npm test`, `pytest`, `go test`)
       - If tests fail:
         ```bash
         python3 ~/.claude/skills/implement-solution/scripts/update_progress.py --action=add-blocker --blocker="Tests failing: [details]"
         ```
         - Fix issues before proceeding
         - Do NOT move to next step until tests pass
         - Document what broke and how it was fixed

    c. **Mark success criteria** (if this step completes a criterion):
       ```bash
       python3 ~/.claude/skills/implement-solution/scripts/update_plan_checkbox.py --story=[story-number] --criterion="[criterion text]"
       ```

    d. **Commit automatically**:
       ```bash
       git add [relevant files]
       git commit -m "Step N: [step name] - [brief context]"
       ```
       - NO Claude Code footer in commit message
       - Atomic commits per step
       - Example: `git commit -m "Step 3: Add validation - email format and password strength"`

    e. **Record test files** (if new tests written):
       ```bash
       python3 ~/.claude/skills/implement-solution/scripts/update_progress.py --action=add-test-file --test-files=[test file paths]
       ```

22. **Continue until all steps complete**

## Definition of Done (Per Step)

**Step is complete when ALL apply**:
- Expected outcomes achieved
- Minimal code changes (no over-engineering)
- **All tests pass** (full test suite run after each step - MANDATORY)
- No new errors/warnings introduced
- Changes committed to feature branch
- Relevant success criteria marked complete in plan

---

# Command: complete

## Purpose
Verify all work is done, run tests, merge to main, update progress.

## Workflow

1. **Verify current story exists**:
   - Read `implementation-progress.json`
   - Check that `currentStory` exists and `completed_at` is null
   - If not: Error "No story in progress to complete"

2. **Check plan completion**:
   ```bash
   python3 ~/.claude/skills/implement-solution/scripts/check_plan_complete.py --story=[current-story-number]
   ```

   - If result has `complete: false`:
     - Display: "Story cannot be completed. The following success criteria are not met:"
     - List `incomplete` array items
     - **STOP** - do not proceed to testing or merge
     - User must complete remaining criteria first

3. **Run all tests** (MANDATORY):
   - Run full test suite:
     ```bash
     # Run appropriate test command for project
     npm test  # or pytest, go test, etc.
     ```

4. **If tests fail**:
   - Display test failures
   - Add blocker:
     ```bash
     python3 ~/.claude/skills/implement-solution/scripts/update_progress.py --action=add-blocker --blocker="Tests failing on completion check: [details]"
     ```
   - Message: "Tests failed. Fix issues before completing story."
   - **Do NOT merge** - stay on feature branch
   - **STOP** - user must fix tests and run complete again

5. **If tests pass**, generate completion summary:
   - Read git commits on feature branch:
     ```bash
     git log main..HEAD --oneline
     ```
   - Read files changed:
     ```bash
     git diff main --name-only
     ```
   - Read success criteria from plan (all checked items)
   - **Auto-generate summary sentence** combining:
     - Main accomplishment (from story title)
     - Key changes (from commits/files)
     - Success criteria met
   - Example: "Implemented Cognito user pool with email verification and password policy enforcement (5 files changed, 3 commits)"

6. **Show summary and ask for confirmation**:
   - Display generated summary
   - Show git diff stats
   - Ask: "Ready to merge story [X.XXX] to main?"

7. **If user approves**:

   a. **Merge to main**:
      ```bash
      git checkout main
      git merge --no-ff feature/[story-number] -m "[auto-generated summary]"
      ```

   b. **Delete feature branch**:
      ```bash
      git branch -d feature/[story-number]
      ```

   c. **Update progress** with completion:
      ```bash
      python3 ~/.claude/skills/implement-solution/scripts/update_progress.py \
        --action=complete \
        --story=[story-number] \
        --notes="[auto-generated summary]"
      ```
      This will:
      - Set `completed_at` timestamp
      - Calculate `duration_minutes`
      - Set `notes` with auto-generated summary
      - Move `currentStory` to `completedStories` array
      - Clear `currentStory` to null

   d. **Commit progress update**:
      ```bash
      git add .project-work/implementation-progress.json
      git commit -m "Update progress: Story [X.XXX] completed"
      ```

   e. **Display completion**:
      ```
      ✅ Story [X.XXX] completed and merged to main
      Duration: [N] minutes
      Summary: [auto-generated summary]
      ```

8. **Check for epic boundary**:
   ```bash
   python3 ~/.claude/skills/implement-solution/scripts/detect_epic_boundary.py --story=[story-number]
   ```
   Parse result to check `isLastInEpic`

9. **If epic complete** (`isLastInEpic: true`):

   a. **Create test documentation structure**:
      ```bash
      python3 ~/.claude/skills/implement-solution/scripts/generate_epic_tests.py --epic=[epic-number]
      ```

   b. **Gather epic context**:
      - Read all completed stories in epic from `implementation-progress.json`
      - Read all plan files for epic stories from `.project-work/plans/`
      - Get git log for epic to understand changes:
        ```bash
        # Find commits for all stories in epic
        git log --oneline --grep="Epic [epic-number]" --all
        ```
      - Get files changed across epic:
        ```bash
        # Compare from start of epic to current HEAD
        git diff --stat [first-story-commit]..HEAD
        ```

   c. **Generate comprehensive test documentation**:

      **Create `.project-work/testing/epic#/README.md`:**
      - Epic Overview section:
        - Epic number and theme (extract from phase-N-stories.md epic header)
        - What was implemented (summary of all stories in epic)
        - Total stories completed
        - Key files modified/created (from git diff stats)
      - Quick Start section:
        - Prerequisites to run tests (dependencies, setup needed)
        - How to execute tests (step-by-step)
        - Expected time to complete testing
      - Test Summary section:
        - Link to detailed test-plan.md
        - Link to test scripts directory
        - Overview of what needs to be tested

      **Create `.project-work/testing/epic#/test-plan.md`:**
      - Objectives section:
        - What this epic accomplished
        - Why manual testing matters for this epic
        - Integration points to verify
      - Test Scenarios section:
        - For each story or major feature in epic:
          - Scenario description
          - Steps to test manually
          - Expected outcome
          - How to verify success
      - Acceptance Criteria Verification:
        - Checklist of ALL acceptance criteria from ALL stories in epic
        - Instructions on how to verify each criterion
        - [ ] Format for user to check off
      - Edge Cases section:
        - Edge cases to test
        - Expected behavior for edge cases
        - Error scenarios to verify
      - Known Limitations section:
        - Any known issues or future work
        - What was intentionally deferred

      **Create test scripts in `.project-work/testing/epic#/test-scripts/`:**
      - If applicable for the epic, create:
        - Automated test scripts (API calls, CLI commands)
        - Setup scripts (database seeding, environment setup)
        - Teardown scripts (cleanup)
        - Sample curl commands or API test collections
      - If automated tests not applicable:
        - Create `manual-test-guide.sh` with commented test commands
        - Document manual verification steps

      **Create test data in `.project-work/testing/epic#/test-data/`:**
      - Sample input data files (JSON, CSV, etc.) if applicable
      - Expected output examples
      - Test database fixtures or seed data
      - Configuration files needed for testing
      - If not applicable, create `README.md` explaining no test data needed

   d. **Commit test documentation**:
      ```bash
      git add .project-work/testing/epic#
      git commit -m "Add comprehensive test documentation for Epic #"
      ```

   e. **Update epic tracking**:
      ```bash
      python3 ~/.claude/skills/implement-solution/scripts/update_progress.py \
        --action=set-epic \
        --story=[next-epic-number]
      ```

   f. **Prompt for manual testing**:
      ```

      ═══════════════════════════════════════════════════════════════
      🎯 Epic [#] Complete!
      ═══════════════════════════════════════════════════════════════

      All [X] stories in Epic [#] have been implemented and merged.

      Comprehensive test documentation has been created in:
      📁 .project-work/testing/epic#/

      ┌─────────────────────────────────────────────────────────────┐
      │ MANUAL TESTING REQUIRED                                      │
      ├─────────────────────────────────────────────────────────────┤
      │ Please review and execute the test plan to verify all epic   │
      │ functionality works correctly before proceeding.              │
      │                                                              │
      │ 1. Review: .project-work/testing/epic#/README.md            │
      │ 2. Follow: .project-work/testing/epic#/test-plan.md         │
      │ 3. Run: Test scripts in test-scripts/ (if applicable)       │
      │ 4. Verify: All acceptance criteria met                      │
      │ 5. Document: Any issues found during testing                │
      └─────────────────────────────────────────────────────────────┘

      When testing is complete and epic is verified:
      ✅ Run: /implement-solution next

      This will continue to Epic [next-epic-number].

      ═══════════════════════════════════════════════════════════════
      ```

   g. **STOP** - Do not automatically proceed to next story
      - User must complete manual testing
      - User must explicitly run `/implement-solution next` to continue
      - This ensures quality gate is enforced

## Handling Blockers

If story is blocked at any point:

1. **Document blocker**:
   ```bash
   python3 ~/.claude/skills/implement-solution/scripts/update_progress.py --action=add-blocker --blocker="[description]"
   ```

2. **Assess impact**:
   - Can we work around it?
   - Does plan need revision?
   - Is there a requirements gap?
   - Is it a dependency issue?

3. **User consultation**:
   - Present blocker with context
   - Show what was attempted
   - Offer 2-3 paths forward with pros/cons
   - Get user decision

4. **Update plan if needed**:
   - If significant change required, update plan file
   - Document reason for change
   - Get user approval for revised approach

5. **Never proceed without resolution**:
   - Don't mark steps complete
   - Don't skip steps
   - Don't guess solutions
   - Wait for user guidance

---

# Command: status

## Purpose
Show summary of project progress.

## Workflow

1. **Run get_status.py script**:
   ```bash
   python3 ~/.claude/skills/implement-solution/scripts/get_status.py
   ```

2. **Parse result and display**:
   ```
   Phase [N] Progress: [X] completed, [Y] remaining of [Z] total stories
   Current Epic: [N] (or "Not set" if null)
   Next Epic to Generate: [N] (or "Not set" if null)

   [If current story exists:]
   Currently working on: Story [X.XXX] (started [HH]h [MM]m ago)
   Test files: [list]
   Blockers: [list if any]
   ```

---

# Error Handling

## Missing .project-work Structure

If `.project-work/` directory or required files don't exist:
1. Display helpful error message
2. Explain expected structure:
   ```
   .project-work/
   ├── implementation-progress.json
   ├── phase-1-stories.md
   ├── phase-2-stories.md
   └── plans/
   ```
3. Provide guidance on setting up structure
4. STOP - user must create structure first

## Git Issues

### Dirty Working Directory
- Display uncommitted changes
- Ask user to commit or stash
- STOP until resolved

### Not on Main Branch (when starting)
- Display current branch
- Ask user to switch to main
- STOP until on main

### Merge Conflicts
- Display conflict details
- Guide user through resolution
- Re-run tests after resolution
- Continue merge process

## Script Errors

If Python script fails:
1. Display script error output
2. Check if `.project-work/` files are malformed JSON or markdown
3. Provide specific guidance based on error
4. STOP until resolved

---

# Resuming Work

If a story is already in progress (currentStory exists with no completed_at):

1. **Display story status**:
   - Story number and title
   - Time elapsed since start
   - Test files created so far
   - Any blockers

2. **Read context**:
   - Read plan file
   - Check which success criteria are complete
   - Review recent commits on feature branch

3. **Ask user**: "Continue working on story [X.XXX]?"

4. **If yes**:
   - Resume from current point in plan
   - Continue normal execution workflow

5. **If no**:
   - User may want to abandon or reset
   - Provide options and guidance

---

# Best Practices

## Code Quality
- Avoid over-engineering
- Only make changes directly requested or clearly necessary
- Keep solutions simple and focused
- Don't add features beyond what was asked
- Don't refactor surrounding code unnecessarily
- Only add comments where logic isn't self-evident

## Security
- Watch for command injection vulnerabilities
- Avoid XSS, SQL injection, OWASP top 10 issues
- If insecure code written, immediately fix it

## Git Hygiene
- Atomic commits per step
- Clear, descriptive commit messages
- No Claude Code footer
- Always work on feature branches
- Merge only when all criteria met and tests pass

## Testing
- **MANDATORY**: Always run full test suite after each step to catch regressions immediately
- **MANDATORY**: Write unit tests alongside code changes for all story implementations
- Block progress on test failures - do not proceed until tests pass
- Follow existing test patterns in the codebase
- Tests must be comprehensive and cover acceptance criteria

## Communication
- Ask ONE question at a time (except tightly coupled questions)
- Get explicit user approval at key gates
- Show changes before committing
- Explain blockers clearly with context
- Provide options when decisions needed

---

# Troubleshooting

## "No next story found"
- All stories in current phase completed
- Consider incrementing phase or celebrating completion
- Check if phase-N-stories.md has stories defined

## "Plan file not found"
- Plan wasn't created during start workflow
- Re-run start process
- Check `.project-work/plans/` directory exists

## "Tests keep failing"
- Add blocker to track issue
- Investigate test failures systematically
- May need to revise implementation approach
- Don't proceed until tests pass

## "Success criteria incomplete"
- Review plan file manually
- Verify checkboxes marked with [x]
- Complete remaining work
- Update checkboxes as criteria met
- Run complete again when all checked

## "Git merge conflicts"
- Main branch changed since feature branch created
- Resolve conflicts manually
- Re-run tests after resolution
- Continue merge process
