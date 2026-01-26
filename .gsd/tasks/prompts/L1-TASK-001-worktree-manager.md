# L1-TASK-001: Git Worktree Manager

## Objective

Implement worktree creation, cleanup, and branch management for worker isolation.

## Context

**Depends on**: L0-TASK-001 (Orchestrator Core)

Git worktrees give each worker its own working directory and branch. This prevents conflicts without file locking. Workers can execute in parallel without stepping on each other.

## Files to Modify/Create

```
.zerg/
├── worktree.py       # CREATE: WorktreeManager class
└── orchestrator.py   # MODIFY: Integrate worktree manager
```

## Implementation Requirements

### WorktreeManager Class

```python
import subprocess
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Worktree:
    """Represents a git worktree."""
    path: Path
    branch: str
    worker_id: str
    created_at: datetime

class WorktreeManager:
    """Manages git worktrees for worker isolation."""
    
    WORKTREE_DIR = ".zerg/worktrees"
    BRANCH_PREFIX = "zerg"
    
    def __init__(self, repo_root: Path = None):
        self.repo_root = repo_root or Path.cwd()
        self.worktrees: dict[str, Worktree] = {}
        
    def create(self, worker_id: str, base_branch: str = "main") -> Worktree:
        """Create worktree for worker.
        
        Creates:
        - Branch: zerg/worker-{worker_id}
        - Worktree: .zerg/worktrees/worker-{worker_id}
        """
        branch_name = f"{self.BRANCH_PREFIX}/worker-{worker_id}"
        worktree_path = self.repo_root / self.WORKTREE_DIR / f"worker-{worker_id}"
        
        # Create branch from base
        self._run_git(["branch", branch_name, base_branch])
        
        # Create worktree
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        self._run_git(["worktree", "add", str(worktree_path), branch_name])
        
        wt = Worktree(
            path=worktree_path,
            branch=branch_name,
            worker_id=worker_id,
            created_at=datetime.now()
        )
        self.worktrees[worker_id] = wt
        return wt
    
    def cleanup(self, worker_id: str) -> None:
        """Remove worktree and optionally delete branch."""
        wt = self.worktrees.get(worker_id)
        if not wt:
            return
            
        # Remove worktree
        self._run_git(["worktree", "remove", str(wt.path), "--force"])
        
        # Prune worktree references
        self._run_git(["worktree", "prune"])
        
        del self.worktrees[worker_id]
    
    def merge_to_base(self, worker_id: str, base_branch: str = "main") -> MergeResult:
        """Merge worker branch back to base."""
        wt = self.worktrees.get(worker_id)
        if not wt:
            raise ValueError(f"No worktree for worker {worker_id}")
        
        # Checkout base branch (in main repo)
        self._run_git(["checkout", base_branch])
        
        # Merge worker branch
        result = self._run_git(
            ["merge", "--no-ff", wt.branch, "-m", f"Merge {wt.branch}"],
            check=False
        )
        
        if result.returncode != 0:
            return MergeResult(success=False, conflicts=self._get_conflicts())
        
        return MergeResult(success=True, conflicts=[])
    
    def _run_git(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Execute git command."""
        return subprocess.run(
            ["git"] + args,
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=check
        )
    
    def _get_conflicts(self) -> list[str]:
        """Get list of conflicting files."""
        result = self._run_git(["diff", "--name-only", "--diff-filter=U"], check=False)
        return result.stdout.strip().split('\n') if result.stdout else []
```

### MergeResult

```python
@dataclass
class MergeResult:
    success: bool
    conflicts: list[str]
    commit_sha: Optional[str] = None
```

### Level Completion Merge

```python
def merge_level_branches(self, level: int, worker_ids: list[str]) -> LevelMergeResult:
    """Sequentially merge all worker branches for a level."""
    results = []
    
    for worker_id in worker_ids:
        result = self.merge_to_base(worker_id)
        results.append(result)
        
        if not result.success:
            # Stop on first conflict
            return LevelMergeResult(
                success=False,
                failed_worker=worker_id,
                conflicts=result.conflicts
            )
    
    return LevelMergeResult(success=True, merged_count=len(worker_ids))
```

## Acceptance Criteria

- [ ] Create worktree at `.zerg/worktrees/worker-{N}`
- [ ] Create branch `zerg/worker-{N}` from base
- [ ] Cleanup worktree on worker completion
- [ ] Sequential merge after level completion
- [ ] Handle merge conflicts gracefully (return conflict list)
- [ ] Prune stale worktree references

## Verification

```bash
cd .zerg && python -c "
from worktree import WorktreeManager

wm = WorktreeManager()

# Create worktree
wt = wm.create('test-001')
assert wt.path.exists()
assert wt.branch == 'zerg/worker-test-001'

# Verify git recognizes it
import subprocess
result = subprocess.run(['git', 'worktree', 'list'], capture_output=True, text=True)
assert 'worker-test-001' in result.stdout

# Cleanup
wm.cleanup('test-001')
assert not wt.path.exists()

print('OK: Worktree manager works')
"
```

## Integration with Orchestrator

Update `orchestrator.py`:

```python
class Orchestrator:
    def __init__(self, ...):
        ...
        self.worktree_manager = WorktreeManager()
    
    def spawn_worker(self, worker_id: str, task: Task) -> Worker:
        # Create isolated worktree
        worktree = self.worktree_manager.create(worker_id)
        
        # Launch worker in worktree directory
        return self._launch_worker(worker_id, task, worktree.path)
    
    def complete_level(self, level: int) -> None:
        # Merge all worker branches
        worker_ids = [w.id for w in self.get_level_workers(level)]
        result = self.worktree_manager.merge_level_branches(level, worker_ids)
        
        if not result.success:
            raise MergeConflictError(result.conflicts)
```

## Test Cases

```python
# .zerg/tests/test_worktree.py
import pytest
from pathlib import Path
from worktree import WorktreeManager

@pytest.fixture
def git_repo(tmp_path):
    """Create a test git repo."""
    import subprocess
    subprocess.run(['git', 'init'], cwd=tmp_path)
    subprocess.run(['git', 'commit', '--allow-empty', '-m', 'Initial'], cwd=tmp_path)
    return tmp_path

def test_create_worktree(git_repo):
    wm = WorktreeManager(git_repo)
    wt = wm.create('w1')
    assert wt.path.exists()
    assert wt.branch == 'zerg/worker-w1'

def test_cleanup_worktree(git_repo):
    wm = WorktreeManager(git_repo)
    wt = wm.create('w1')
    wm.cleanup('w1')
    assert not wt.path.exists()

def test_merge_no_conflicts(git_repo):
    wm = WorktreeManager(git_repo)
    wt = wm.create('w1')
    # Create a file in worktree
    (wt.path / 'test.txt').write_text('hello')
    # Commit in worktree
    subprocess.run(['git', 'add', '.'], cwd=wt.path)
    subprocess.run(['git', 'commit', '-m', 'Add test'], cwd=wt.path)
    # Merge back
    result = wm.merge_to_base('w1')
    assert result.success
```

## Definition of Done

1. All acceptance criteria checked
2. Verification command passes
3. Unit tests pass: `pytest .zerg/tests/test_worktree.py`
4. Orchestrator integration complete
5. `.zerg/worktrees/` added to `.gitignore`
