#!/bin/bash
set -e

echo "═══════════════════════════════════════════════════"
echo "  Factory Worker Post-Create Setup"
echo "  Worker ID: ${ZERG_WORKER_ID:-0}"
echo "  Feature: ${ZERG_FEATURE:-unknown}"
echo "═══════════════════════════════════════════════════"

# Install project dependencies
if [ -f "package.json" ]; then
  echo "Installing Node.js dependencies..."
  if [ -f "pnpm-lock.yaml" ]; then
    npm install -g pnpm && pnpm install
  elif [ -f "yarn.lock" ]; then
    npm install -g yarn && yarn install
  else
    npm install
  fi
fi

if [ -f "requirements.txt" ]; then
  echo "Installing Python dependencies..."
  pip install --break-system-packages -r requirements.txt
fi

if [ -f "pyproject.toml" ]; then
  echo "Installing Python project..."
  pip install --break-system-packages -e .
fi

# Copy MCP server configuration if present
if [ -f ".devcontainer/mcp-servers/config.json" ]; then
  echo "Configuring MCP servers..."
  mkdir -p /root/.claude
  cp .devcontainer/mcp-servers/config.json /root/.claude/mcp_servers.json
fi

# Setup git identity for commits
echo "Configuring git..."
git config --global user.email "zerg-worker-${ZERG_WORKER_ID:-0}@agentic.local"
git config --global user.name "Factory Worker ${ZERG_WORKER_ID:-0}"
git config --global init.defaultBranch main
git config --global pull.rebase true

# Ensure .gsd directory exists
mkdir -p .gsd/specs

echo ""
echo "Post-create setup complete"
echo "═══════════════════════════════════════════════════"
