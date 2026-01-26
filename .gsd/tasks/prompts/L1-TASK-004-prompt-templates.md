# L1-TASK-004: Worker Prompt Templates

## Objective

Implement Handlebars-style prompt templates for worker/reviewer dispatch.

## Context

**Depends on**: L0-TASK-004 (Worker Protocol)

Workers and reviewers receive structured prompts that enforce TDD, verification-before-completion, and consistent output formats. Templates use variable substitution for task-specific content.

## Files to Create

```
.zerg/
├── template_engine.py        # Template rendering engine
└── templates/
    ├── implementer.md        # Task implementation prompt
    ├── spec-reviewer.md      # Spec compliance review
    └── quality-reviewer.md   # Code quality review
```

## Implementation Requirements

### Template Engine

```python
import re
from pathlib import Path
from typing import Any

class TemplateEngine:
    """Handlebars-style template rendering."""
    
    TEMPLATE_DIR = Path(".zerg/templates")
    
    def __init__(self, template_dir: Path = None):
        self.template_dir = template_dir or self.TEMPLATE_DIR
        self._cache: dict[str, str] = {}
    
    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Render template with context variables."""
        template = self._load_template(template_name)
        return self._render_template(template, context)
    
    def _load_template(self, name: str) -> str:
        """Load template from file."""
        if name in self._cache:
            return self._cache[name]
        
        # Check custom templates first
        custom_path = self.template_dir / "custom" / name
        if custom_path.exists():
            template = custom_path.read_text()
        else:
            template = (self.template_dir / name).read_text()
        
        self._cache[name] = template
        return template
    
    def _render_template(self, template: str, context: dict) -> str:
        """Replace variables and process conditionals."""
        result = template
        
        # Process {{#each}} blocks
        result = self._process_each(result, context)
        
        # Process {{#if}} blocks
        result = self._process_if(result, context)
        
        # Replace {{variable}} and {{nested.variable}}
        result = self._replace_variables(result, context)
        
        return result
    
    def _replace_variables(self, template: str, context: dict) -> str:
        """Replace {{var}} with values from context."""
        def replace(match):
            key = match.group(1).strip()
            value = self._get_nested(context, key)
            if value is None:
                return match.group(0)  # Keep original if not found
            return str(value)
        
        return re.sub(r'\{\{([^#/}]+)\}\}', replace, template)
    
    def _get_nested(self, obj: dict, key: str) -> Any:
        """Get nested value like 'files.create'."""
        parts = key.split('.')
        value = obj
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value
    
    def _process_each(self, template: str, context: dict) -> str:
        """Process {{#each items}}...{{/each}} blocks."""
        pattern = r'\{\{#each\s+(\w+(?:\.\w+)*)\}\}(.*?)\{\{/each\}\}'
        
        def replace(match):
            key = match.group(1)
            block = match.group(2)
            items = self._get_nested(context, key)
            
            if not items:
                return ""
            
            result = []
            for item in items:
                item_context = {**context, 'this': item}
                result.append(self._render_template(block, item_context))
            
            return ''.join(result)
        
        return re.sub(pattern, replace, template, flags=re.DOTALL)
    
    def _process_if(self, template: str, context: dict) -> str:
        """Process {{#if var}}...{{/if}} blocks."""
        pattern = r'\{\{#if\s+(\w+(?:\.\w+)*)\}\}(.*?)\{\{/if\}\}'
        
        def replace(match):
            key = match.group(1)
            block = match.group(2)
            value = self._get_nested(context, key)
            
            if value:
                return self._render_template(block, context)
            return ""
        
        return re.sub(pattern, replace, template, flags=re.DOTALL)


def render(template_name: str, context: dict) -> str:
    """Convenience function for rendering."""
    engine = TemplateEngine()
    return engine.render(template_name, context)
```

### Implementer Template

Create `.zerg/templates/implementer.md`:

```markdown
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
```

### Spec Reviewer Template

Create `.zerg/templates/spec-reviewer.md`:

```markdown
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
  - Status: ✅ Met | ❌ Not met | ⚠️ Partial
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
[✅|❌|⚠️] <criterion>
    Evidence: ...

SCOPE:
[✅|❌] Only allowed files modified
[✅|❌] No extra features

VERDICT: ✅ SPEC COMPLIANT | ❌ NOT COMPLIANT

{{#if issues}}
ISSUES REQUIRING FIX:
1. ...
{{/if}}
```
```

### Quality Reviewer Template

Create `.zerg/templates/quality-reviewer.md`:

```markdown
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

VERDICT: ✅ APPROVED | ⚠️ APPROVED WITH NOTES | ❌ CHANGES REQUIRED
```
```

## Acceptance Criteria

- [ ] Template loading from `.zerg/templates/`
- [ ] Variable substitution ({{var}}, {{nested.var}})
- [ ] Conditional sections ({{#if}})
- [ ] List iteration ({{#each}})
- [ ] Custom template override support
- [ ] All three prompt templates created

## Verification

```bash
cd .zerg && python -c "
from template_engine import render

context = {
    'task_id': 'TASK-001',
    'task_title': 'Create auth types',
    'task_description': 'Define authentication types',
    'files': {
        'create': ['src/auth/types.ts'],
        'modify': [],
        'read': ['src/config.ts']
    },
    'acceptance_criteria': ['AuthUser type defined', 'Token type defined'],
    'verification': {'command': 'npm test'},
    'scope': 'auth'
}

output = render('implementer.md', context)
assert 'TASK-001' in output
assert 'Create auth types' in output
assert 'src/auth/types.ts' in output
assert 'npm test' in output

print('OK: Template engine works')
print(output[:500])
"
```

## Test Cases

```python
# .zerg/tests/test_templates.py
import pytest
from template_engine import TemplateEngine, render

def test_simple_variable():
    engine = TemplateEngine()
    template = "Hello {{name}}"
    result = engine._render_template(template, {'name': 'World'})
    assert result == "Hello World"

def test_nested_variable():
    engine = TemplateEngine()
    template = "File: {{files.create}}"
    result = engine._render_template(template, {'files': {'create': 'test.py'}})
    assert result == "File: test.py"

def test_each_block():
    engine = TemplateEngine()
    template = "{{#each items}}- {{this}}\n{{/each}}"
    result = engine._render_template(template, {'items': ['a', 'b', 'c']})
    assert result == "- a\n- b\n- c\n"

def test_if_block():
    engine = TemplateEngine()
    template = "{{#if show}}Visible{{/if}}"
    assert engine._render_template(template, {'show': True}) == "Visible"
    assert engine._render_template(template, {'show': False}) == ""
```

## Definition of Done

1. All acceptance criteria checked
2. Verification command passes
3. Unit tests pass: `pytest .zerg/tests/test_templates.py`
4. All three templates created and functional
