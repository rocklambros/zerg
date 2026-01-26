# Task Implementation

You are implementing a specific task from the project plan.

## Your Task

**Task ID**: {{task_id}}
**Title**: {{task_title}}

**Description**:
{{task_description}}

**Files to Create**:
{{#each files.create}}
- {{this}}
{{/each}}

**Files to Modify**:
{{#each files.modify}}
- {{this}}
{{/each}}

**Files to Read** (context only):
{{#each files.read}}
- {{this}}
{{/each}}

**Acceptance Criteria**:
{{#each acceptance_criteria}}
- [ ] {{this}}
{{/each}}

## Protocol

1. **Ask Questions First**: Clarify before implementing.

2. **Follow TDD** (for code tasks):
   - Write failing test FIRST
   - Run to confirm failure (red)
   - Write minimal code to pass (green)
   - Refactor if needed

3. **Verify Before Claiming Done**:
   - Run: `{{verification.command}}`
   - Check output shows 0 failures
   - Include output in response

4. **Self-Review**:
   - All acceptance criteria met?
   - Only specified files modified?
   - No TODOs or incomplete sections?

5. **Commit**: `{{commit_type}}({{scope}}): {{description}} [{{task_id}}]`

## Constraints

- Do NOT modify files outside the list
- Do NOT add features beyond acceptance criteria
- Do NOT skip verification
- Do NOT claim done without test output

## Output

When complete, provide:
1. Summary of implementation
2. Verification output (REQUIRED)
3. Files created/modified
4. Concerns for review
