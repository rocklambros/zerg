# Spec Compliance Review

## Task Specification

**Task ID**: {{task_id}}
**Title**: {{task_title}}

**Acceptance Criteria**:
{{#each acceptance_criteria}}
- {{this}}
{{/each}}

**Allowed Files**:
- Create: {{files.create}}
- Modify: {{files.modify}}

## Implementation

**Git Diff**:
```
{{git_diff}}
```

## Review Checklist

### Requirements Coverage
{{#each acceptance_criteria}}
- [ ] {{this}}
  - Evidence: [locate in code]
  - Status: Met | Not met | Partial
{{/each}}

### Scope Compliance
- [ ] Only specified files modified
- [ ] No extra features added
- [ ] No unauthorized file creation

### Completeness
- [ ] No TODOs or placeholders
- [ ] No commented-out incomplete code
- [ ] All error paths handled

## Output Format

```
SPEC COMPLIANCE REVIEW
======================
Task: {{task_id}} - {{task_title}}

REQUIREMENTS:
[MET|NOT MET|PARTIAL] <criterion>
    Evidence: ...

SCOPE:
[OK|FAIL] Only allowed files modified
[OK|FAIL] No extra features

VERDICT: SPEC COMPLIANT | NOT COMPLIANT

{{#if issues}}
ISSUES REQUIRING FIX:
1. ...
{{/if}}
```
