FROM mcr.microsoft.com/devcontainers/base:ubuntu

ARG NODE_VERSION=20
ARG PYTHON_VERSION=3.12

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# System dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    jq \
    netcat-openbsd \
    build-essential \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION}.x | bash - \
    && apt-get install -y nodejs

# Configure npm for global installs
ENV NPM_CONFIG_PREFIX=/root/.npm-global
ENV PATH=$NPM_CONFIG_PREFIX/bin:$PATH
RUN mkdir -p $NPM_CONFIG_PREFIX

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Install common MCP servers
RUN npm install -g \
    @anthropic-ai/mcp-server-filesystem \
    @anthropic-ai/mcp-server-github \
    2>/dev/null || true

# Install Python dependencies for ZERG
RUN pip3 install --break-system-packages \
    pyyaml \
    requests \
    pydantic \
    click \
    rich \
    jsonschema

# Create directories
RUN mkdir -p /root/.claude/tasks /workspace

# Set working directory
WORKDIR /workspace

# Default command
CMD ["bash"]
