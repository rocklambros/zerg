#!/bin/bash
# ZERG Installation Script
# Copies ZERG files to the current project

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-.}"

echo "Installing ZERG to $TARGET_DIR..."

# Create directories
mkdir -p "$TARGET_DIR/.zerg"
mkdir -p "$TARGET_DIR/.claude/commands/zerg"
mkdir -p "$TARGET_DIR/.claude/commands/z"
mkdir -p "$TARGET_DIR/.devcontainer/mcp-servers"
mkdir -p "$TARGET_DIR/.gsd/specs"

# Copy orchestrator and config
cp "$SCRIPT_DIR/.zerg/orchestrator.py" "$TARGET_DIR/.zerg/"
cp "$SCRIPT_DIR/.zerg/config.yaml" "$TARGET_DIR/.zerg/"

# Copy slash commands into zerg/ and z/ subdirs
cp "$SCRIPT_DIR/.claude/commands/zerg/"*.md "$TARGET_DIR/.claude/commands/zerg/"
cp "$SCRIPT_DIR/.claude/commands/z/"*.md "$TARGET_DIR/.claude/commands/z/"

# Copy devcontainer files
cp "$SCRIPT_DIR/.devcontainer/devcontainer.json" "$TARGET_DIR/.devcontainer/"
cp "$SCRIPT_DIR/.devcontainer/Dockerfile" "$TARGET_DIR/.devcontainer/"
cp "$SCRIPT_DIR/.devcontainer/docker-compose.yaml" "$TARGET_DIR/.devcontainer/"
cp "$SCRIPT_DIR/.devcontainer/post-create.sh" "$TARGET_DIR/.devcontainer/"
cp "$SCRIPT_DIR/.devcontainer/post-start.sh" "$TARGET_DIR/.devcontainer/"
cp "$SCRIPT_DIR/.devcontainer/mcp-servers/config.json" "$TARGET_DIR/.devcontainer/mcp-servers/"

# Make scripts executable
chmod +x "$TARGET_DIR/.zerg/orchestrator.py"
chmod +x "$TARGET_DIR/.devcontainer/post-create.sh"
chmod +x "$TARGET_DIR/.devcontainer/post-start.sh"

echo ""
echo "ZERG installed successfully!"
echo ""
echo "Next steps:"
echo "  1. cd $TARGET_DIR"
echo "  2. claude"
echo "  3. /init"
echo ""
echo "Commands available:"
echo "  /init     - Initialize project infrastructure"
echo "  /plan     - Plan a feature"
echo "  /design   - Design architecture and task graph"
echo "  /rush     - Launch parallel workers"
echo "  /status   - Check progress"
echo ""
