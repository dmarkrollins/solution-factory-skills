---
description: Generate epic stories from phase plans with complexity management and sequencing
argument-hint: [--max-complexity=N]
allowed-tools: [Read, Glob, Grep, Bash, Write, Task]
---

# Mode of Operation

Break down a phase objective into a single epic with sequenced stories that build toward the phase goal.

**Key features:**
- Generates ONE epic at a time
- Enforces max complexity per story (configurable, default: 3)
- Sequences stories with explicit dependencies
- Creates comprehensive, testable story definitions
- Collaborative refinement with user

**Arguments:**
- `--max-complexity=N` - Maximum story complexity (default: 3)

**Input:** `/docs/phase-N-plan.md` (phase objective and requirements)

**Output:** Appends epic stories to `.project-work/phase-N-stories.md`

---

# Workflow

## Step 1: Get Next Epic Number

1. **Run get_next_epic.py script**:
   ```bash
   python3 ~/.claude/skills/story-generation/scripts/get_next_epic.py
   ```

2. **Parse result**:
   - If `error`: Display error and stop
   - Extract: `nextEpic`, `currentPhase`, `lastCompletedEpic`
   - Determine phase from epic number (read from implementation-progress.json)

3. **Display**:
   ```
   Generating Epic [N] for Phase [P]
   Last Completed Epic: [N-1] (or "None" if first epic)
   Max Complexity: [X]/10
   ```

---

## Step 2: Establish Context

CRITICAL: Gather full context before generating stories.

4. **Read phase plan**:
   - Read `/docs/phase-N-plan.md`
   - Extract:
     - Phase objective
     - Key requirements
     - Success criteria
     - Constraints
     - Any epic-specific guidance

5. **Extract documentation context**:
   ```bash
   python3 ~/.claude/skills/implement-solution/scripts/extract_docs.py
   ```
   - Review extracted JSON containing headings, key sentences, lists, code blocks, tables
   - Create context summary relevant to phase objective

6. **Review codebase structure**:
   - Use Task tool with subagent_type=Explore
   - Prompt: "Explore codebase to understand structure, key components, and architecture for Phase [N]: [phase objective]"
   - Set thoroughness to "medium"
   - Focus on areas relevant to phase work

7. **Read completed work** (if any):
   - Read `implementation-progress.json` for completed stories/epics
   - If epics exist in this phase, read `.project-work/phase-N-stories.md` to see existing epics
   - Understand what's already been built to inform next epic

---

## Step 3: Generate Epic with Iterative Refinement

### 3a. Analyze Epic Scope

8. **Determine epic theme**:
   - Review phase objective from `phase-N-plan.md`
   - Consider what's already complete (if any prior epics)
   - Identify logical grouping for this epic:
     - What functionality belongs together?
     - What can be manually tested as a complete unit?
     - What represents a natural milestone toward phase goal?
   - Define epic contribution to phase goal
   - Identify functional boundaries

9. **Consider epic boundaries**:
   - **Functional logic**: Related features that work together
   - **Complexity budget**: Aim for 5-8 stories, total complexity 15-25 points
   - **Testable milestone**: End epic when there's something meaningful to manually test
   - Epic should deliver cohesive, demonstrable value

### 3b. Draft Initial Stories

10. **Break epic into logical stories**:
    - Focus on functional decomposition (ignore complexity initially)
    - Think about natural implementation flow
    - Aim for 8-15 initial stories per epic (will be refined through splitting)
    - Each story should have clear purpose and deliverable

### 3c. Score Story Complexity

11. **Apply Complexity Rubric to each story**:

    **Complexity Scoring Framework (0-10 scale):**

    **1. Technical Complexity (0-3 points):**
    - **0 points**: Trivial
      - Edit existing pattern, no new concepts
      - Example: Change hardcoded value, update text
    - **1 point**: Simple
      - New file using existing patterns
      - Minimal logic, straightforward implementation
      - Example: Add new model field, create basic CRUD endpoint
    - **2 points**: Moderate
      - New pattern/approach in codebase
      - Multiple files affected
      - Moderate logic complexity
      - Example: Implement validation layer, add middleware
    - **3 points**: Complex
      - New architecture or framework integration
      - Significant new concepts
      - Complex logic or algorithms
      - Example: Implement authentication system, add caching layer

    **2. Scope Size (0-3 points):**
    - **0 points**: Tiny
      - 1-2 acceptance criteria
      - Single responsibility
      - Example: Add email validation to one field
    - **1 point**: Small
      - 3-4 acceptance criteria
      - Focused feature
      - Example: Create registration form with basic validation
    - **2 points**: Medium
      - 5-6 acceptance criteria
      - Multiple related features
      - Example: Implement user profile with multiple sections
    - **3 points**: Large
      - 7+ acceptance criteria
      - Broad functionality
      - Example: Build entire authentication flow

    **3. Risk/Uncertainty (0-2 points):**
    - **0 points**: Clear
      - Well-understood requirements
      - No unknowns or dependencies on external systems
      - Example: Add field to existing form
    - **1 point**: Some uncertainty
      - Minor unknowns that can be resolved quickly
      - Manageable risks
      - Example: Integrate with documented third-party API
    - **2 points**: High uncertainty
      - Significant unknowns or unclear requirements
      - External dependencies with uncertain behavior
      - Example: Integrate with poorly documented system

    **4. Integration Complexity (0-2 points):**
    - **0 points**: Isolated
      - Single module, no integration
      - Example: Add helper function to utils
    - **1 point**: Moderate
      - Touches 2-3 modules/systems
      - Straightforward integration points
      - Example: Connect frontend form to backend endpoint
    - **2 points**: Complex
      - Touches 4+ modules/systems
      - Intricate integration points, data flow across boundaries
      - Example: Coordinate changes across frontend, API, database, and queue system

    **Total Score:** Sum of all dimensions = 0-10

12. **Calculate and record complexity** for each drafted story:
    - Analyze each story against the rubric
    - Assign points for each dimension
    - Sum to get total complexity score
    - Flag any story where total > max-complexity

### 3d. Split High-Complexity Stories

13. **For each story where total > max-complexity:**

    a. **Identify highest-scoring dimension(s)**:
       - Which dimension(s) contributed most to high score?

    b. **Apply appropriate splitting strategy**:

       **If Scope is high (2-3 points):**
       - Split by acceptance criteria (group related criteria)
       - Split by functional areas
       - Example: "User profile with settings and preferences" →
         - Story A: "User profile display with basic info"
         - Story B: "Add user settings section"
         - Story C: "Add user preferences section"

       **If Technical is high (2-3 points):**
       - Split by layers (model → service → API → UI)
       - Split by implementation phases
       - Example: "Implement caching with Redis" →
         - Story A: "Setup Redis connection and configuration"
         - Story B: "Implement cache read/write methods"
         - Story C: "Integrate caching into API endpoints"

       **If Risk is high (2 points):**
       - Create spike/research story first
       - Then create implementation stories based on findings
       - Example: "Integrate with unknown payment gateway" →
         - Story A: "Research payment gateway API and capabilities"
         - Story B: "Implement basic payment flow"
         - Story C: "Add error handling and edge cases"

       **If Integration is high (2 points):**
       - Split by integration point or system boundary
       - Example: "Connect frontend, API, and database for orders" →
         - Story A: "Create order database model and queries"
         - Story B: "Create order API endpoints"
         - Story C: "Build order management UI"

    c. **Create 2-3 smaller stories** from the split

    d. **Re-score each new story** using the rubric

    e. **Repeat splitting** until all stories ≤ max-complexity

**Example Split:**

*Original Story (Complexity: 8):*
```
Title: Implement user registration with email verification, password validation, and duplicate checking
Technical: 3 (new auth flow)
Scope: 3 (7+ criteria)
Risk: 1 (external email service)
Integration: 1 (2 systems)
Total: 8
```

*After Split (each ≤ 3):*
```
Story 5.001: Create user model with basic fields
Technical: 1 (new file, existing pattern)
Scope: 1 (3 criteria: model, validation, tests)
Risk: 0 (clear requirements)
Integration: 0 (single module)
Total: 2

Story 5.002: Add registration endpoint - happy path only
Technical: 1 (new endpoint, standard pattern)
Scope: 1 (3 criteria: endpoint, success response, basic test)
Risk: 0 (clear requirements)
Integration: 1 (connects model to API)
Total: 3

Story 5.003: Add email format validation
Technical: 1 (use validation library)
Scope: 1 (3 criteria: validation, error message, test)
Risk: 0 (well-understood)
Integration: 0 (single module)
Total: 2

Story 5.004: Add password strength requirements
Technical: 1 (validation rules)
Scope: 1 (3 criteria: strength check, error message, test)
Risk: 0 (clear requirements)
Integration: 0 (single module)
Total: 2

Story 5.005: Add duplicate user checking
Technical: 1 (database query)
Scope: 2 (5 criteria: query, check logic, error handling, response, test)
Risk: 0 (clear requirements)
Integration: 0 (single module)
Total: 3
```

### 3e. Sequence Stories with Dependencies

14. **Apply sequencing principles**:

    **Foundation First:**
    - Infrastructure, models, schemas, core setup come before features
    - Stories with no dependencies go first
    - Example: Database models before API endpoints

    **Vertical Slices:**
    - After foundation, deliver thin working slices end-to-end
    - Each slice can be tested independently
    - Example: Basic registration endpoint before adding validations

    **Progressive Enhancement:**
    - Start with basic/happy-path functionality
    - Add validation, error handling, edge cases in subsequent stories
    - Add integrations and polish last
    - Example: Happy path → Validation → Error handling → Edge cases

    **Build-Upon Context:**
    - Each story explicitly states what it builds upon
    - Makes implementation clear and focused
    - Example: "Builds upon 5.002 by adding email validation to the registration endpoint"

15. **Sequence stories step-by-step**:

    a. **Identify foundation stories** (no dependencies):
       - Models, schemas, basic setup
       - These stories can start immediately
       - Mark as `Dependencies: None`

    b. **Create first vertical slice** (depends on foundation):
       - Minimal working feature end-to-end
       - Proves the approach works
       - Mark dependencies on foundation stories

    c. **Plan progressive enhancements** (depends on vertical slice):
       - Validation stories
       - Error handling stories
       - Edge case stories
       - Mark dependencies on vertical slice

    d. **Add integration stories** (depends on core + enhancements):
       - Connect to other systems
       - Full feature integration
       - Mark all relevant dependencies

16. **Assign explicit dependencies**:
    - For each story, list ALL prerequisite stories
    - Format: `Dependencies: None` or `Dependencies: 5.001, 5.002`
    - A story can only depend on earlier stories in the sequence

17. **Add "Builds Upon" context to descriptions**:
    - Each story description should include what it builds upon
    - Examples:
      - Story 5.001: "Builds upon: N/A - Foundation story"
      - Story 5.002: "Builds upon: Story 5.001 by creating an endpoint that uses the user model"
      - Story 5.003: "Builds upon: Story 5.002 by adding email validation to the registration endpoint"

### 3f. Validate Sequence

18. **Verify sequence integrity**:
    - [ ] All dependencies listed are earlier in the sequence (no forward references)
    - [ ] Each story has "Builds Upon" context in description
    - [ ] Each story can be implemented independently given its dependencies are complete
    - [ ] Each story delivers testable value
    - [ ] All complexity scores ≤ max-complexity threshold
    - [ ] Stories progress logically toward epic objective
    - [ ] Epic as a whole represents a testable milestone

### 3g. Format Stories

19. **Format each story using standard template**:

```markdown
# Epic N: [Epic Theme/Name]

Brief description of what this epic accomplishes toward the phase objective.

## Story N.001: [Story Title]

**Complexity**: 2/10
**Description**: [What this story does and delivers. Builds upon: N/A - Foundation story OR Builds upon: Story N.XXX by adding/enhancing...]
**Dependencies**: None
**Acceptance Criteria**:
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Story N.002: [Story Title]

**Complexity**: 3/10
**Description**: [What this story does. Builds upon: Story N.001 by creating...]
**Dependencies**: N.001
**Acceptance Criteria**:
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3
- [ ] Criterion 4
```

**Story template requirements:**
- Complexity score clearly stated
- Description includes "Builds Upon" context
- Dependencies explicitly listed (or "None")
- Acceptance criteria in checklist format (3-6 criteria typical)
- Unchecked boxes [ ] for tracking

---

## Step 4: Append to Phase File

20. **Prepare file path**:
    - File: `.project-work/phase-N-stories.md`
    - Determine phase from epic number (read from implementation-progress.json)

21. **Read existing file** (if it exists):
    - Check if `.project-work/phase-N-stories.md` exists
    - If exists, read current content to append to it
    - If not exists, will create new file

22. **Format epic content**:
    - Include epic header with theme/name
    - Include brief epic description
    - Include all formatted stories

23. **Write/append to file**:
    - If file doesn't exist:
      ```markdown
      # Phase N Stories

      # Epic [N]: [Epic Theme]

      [Epic description]

      [All stories]
      ```
    - If file exists:
      - Append epic header and stories to end of existing content
      - Maintain clear separation between epics

---

## Step 5: Present Epic Summary

24. **Calculate summary statistics**:
    - Count total stories in epic
    - Calculate total complexity points
    - Identify complexity range (min-max)
    - List all story numbers and titles

25. **Display comprehensive summary**:
    ```

    ═══════════════════════════════════════════════════════════════
    📋 Epic [N]: [Epic Theme]
    ═══════════════════════════════════════════════════════════════

    Phase: [N]
    Stories: [X]
    Total Complexity: [Y] points
    Complexity Range: [min]-[max] (all within max-complexity threshold of [Z])

    Epic Objective:
    [What this epic accomplishes toward phase goal - 2-3 sentences]

    Stories:
    - [N.001]: [Title] (Complexity: 2, Dependencies: None)
    - [N.002]: [Title] (Complexity: 3, Dependencies: N.001)
    - [N.003]: [Title] (Complexity: 2, Dependencies: N.002)
    - [N.004]: [Title] (Complexity: 3, Dependencies: N.002, N.003)
    ...

    Dependencies on Prior Epics:
    [List any stories that depend on previous epic's work, or "None"]

    Files Updated:
    - .project-work/phase-N-stories.md

    ═══════════════════════════════════════════════════════════════
    ```

26. **Ask for review**:
    ```
    Please review Epic [N] above.

    Options:
    1. Approve and finalize this epic
    2. Request refinements (add/remove/split/merge stories, adjust complexity, resequence, clarify)

    Would you like to proceed with this epic, or make refinements?
    ```

---

## Step 6: Collaborative Refinement

27. **If user requests refinements**:

    **Types of refinements:**

    a. **Add stories**:
       - User identifies missing functionality
       - Draft new story with complexity scoring
       - Insert in appropriate sequence position
       - Update dependencies as needed

    b. **Remove stories**:
       - User identifies unnecessary story
       - Remove from epic
       - Update dependencies of stories that depended on it

    c. **Split stories**:
       - User feels story is too complex or broad
       - Apply splitting strategy (by scope, technical, etc.)
       - Re-score split stories
       - Update sequence and dependencies

    d. **Merge stories**:
       - User feels stories are too granular
       - Combine related stories
       - Re-score merged story
       - Verify still within max-complexity
       - Update dependencies

    e. **Adjust complexity scores**:
       - User disagrees with scoring
       - Review rubric together
       - Adjust scores as agreed
       - If score exceeds max-complexity, split story

    f. **Resequence stories**:
       - User identifies better order
       - Rearrange stories
       - Update dependencies to match new sequence
       - Verify dependencies still make sense

    g. **Clarify descriptions**:
       - User needs more detail
       - Expand description
       - Add more context to "Builds Upon" section
       - Add more specific acceptance criteria

28. **Edit `.project-work/phase-N-stories.md`**:
    - Make requested changes to the file
    - Ensure all stories remain properly formatted
    - Verify epic header and description are clear

29. **Re-present summary**:
    - Display updated epic summary (same format as Step 25)
    - Show what changed
    - Ask again: "Please review the updated epic. Proceed or refine further?"

30. **Repeat refinement** until user approves

---

## Step 7: Finalize and Update Tracking

31. **Commit epic stories**:
    ```bash
    git add .project-work/phase-N-stories.md
    git commit -m "Add Epic [N] stories to Phase [N]

    Epic [N]: [Epic Theme]
    - [X] stories created
    - Complexity range: [min]-[max]
    - All stories sequenced with dependencies"
    ```

32. **Update progress tracking**:
    ```bash
    python3 ~/.claude/skills/implement-solution/scripts/update_progress.py \
      --action=set-next-epic-to-generate \
      --story=[N+1]
    ```
    This sets nextEpicToGenerate to the next epic number

33. **Display completion message**:
    ```

    ✅ Epic [N] stories created and saved

    Epic [N]: [Epic Theme]
    - [X] stories in .project-work/phase-N-stories.md
    - Ready for implementation

    Next steps:
    1. Run: /implement-solution next
       This will start the first story in Epic [N]

    2. Work through epic stories sequentially

    3. Complete manual testing when Epic [N] finishes
       Test documentation will be auto-generated in:
       .project-work/testing/epic[N]/

    ```

---

# Best Practices

## Complexity Scoring

- **Be consistent**: Apply rubric uniformly across all stories
- **When in doubt, split**: If unsure whether story fits max-complexity, split it
- **Consider implementation reality**: Score based on actual coding effort, not perceived importance
- **Re-score after splitting**: Split stories often score lower due to reduced scope

## Story Sequencing

- **Foundation before features**: Models, schemas, setup must come first
- **Minimize dependencies**: Stories with fewer dependencies are easier to implement
- **Test early**: First vertical slice should be testable end-to-end
- **Progressive enhancement**: Add validation/error handling after basic functionality works

## Epic Boundaries

- **Testable milestones**: Epic should end when there's something meaningful to manually test
- **Cohesive functionality**: Stories in an epic should relate to each other
- **Reasonable size**: 5-10 stories typical, adjust based on complexity
- **Phase alignment**: Epic should clearly contribute to phase objective

## Collaboration

- **Listen to user feedback**: They know the project better
- **Explain trade-offs**: Help user understand complexity vs. granularity
- **Be flexible**: User may have insights about better sequencing or scope
- **Iterate quickly**: Make changes and re-present rather than lengthy discussions

---

# Error Handling

## Missing Phase Plan

If `/docs/phase-N-plan.md` not found:
1. Display error with expected file path
2. Explain what should be in the phase plan:
   - Phase objective
   - Key requirements
   - Success criteria
   - Constraints
3. STOP - user must create phase plan first

## Invalid Max Complexity

If `--max-complexity` is not 1-10:
1. Display error: "Max complexity must be between 1 and 10"
2. Suggest: "Use --max-complexity=3 (default) for balanced story size"
3. STOP - user must provide valid value

## No Implementation Progress File

If `.project-work/implementation-progress.json` not found:
1. Display error explaining file is required
2. Suggest running `/implement-solution status` to initialize
3. STOP - user must set up project structure

## Epic Already Generated

If trying to generate epic that already exists in phase-N-stories.md:
1. Check if epic number already in file
2. Display warning: "Epic [N] appears to already exist"
3. Ask: "Do you want to regenerate/replace it? (yes/no)"
4. If yes: Remove existing epic and regenerate
5. If no: STOP

---

# Troubleshooting

## "Stories too granular"
- User feels stories are too small
- Consider merging related stories
- Verify merged stories still ≤ max-complexity
- May need to increase max-complexity parameter

## "Stories too large"
- Stories consistently at or above max-complexity
- Apply more aggressive splitting
- Break by layers (model, service, API, UI)
- Consider if max-complexity threshold should be lower

## "Dependencies unclear"
- Story sequence doesn't make sense
- Review "Builds Upon" descriptions
- Ensure dependencies align with implementation order
- Consider if foundation stories are missing

## "Epic scope too broad"
- Epic has 15+ stories
- Consider if epic should be split into two epics
- Look for natural break point (testable milestone)
- Each epic should be manually testable as a unit

## "Can't determine next epic"
- get_next_epic.py returns unexpected result
- Check implementation-progress.json for valid data
- Verify completedStories array has valid story numbers
- May need to manually set nextEpicToGenerate field

---
