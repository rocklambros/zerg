# Welcome to ZERG

If you've ever wished you could clone yourself to build software faster, ZERG is the next best thing. It coordinates multiple Claude Code instances—called *zerglings*—to work on different parts of your feature simultaneously. While one zergling builds your authentication system, another creates the database models, and a third writes the API endpoints. All at once, all in parallel.

**ZERG** stands for **Zero-Effort Rapid Growth**. The name comes from the StarCraft strategy of overwhelming opponents with coordinated swarm units. In our case, we're overwhelming features with coordinated AI instances.

## Who Is This For?

ZERG is designed for developers who:

- Use Claude Code and want to build features faster
- Have features that can be broken into independent tasks
- Want AI assistance without babysitting each step
- Are comfortable with Python and basic git operations

You don't need to understand distributed systems, container orchestration, or advanced concurrency. ZERG handles the complexity—you focus on describing what you want to build.

---

## How ZERG Works

Here's what happens when you use ZERG to build a feature:

```
                           YOUR FEATURE IDEA
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. PLAN                                                        │
│     ZERG asks questions to understand your requirements.        │
│     Output: requirements.md (your feature spec)                 │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. DESIGN                                                      │
│     ZERG breaks work into atomic tasks with exclusive files.    │
│     Output: task-graph.json (who does what, in what order)      │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. RUSH                                                        │
│                                                                 │
│     Level 1:  [Zergling-0]  [Zergling-1]  [Zergling-2]         │
│                    │             │             │                │
│                    ▼             ▼             ▼                │
│               models.py    api.py        tests/                 │
│                                                                 │
│     ────── wait for Level 1 to complete, then merge ──────     │
│                                                                 │
│     Level 2:  [Zergling-0]  [Zergling-1]                       │
│                    │             │                              │
│                    ▼             ▼                              │
│              services.py   integration/                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                         FEATURE COMPLETE
```

**Why levels?** Some tasks depend on others. You can't write integration tests until the API exists. ZERG groups tasks into *levels* where everything in Level 1 can run in parallel, everything in Level 2 can run in parallel (after Level 1 finishes), and so on.

**Why exclusive files?** Each zergling owns specific files. Zergling-0 might own `models.py`, while Zergling-1 owns `api.py`. This means no merge conflicts within a level—zerglings never step on each other's work.

---

## Find What You Need

### I'm new to ZERG

Start with the **[Tutorial](Tutorial)**. It walks you through building a complete feature from scratch, showing you exactly what to type and what to expect. You'll build a minerals store API and see ZERG in action.

### I want to understand the architecture

Read **[Architecture](Architecture)** for a deep dive into how ZERG's components work together: the launcher, workers, state management, and quality gates.

### I need to look up a specific command

See **[Command-Reference](Command-Reference)** for complete documentation of all 26 commands with flags, examples, and use cases.

### I want to extend ZERG with plugins

Check out **[Plugins](Plugins)** to learn about quality gates, lifecycle hooks, and custom launchers.

---

## Quick Install

Getting ZERG running takes about 2 minutes:

```bash
# 1. Clone the repository
git clone https://github.com/rocklambros/zerg.git && cd zerg

# 2. Install ZERG as an editable package (includes dev dependencies)
pip install -e ".[dev]"

# 3. Install the slash commands into Claude Code
zerg install
```

**What does each step do?**
- `git clone` downloads the ZERG source code
- `pip install -e ".[dev]"` installs ZERG so you can run it, plus development tools like pytest and pre-commit
- `zerg install` copies slash commands (like `/zerg:plan`) into Claude Code so you can use them in any session

**Prerequisites:**
- Python 3.12 or newer
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- Git
- Docker (optional—only needed if you want zerglings to run in containers)

---

## Your First Feature (30-Second Overview)

Once installed, here's the typical workflow inside a Claude Code session:

```bash
/zerg:init                    # Set up ZERG in your project
/zerg:plan user-auth          # Tell ZERG what you want to build
/zerg:design                  # Generate the task breakdown
/zerg:rush --workers=5        # Launch 5 zerglings to build it
/zerg:status                  # Watch progress in real-time
```

Want the full walkthrough? Head to the **[Tutorial](Tutorial)**.

---

## Wiki Pages

| Page | What You'll Learn |
|------|-------------------|
| **[Home](Home)** | You're here! Overview and getting started |
| **[Tutorial](Tutorial)** | Build a complete feature step-by-step with explanations |
| **[Architecture](Architecture)** | How ZERG's internals work and why they're designed that way |
| **[Command-Reference](Command-Reference)** | Every command explained with examples and use cases |
| **[Configuration](Configuration)** | Customize ZERG behavior through config files and environment variables |
| **[Plugins](Plugins)** | Extend ZERG with quality gates, hooks, and custom launchers |
| **[Security](Security)** | How ZERG handles security rules and vulnerability scanning |
| **[Context-Engineering](Context-Engineering)** | How ZERG minimizes token usage (saves money, improves quality) |
| **[Troubleshooting](Troubleshooting)** | When things go wrong: diagnosis and fixes |
| **[FAQ](FAQ)** | Answers to common questions |
| **[Contributing](Contributing)** | How to contribute code, report bugs, or improve docs |

---

## Key Concepts at a Glance

| Concept | What It Means |
|---------|---------------|
| **Zergling** | A single Claude Code instance executing one task. Named after the fast, cheap units from StarCraft. |
| **Level** | A group of tasks that can run in parallel. Level 1 must complete before Level 2 begins. |
| **Spec as Memory** | Zerglings read specification files, not conversation history. This makes them stateless and restartable. |
| **File Ownership** | Each task owns specific files. No two tasks in the same level touch the same file. |
| **Verification** | Every task has an automated pass/fail check. No subjective "looks good" reviews. |

---

## Resources

- [GitHub Repository](https://github.com/rocklambros/zerg) — Source code, issues, and discussions
- [Security Rules](https://github.com/TikiTribe/claude-secure-coding-rules) — Auto-fetched secure coding rules that ZERG applies

---

Ready to build something? Start with the **[Tutorial](Tutorial)** or jump to **[Command-Reference](Command-Reference)** if you already know the basics.
