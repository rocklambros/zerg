#!/bin/bash

WORKER_ID=${ZERG_WORKER_ID:-0}
FEATURE=${ZERG_FEATURE:-unknown}
BRANCH=${ZERG_BRANCH:-main}

echo "═══════════════════════════════════════════════════"
echo "  Factory Worker Starting"
echo "  Worker ID: $WORKER_ID"
echo "  Feature: $FEATURE"
echo "  Branch: $BRANCH"
echo "  Task List: $CLAUDE_CODE_TASK_LIST_ID"
echo "═══════════════════════════════════════════════════"

# Checkout the assigned branch if specified
if [ "$BRANCH" != "main" ] && [ -n "$BRANCH" ]; then
  echo "Checking out branch: $BRANCH"
  git fetch origin 2>/dev/null || true
  git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH"
fi

# Wait for any required services
if [ -f ".devcontainer/wait-for-services.sh" ]; then
  echo "Waiting for services..."
  bash .devcontainer/wait-for-services.sh
fi

# Report ready status
echo ""
echo "Worker $WORKER_ID ready for tasks"
echo ""

# If running in orchestrated mode, start Claude Code
if [ "$ZERG_ORCHESTRATED" = "true" ]; then
  echo "Starting Claude Code in worker mode..."
  exec claude --dangerously-skip-permissions \
    -p "You are Factory Worker $WORKER_ID. Run /worker to begin execution."
fi
