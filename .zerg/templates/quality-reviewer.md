# Code Quality Review

## Context

**Task ID**: {{task_id}}
**Language**: {{language}}
**Framework**: {{framework}}

## Code to Review

{{#each files}}
### {{this.path}}
```{{this.language}}
{{this.content}}
```
{{/each}}

## Checklist

### Code Style
- [ ] Follows project conventions
- [ ] Consistent formatting
- [ ] Meaningful names
- [ ] No magic numbers

### Code Quality
- [ ] No duplication
- [ ] Appropriate abstraction
- [ ] Error handling present
- [ ] No performance issues

### Testing
- [ ] Tests are meaningful
- [ ] Edge cases covered
- [ ] Independent tests

### Security
- [ ] Input validation
- [ ] No hardcoded secrets
- [ ] Safe data handling

## Output Format

```
CODE QUALITY REVIEW
===================
Task: {{task_id}}

STRENGTHS:
- ...

ISSUES:
[Critical] ...
[Important] ...
[Minor] ...

VERDICT: APPROVED | APPROVED WITH NOTES | CHANGES REQUIRED
```
