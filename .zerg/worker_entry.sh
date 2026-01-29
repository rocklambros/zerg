#!/bin/bash
# ZERG Worker Entry - Invokes worker_main to execute assigned tasks
set -e

WORKER_ID=${ZERG_WORKER_ID:-0}
FEATURE=${ZERG_FEATURE}
WORKTREE=${ZERG_WORKTREE:-/workspace}
BRANCH=${ZERG_BRANCH}
SPEC_DIR=${ZERG_SPEC_DIR}

echo "========================================"
echo "ZERG Worker $WORKER_ID starting..."
echo "Feature: $FEATURE"
echo "Worktree: $WORKTREE"
echo "Branch: $BRANCH"
echo "Spec Dir: $SPEC_DIR"
echo "========================================"

cd "$WORKTREE"

# Fix git worktree paths for container environment
# The worktree metadata is mounted from the host but uses host-specific paths.
# We create a local copy of the metadata and fix paths without modifying the mounted original.
if [ -n "$ZERG_GIT_WORKTREE_DIR" ] && [ -d "$ZERG_GIT_WORKTREE_DIR" ]; then
    echo "Setting up git worktree for container..."
    LOCAL_GIT_DIR="$WORKTREE/.git-local"

    # Create a local copy of worktree metadata
    rm -rf "$LOCAL_GIT_DIR"
    cp -r "$ZERG_GIT_WORKTREE_DIR" "$LOCAL_GIT_DIR"

    # Point worktree's .git to local copy
    echo "gitdir: $LOCAL_GIT_DIR" > "$WORKTREE/.git"

    # Fix gitdir in local copy to point to this worktree
    echo "$WORKTREE/.git" > "$LOCAL_GIT_DIR/gitdir"

    # Fix commondir to point to mounted main repo's .git
    if [ -n "$ZERG_GIT_MAIN_DIR" ]; then
        echo "$ZERG_GIT_MAIN_DIR" > "$LOCAL_GIT_DIR/commondir"
    fi

    echo "Git worktree configured: LOCAL_GIT_DIR=$LOCAL_GIT_DIR"

    # Configure git user identity for commits
    git config user.email "zerg-worker@local"
    git config user.name "ZERG Worker $WORKER_ID"
fi

# Create healthcheck marker file (checked by Dockerfile HEALTHCHECK)
touch /tmp/.zerg-alive

# Remove marker on exit to signal unhealthy state
cleanup() {
    rm -f /tmp/.zerg-alive
}
trap cleanup EXIT

# Install ZERG dependencies if not already installed
if ! python3 -c "import pydantic" 2>/dev/null; then
    echo "Installing ZERG dependencies..."
    pip3 install -q --break-system-packages -e . 2>/dev/null || \
        pip3 install -q --break-system-packages pydantic click rich jsonschema
fi

# Run the ZERG worker main
# Note: Do NOT use 'exec' here -- the container CMD has a fallback sleep
# after this script to keep the container alive for debugging if worker exits.
python3 -m zerg.worker_main \
     --worker-id "$WORKER_ID" \
     --feature "$FEATURE" \
     --worktree "$WORKTREE" \
     --branch "$BRANCH" \
     --verbose
EXIT_CODE=$?
echo "Worker $WORKER_ID exited with code $EXIT_CODE"
exit $EXIT_CODE
