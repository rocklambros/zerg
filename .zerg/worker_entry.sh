#!/bin/bash
# ZERG Worker Entry - Invokes Claude with native task list
set -e

WORKER_ID=${ZERG_WORKER_ID:-0}
TASK_LIST_ID=${ZERG_TASK_LIST_ID}
WORKTREE=${ZERG_WORKTREE:-/workspace}

echo "========================================"
echo "ZERG Worker $WORKER_ID starting..."
echo "Task List: $TASK_LIST_ID"
echo "Worktree: $WORKTREE"
echo "========================================"

cd "$WORKTREE"

# Check if Claude CLI is available
if ! command -v claude &> /dev/null; then
    echo "ERROR: Claude CLI not found. Installing..."
    npm install -g @anthropic/claude-code
fi

# Launch Claude Code with task list (native feature)
exec claude --task-list "$TASK_LIST_ID" \
     --dangerously-skip-permissions \
     --env ZERG_WORKER_ID="$WORKER_ID"
