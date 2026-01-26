# L2-TASK-001: /zerg:init Command Update

## Objective

Update init command to generate v2 directory structure and orchestrator configuration.

## Context

**Depends on**: L0-TASK-002, L1-TASK-004

The init command sets up a project for ZERG. This update adds v2 structure with schemas, templates, and proper config.

## Files to Modify/Create

```
.claude/commands/
└── zerg:init.md          # MODIFY: Update prompt

.zerg/
└── init_generator.py     # CREATE: Generation logic
```

## Implementation Requirements

Update the `/zerg:init` command to:

1. **Detect Project Type**:
   - Language (Python, TypeScript, Rust, Go)
   - Framework (Express, FastAPI, React, etc.)
   - Package manager (npm, pip, cargo)

2. **Generate v2 Structure**:
```
.zerg/
├── config.json           # Project configuration
├── schemas/              # JSON schemas
├── templates/            # Worker prompts
└── logs/                 # Log directory
```

3. **Create config.json**:
```json
{
  "version": "2.0.0",
  "project": {
    "name": "detected-name",
    "language": "detected-language",
    "framework": "detected-framework"
  },
  "orchestrator": {
    "max_workers": 5,
    "heartbeat_interval": 30,
    "context_threshold": 0.70
  },
  "quality_gates": {
    "stage_1": ["spec_compliance"],
    "stage_2": ["lint", "test", "security"]
  }
}
```

## Verification

```bash
# In a test project directory
/zerg:init

# Verify output
ls -la .zerg/
cat .zerg/config.json | python -m json.tool
ls .zerg/templates/
```

## Definition of Done

1. Command generates v2 structure
2. config.json has valid schema
3. Templates are populated
4. Language/framework auto-detected

---

# L2-TASK-002: /zerg:rush Command Update

## Objective

Update rush command to use Python orchestrator instead of shell coordination.

## Context

**Depends on**: L0-TASK-001, L0-TASK-003, L1-TASK-001, L1-TASK-003

Rush is the main execution command. This update integrates the Python orchestrator for proper level synchronization and worker management.

## Files to Modify/Create

```
.claude/commands/
└── zerg:rush.md          # MODIFY: Update prompt

.zerg/
└── rush.py               # CREATE: Rush command logic
```

## Implementation Requirements

### Rush Command Class

```python
class RushCommand:
    """Execute task graph with orchestrator."""
    
    def __init__(self):
        self.orchestrator = Orchestrator()
    
    def execute(
        self,
        workers: int = 5,
        dry_run: bool = False,
        resume: bool = False
    ) -> ExecutionResult:
        """Execute the task graph."""
        
        # Load or resume state
        if resume:
            state = ExecutionState.load()
        else:
            state = ExecutionState.create(self._get_feature_name())
        
        # Load task graph
        graph = TaskGraph.from_file(self._get_graph_path())
        
        if dry_run:
            return self._dry_run(graph)
        
        # Execute with orchestrator
        return self.orchestrator.start(graph, workers)
```

### Command Prompt Updates

```markdown
## Usage

/zerg:rush [--workers N] [--dry-run] [--resume]

## Behavior

1. Load task graph from `.gsd/specs/{feature}/task-graph.json`
2. Validate graph (dependencies, file ownership)
3. Start orchestrator with N workers
4. Execute levels sequentially with barriers
5. Run quality gates between levels
6. Report progress via /zerg:status
```

## Verification

```bash
cd .zerg && python -c "
from rush import RushCommand

rc = RushCommand()

# Test dry run
result = rc.execute(dry_run=True)
assert result.validated

print('OK: Rush command ready')
"
```

## Definition of Done

1. Rush invokes Python orchestrator
2. Level barriers enforced
3. Progress reported to status
4. Resume from checkpoint works

---

# L2-TASK-003: /zerg:worker Command Update

## Objective

Update worker command with TDD protocol and verification-before-completion.

## Context

**Depends on**: L0-TASK-004, L1-TASK-004

Workers must follow strict protocols: TDD for code tasks, verification before claiming completion, and self-review before handoff.

## Files to Modify/Create

```
.claude/commands/
└── zerg:worker.md        # MODIFY: Add protocols

.zerg/
└── worker_protocol.py    # CREATE: Protocol enforcement
```

## Implementation Requirements

### TDD Enforcement

```python
def enforce_tdd(spec: TaskSpec) -> TDDResult:
    """Enforce red-green-refactor cycle."""
    
    # Step 1: Write test
    # Step 2: Run test - MUST FAIL
    # Step 3: Write implementation
    # Step 4: Run test - MUST PASS
    # Step 5: Refactor if needed
```

### Verification Protocol

```python
def verify_before_completion(spec: TaskSpec) -> Verification:
    """THE IRON LAW: No completion without fresh verification."""
    
    # Run verification command
    result = run_command(spec.verification.command)
    
    # Parse output
    # Return evidence
```

### Forbidden Phrases

Worker must NOT use:
- "should work now"
- "probably passes"
- "seems correct"
- "looks good"

## Verification

```bash
# Manual test with /zerg:worker
# Verify TDD steps in output
# Verify verification command is run
```

## Definition of Done

1. TDD protocol documented and enforced
2. Verification-before-completion required
3. Self-review checklist included

---

# L2-TASK-004: /zerg:status Command Update

## Objective

Update status command with v2 dashboard format and worker health.

## Context

**Depends on**: L0-TASK-002, L1-TASK-005

Status provides real-time visibility into execution progress, worker states, and quality gate results.

## Files to Modify/Create

```
.claude/commands/
└── zerg:status.md        # MODIFY: Dashboard format

.zerg/
└── status.py             # CREATE: Status rendering
```

## Dashboard Format

```
ZERG Status - Project: my-feature
═══════════════════════════════════════════════════════════════

Progress: Level 2/5 | Tasks: 12/47 (25.5%) | Workers: 4/5 active

Level 1 [████████████████████] 100% (8/8 tasks) ✓
Level 2 [████████░░░░░░░░░░░░]  40% (4/10 tasks)
Level 3 [░░░░░░░░░░░░░░░░░░░░]   0% (0/15 tasks) ⏳

Workers:
  [1] feature-001 ● EXECUTING  TASK-009 (2m 15s)
  [2] feature-002 ● VERIFYING  TASK-010
  [3] feature-003 ○ IDLE

Quality Gates: spec-compliance ✓ | code-quality ✓

Elapsed: 8m 23s | Estimated: 24m remaining
```

## Verification

```bash
cd .zerg && python -c "
from status import StatusCommand

sc = StatusCommand()
dashboard = sc.format_dashboard()
print(dashboard)
"
```

## Definition of Done

1. Progress bars per level
2. Worker state display
3. Quality gate status
4. JSON output option

---

# L2-TASK-005: /zerg:plan Command Update

## Objective

Add --socratic flag for structured brainstorming.

## Context

**Depends on**: None

Socratic mode guides requirements gathering through three structured rounds of questions.

## Files to Modify

```
.claude/commands/
└── zerg:plan.md          # MODIFY: Add --socratic
```

## Socratic Rounds

**Round 1: Problem Space**
- What problem are we solving?
- Who are the users?
- Why does this matter?

**Round 2: Solution Space**
- What does success look like?
- What are the constraints?
- What can we NOT do?

**Round 3: Implementation Space**
- What's the MVP?
- What can we defer?
- What are the risks?

## Verification

```bash
# Manual test
/zerg:plan my-feature --socratic --rounds 3
# Verify three-round structure
```

## Definition of Done

1. --socratic flag works
2. --rounds configurable
3. Transcript captured in requirements

---

# L2-TASK-006: /zerg:design Command Update

## Objective

Update design to generate v2 task graph schema with file ownership validation.

## Context

**Depends on**: L0-TASK-003

Design produces the task graph that drives execution. v2 schema adds explicit file ownership and verification commands.

## Files to Modify

```
.claude/commands/
└── zerg:design.md        # MODIFY: v2 schema
```

## Task Graph v2 Schema

```json
{
  "tasks": [
    {
      "id": "TASK-001",
      "title": "Create auth types",
      "level": 0,
      "dependencies": [],
      "files": {
        "create": ["src/auth/types.ts"],
        "modify": [],
        "read": ["src/config.ts"]
      },
      "acceptance_criteria": ["AuthUser type exported"],
      "verification": {
        "command": "npm test -- --grep auth",
        "timeout_seconds": 60
      },
      "agents_required": ["coder", "reviewer"]
    }
  ]
}
```

## Verification

```bash
# After running /zerg:design
python -c "
import json
from jsonschema import validate

schema = json.load(open('.zerg/schemas/task-graph.schema.json'))
graph = json.load(open('.gsd/specs/test/task-graph.json'))
validate(graph, schema)
print('OK: Valid v2 task graph')
"
```

## Definition of Done

1. v2 schema with files.create/modify/read
2. verification.command per task
3. File ownership validation
4. Mermaid architecture diagram
