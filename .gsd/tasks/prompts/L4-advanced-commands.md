# L4-TASK-001: /zerg:git Command

## Objective

Implement git operations with intelligent commits and finish workflow.

## Context

**Depends on**: L1-TASK-001 (Worktree Manager)

The git command provides smart git operations including the critical "finish" workflow for completing development branches.

## Files to Create

```
.claude/commands/
└── zerg:git.md

.zerg/
└── git_ops.py
```

## Actions

### commit
Intelligent commit with auto-generated conventional message:
```bash
/zerg:git --action commit [--push]
```

### branch
Branch management:
```bash
/zerg:git --action branch --name feature/auth
```

### merge
Intelligent merge with conflict detection:
```bash
/zerg:git --action merge --branch feature/auth --strategy squash
```

### sync
Synchronize with remote:
```bash
/zerg:git --action sync
```

### history
Analyze and generate changelog:
```bash
/zerg:git --action history --since v1.0.0
```

### finish (CRITICAL)
Complete development branch with structured options:

```bash
/zerg:git --action finish [--base main]
```

**Finish Workflow**:

```
Implementation complete. All tests passing. What would you like to do?

1. Merge back to main locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work

Which option?
```

**Finish Logic**:

```python
def finish_branch(branch: str, base: str = "main") -> FinishResult:
    # Step 1: Verify tests pass (REQUIRED)
    test_result = run_project_tests()
    if not test_result.passed:
        return FinishResult(
            blocked=True,
            reason=f"Tests failing ({test_result.failures} failures)"
        )
    
    # Step 2: Present options
    choice = present_finish_options(branch, base)
    
    # Step 3: Execute choice
    if choice == 1:  # Merge locally
        checkout(base)
        merge(branch, no_ff=True)
        verify_tests()
        delete_branch(branch)
        cleanup_worktree(branch)
        
    elif choice == 2:  # Create PR
        push(branch, set_upstream=True)
        create_pr(title, body)
        
    elif choice == 3:  # Keep as-is
        pass
        
    elif choice == 4:  # Discard
        if confirm_discard():
            delete_branch(branch, force=True)
            cleanup_worktree(branch)
```

## Verification

```bash
cd .zerg && python -c "
from git_ops import GitOps
go = GitOps()
print('Available actions:', go.available_actions())
"
```

---

# L4-TASK-002: /zerg:build Command

## Objective

Implement build orchestration with error recovery.

## Files to Create

```
.claude/commands/
└── zerg:build.md

.zerg/
└── build.py
```

## Capabilities

1. **Auto-detect**: npm, cargo, make, gradle, go
2. **Error Recovery**: Classify and retry with fixes
3. **Retry Logic**: Up to 3 attempts
4. **Build Report**: Timing, artifact sizes
5. **Watch Mode**: Rebuild on changes

## Error Recovery Categories

- **missing_dependency**: Run install command
- **type_error**: Suggest fix
- **resource_exhaustion**: Reduce parallelism
- **network_timeout**: Retry with backoff

## Usage

```bash
/zerg:build [--target all]
            [--mode dev|staging|prod]
            [--clean]
            [--watch]
            [--retry 3]
```

---

# L4-TASK-003: /zerg:session Command

## Objective

Implement session save/load for multi-session continuity.

## Files to Create

```
.claude/commands/
└── zerg:session.md

.zerg/
└── session.py
```

## Actions

### save
```bash
/zerg:session --action save [--name my-session] [--compress]
```

Saves:
- Execution state
- Task progress
- Worker checkpoints
- Spec files

### load
```bash
/zerg:session --action load --name my-session
```

### list
```bash
/zerg:session --action list
```

### delete
```bash
/zerg:session --action delete --name old-session
```

## Session Manifest

```json
{
  "name": "my-session",
  "created_at": "2025-01-25T12:00:00Z",
  "feature": "auth-system",
  "level": 2,
  "tasks_complete": 12,
  "tasks_total": 47,
  "checksums": {
    "state.json": "abc123",
    "task-graph.json": "def456"
  }
}
```

---

# L4-TASK-004: /zerg:index Command

## Objective

Implement project knowledge base generation.

## Files to Create

```
.claude/commands/
└── zerg:index.md

.zerg/
├── indexer.py
└── index/              # Index output
```

## Capabilities

1. **Structure Scan**: Project file tree
2. **Symbol Extraction**: Functions, classes, types
3. **Dependency Graph**: Import relationships
4. **Documentation**: Docstrings, README
5. **Vector Embeddings**: Optional semantic search

## Index Output

```json
{
  "files": [
    {
      "path": "src/auth/types.ts",
      "language": "typescript",
      "symbols": [
        {"name": "AuthUser", "type": "interface", "line": 10},
        {"name": "authenticate", "type": "function", "line": 25}
      ],
      "imports": ["../config", "jsonwebtoken"],
      "exports": ["AuthUser", "authenticate"]
    }
  ],
  "dependencies": {
    "src/auth/types.ts": ["src/config.ts"]
  }
}
```

## Usage

```bash
/zerg:index [--format json|sqlite]
            [--embeddings]
            [--include "src/**"]
            [--exclude "node_modules"]
```

---

# L4-TASK-005: /zerg:document Command

## Objective

Implement documentation generation and maintenance.

## Files to Create

```
.claude/commands/
└── zerg:document.md

.zerg/
└── document.py
```

## Document Types

1. **api**: API reference from code
2. **readme**: Project README
3. **architecture**: System architecture
4. **changelog**: From git history

## Usage

```bash
/zerg:document --type api [--output docs/api.md]
/zerg:document --type readme [--update]
/zerg:document --type architecture [--diagram]
```

## Features

- Code structure analysis
- JSDoc/docstring extraction
- Mermaid diagram generation
- Update mode (preserve manual edits)

---

# L4-TASK-006: /zerg:purge Command

## Objective

Implement artifact and worktree cleanup (renamed from cleanup).

## Files to Create

```
.claude/commands/
└── zerg:purge.md

.zerg/
└── purge.py
```

## Targets

1. **worktrees**: Remove `.zerg/worktrees/`
2. **logs**: Remove `.zerg/logs/`
3. **checkpoints**: Remove `.zerg/checkpoints/`
4. **metrics**: Remove `.zerg/metrics/`
5. **all**: Everything above

## Usage

```bash
/zerg:purge [--target worktrees|logs|all]
            [--preserve-specs]
            [--dry-run]
            [--force]
```

## Safety

- Confirm before destructive actions
- Never delete `.gsd/specs/` unless forced
- Dry-run shows what would be deleted
