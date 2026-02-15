# Zerg Launch Week Content — February 9-15, 2026

All final LinkedIn posts and tweets for the Zerg open source launch week. Content is ordered chronologically by publish day. Each post has been optimized for LinkedIn algorithm performance (360Brew model, January 2026), reading level B1 English, and Rock's "grumpy security uncle" voice.

Project: github.com/rocklambros/zerg
Blog: rockcybermusings.com
Version: 0.2.0 (MIT License)

---

## MONDAY — Tease Post (LinkedIn)

**Purpose:** Bridge from last week's teaser campaign into Tuesday's launch. First time naming Zerg publicly.

---

For one week I teased a project. Tomorrow the Zerg rush begins.

I told you about context rot. How your AI forgets its own security decisions by file 12.

I told you most security rules bloat context windows without making code safer. That filtering by file type cuts waste and sharpens output.

I told you AI coding without container isolation is reckless. That LD_PRELOAD and PYTHONPATH have no business in an agent's environment.

Each post ended the same way. "I'm building something."

Tomorrow you see what it is.

Zerg. Parallel Claude Code orchestration built security-first. Named after the Starcraft swarm because that's exactly how it works. Spawn workers. Overwhelm the problem. Win through coordinated aggression.

Except these zerglings write secure code. They read specs instead of conversation history. They crash and recover without losing progress. And they can't poison each other because every worker runs in its own worktree.

I've been running this on my own projects for months. Tomorrow the repo goes public, the blog drops, and you can judge for yourself.

Fair warning. Once you see five Claude Code instances working a feature in parallel, you won't go back to one.

Tomorrow. The swarm launches.

👉 Follow and connect for more AI and cybersecurity insights with the occasional rant

#AgenticAI #SecureCoding #ClaudeCode

---

## TUESDAY — Launch Post (LinkedIn)

**Purpose:** Full announcement. Drive stars, clones, blog reads. Anchor post for the week.

**First Comment:** Full technical breakdown on how the architecture works, why I made the security decisions I did, and how to get started in 5 minutes. [BLOG URL] | Repo: github.com/rocklambros/zerg

---

The Swarm is here. I built a zergling rush for Claude Code.

Every major AI coding assistant got pwned last year. GitHub Copilot. Cursor. Windsurf. Claude Code. JetBrains Junie. All of them.

The IDEsaster disclosure documented 30+ vulnerabilities across the entire AI IDE ecosystem. 100% of tested tools were vulnerable to prompt injection that chains through normal IDE features into remote code execution and data theft.

[Source: "IDEsaster: A Novel Vulnerability Class in AI IDEs," Ari Marzouk (MaccariTA), December 2025]

I watched this unfold while building parallel Claude Code infrastructure. The speed gains from running multiple agents were obvious.

The security gaps were terrifying.

So I built Zerg. Named after the swarm for a reason. Spawn workers fast, overwhelm the problem, win through coordinated aggression. Except these zerglings write secure code and don't die to a wall of siege tanks.

Parallel Claude Code orchestration with security, context engineering, and crash recovery built in from day one.

Not bolted on. Not "coming in phase two." Built in.

Here's what it does that nothing else combines into one system.

→ Three rush modes (task, subprocess, container) for different isolation levels
→ Context engineering that cuts tokens 30-50% per worker
→ Crash recovery with circuit breakers and heartbeat monitoring
→ OWASP security rules fetched from external repos so poisoned commits can't degrade your baseline
→ Pre-commit hooks that catch secrets before they reach your repo

The task graph gives each file one owner. No two workers touch the same file in the same level. Merge conflicts become structurally impossible.

Container mode runs workers as non-root UID 10001 with LD_PRELOAD blocked. Even if prompt injection succeeds, blast radius stays contained.

Every token in a worker's context window is a potential injection vector. Fewer tokens means fewer attack surfaces. Context engineering is security engineering.

Version 0.2.0 is live. Open source. MIT license.

Star it. Clone it. Break it. Tell me what fails.

The agentic AI industry is obsessed with autonomy. It should be obsessed with recovery.

You must construct additional pylons. Or just /zerg:rush.

👉 Follow and connect for more AI and cybersecurity insights with the occasional rant

#AgenticAI #SecureCoding #ClaudeCode

---

## WEDNESDAY — Deep Dive: Context Engineering (LinkedIn)

**Purpose:** Technical depth on token reduction. Drive engagement and saves. Position context engineering as security engineering.

**First Comment:** Link to repo with context engineering docs.

---

Zerg workers don't load your whole security rulebook. Here's why.

I ran five Claude Code instances on a Python API last month. Each one got the full security rule set. JavaScript rules. Docker rules. Kubernetes rules. Every language. Every framework.

For a Python project.

70% of the tokens in each worker's context were dead weight. Paid for. Processed. Ignored.

This is the dirty secret of parallel AI coding. Multiply one agent's waste by five and your costs don't scale linearly. They explode.

Chroma's research on context degradation found that LLM performance grows "increasingly unreliable as input length grows." More context doesn't mean better output. Past a threshold, it means worse output that costs more.

[Source: "Context Rot," Hong et al., Chroma Research, 2025]

So I built context engineering into Zerg from the start. Three mechanisms.

Command splitting breaks large instruction files into core docs (30% of tokens) and reference docs (70%). Workers load only what their task needs.

Security rule filtering matches rules to file extensions. A Python task gets Python rules. Not JavaScript. Not Go. Not everything.

Task-scoped context gives each worker spec excerpts within a 4,000 token budget. Not the whole spec. Just what matters for that task.

The result is 30-50% fewer tokens per worker. Across five workers, that savings compounds fast.

But here's what most people miss. Token reduction is also attack surface reduction. Every token in a worker's context is a potential prompt injection vector. IDEsaster proved that. Fewer tokens means fewer ways in.

Context engineering is security engineering. Most people treat them as separate problems. They aren't.

Link in comments to see how this works inside Zerg.

👉 Follow and connect for more AI and cybersecurity insights with the occasional rant

#AgenticAI #ContextEngineering #ClaudeCode

---

## THURSDAY — Deep Dive: Spec-Driven Execution + Task Graph (LinkedIn)

**Purpose:** Architecture post. Show how Zerg coordinates workers. Includes Serena comparison for credibility and honesty.

**First Comment:** Link to repo.

---

Zerg workers don't remember anything. That's the whole point.

I used to run Serena as my MCP coding toolkit. Symbol-level code retrieval. Semantic editing. Legitimately smart about navigating large codebases.

But Serena stores state in conversation history and memory files. For a single agent on a focused task, that works. The moment I tried coordinating multiple agents, it fell apart.

Memory files filled up. Context windows bloated. Claude kept reading symbol bodies it didn't need despite being told not to. And when a session crashed, all that accumulated context vanished.

That was the night I decided workers should be stateless.

Conversation history is the worst possible memory system for parallel coding agents. It bloats over time. It degrades over distance. And it dies when a process dies.

In Zerg, no worker relies on conversation history. Every worker reads from spec files. requirements.md. design.md. task-graph.json. If a worker crashes, another picks up the same task and reads the same specs. No context lost. No decisions forgotten.

The task graph is where it gets interesting.

Every file in the project gets assigned to exactly one worker per execution level. Worker 1 owns models/product.py. Worker 2 owns models/cart.py. Worker 3 owns models/order.py. No overlap. No negotiation.

59% of developers now run three or more AI tools in parallel. Most deal with merge conflicts at the end. Zerg eliminates them at the design phase.

[Source: AI Coding Statistics, Second Talent / Stack Overflow Developer Survey, 2025]

Levels enforce dependency order. Level 1 builds the foundation. All workers must pass quality gates before Level 2 starts. No partial merges. No broken intermediate states.

The result looks like waterfall on paper. In practice it runs like a swarm. Four workers finishing a level in minutes instead of one agent grinding through it sequentially.

Serena is great at what it does. I still respect the project. But it was built for a single agent with memory. Zerg was built for a swarm without it.

Spec as memory. Exclusive file ownership. Level-gated execution. That's how you coordinate a swarm without the chaos.

Link to the repo in comments.

👉 Follow and connect for more AI and cybersecurity insights with the occasional rant

#AgenticAI #SecureCoding #ClaudeCode

---

## SATURDAY — Deep Dive: Security / Containerization (LinkedIn)

**Purpose:** Security-first architecture deep dive. Weekend reading for practitioners. Drive repo stars and clones.

**First Comment:** Link to repo.

---

Zerg assumes every worker can be compromised. Here's what that looks like.

Most parallel coding tools don't ask this question. They should.

IDEsaster proved that 100% of tested AI IDEs were vulnerable to prompt injection. A poisoned README or a malicious MCP server can hijack your agent's behavior. That's bad enough with one agent.

Now run five of them with shared access to your file system, environment variables, and cloud credentials.

[Source: "IDEsaster: A Novel Vulnerability Class in AI IDEs," Ari Marzouk (MaccariTA), December 2025]

That assumption changed every design decision.

Container mode runs workers as non-root UID 10001. Environment filtering blocks LD_PRELOAD, PYTHONPATH, and other injection vectors. Your SSH keys, cloud tokens, and API secrets stay out of reach unless you explicitly pass them in.

Git worktree isolation means each worker gets its own directory. Workers can't see each other's changes. If one gets hijacked through prompt injection, it can't modify another worker's files or poison the shared codebase.

OWASP security rules get fetched from an external repository during initialization. Not bundled locally. Not stored in your project. Why? Because a compromised developer machine or a poisoned commit can't degrade externally sourced rules. The security baseline stays clean even if your repo doesn't.

Pre-commit hooks run before any worker pushes code. Secret detection. Security rule validation. Even if a worker hallucinates insecure code, the commit fails before it reaches your branch.

This is defense in depth for AI coding agents. Not one wall. Layers.

Most orchestration tools optimize for speed and autonomy. Zerg optimizes for blast radius containment. Fast is useless if a single compromised worker can take down the whole project.

Link to the repo in comments.

👉 Follow and connect for more AI and cybersecurity insights with the occasional rant

#AgenticAI #SecureCoding #ClaudeCode

---

## TWEETS — Post Throughout the Week

**Purpose:** Complementary X/Twitter content. Each tweet is standalone, under 280 characters. Post 1-2 per day to drive traffic to LinkedIn posts and the repo.

---

### Tweet 1 — Launch Day (Tuesday)

Zerg is live. Parallel Claude Code orchestration with security built in from day one. Not bolted on. Not "phase two." Open source, MIT license. github.com/rocklambros/zerg

### Tweet 2 — IDEsaster Angle (Tuesday)

100% of tested AI IDEs were vulnerable to prompt injection last year. Then people started running five of them in parallel. I built Zerg because that math scared me. github.com/rocklambros/zerg

### Tweet 3 — Starcraft Hook (Wednesday)

Named it Zerg for a reason. Spawn workers. Overwhelm the problem. Win through coordinated aggression. Except these zerglings write secure code and don't die to siege tanks. github.com/rocklambros/zerg

### Tweet 4 — Context Engineering (Wednesday)

Your AI coding agent loads every security rule for every language into every task. 70% of those tokens are waste. Zerg filters rules by file type. 30-50% fewer tokens per worker. Fewer tokens = fewer prompt injection vectors.

### Tweet 5 — Merge Conflicts (Thursday)

Most parallel agent tools let workers race each other, then deal with merge conflicts at the end. Zerg assigns each file to exactly one worker. Conflicts become structurally impossible.

### Tweet 6 — Spec as Memory (Thursday)

Conversation history dies when a process crashes. Specs don't. Zerg workers are stateless. They read requirements.md, not chat logs. Crash one, restart it, zero context lost.

### Tweet 7 — Container Isolation (Friday)

Zerg container mode: non-root UID 10001, LD_PRELOAD blocked, environment variables filtered. Even if prompt injection succeeds, blast radius stays contained. Security isn't a feature flag. It's architecture.

### Tweet 8 — Philosophy (Saturday)

The agentic AI industry is obsessed with autonomy. It should be obsessed with recovery. What happens when one of your five parallel agents crashes at 2 AM? That question shaped every decision in Zerg.

### Tweet 9 — Open Source CTA (Saturday)

Zerg v0.2.0. 26 slash commands. Three rush modes. OWASP security rules fetched from external repos. Pre-commit secret detection. Open source. Star it. Clone it. Break it. Tell me what fails. github.com/rocklambros/zerg

### Tweet 10 — Closing Zinger (Sunday)

You must construct additional pylons. Or just /zerg:rush.

---

## REFERENCE — Key Data Points and Citations

These citations have been web-verified and can be reused across content:

1. **IDEsaster Disclosure:** "IDEsaster: A Novel Vulnerability Class in AI IDEs," Ari Marzouk (MaccariTA), December 2025. 30+ vulnerabilities, 24 CVEs, 100% of tested AI IDEs vulnerable. Source: maccarita.com/posts/idesaster/

2. **Context Rot Research:** "Context Rot," Hong et al., Chroma Research, 2025. "Models do not use their context uniformly; performance grows increasingly unreliable as input length grows." Presented at NeurIPS 2025 workshop.

3. **Parallel AI Tool Usage:** 59% of developers run three or more AI coding tools in parallel (Second Talent / Stack Overflow Developer Survey, 2025).

4. **AI-Generated PR Rejection:** 67.3% of AI-generated PRs get rejected vs 15.6% for manual code (LinearB data, cited in Mike Mason's analysis, January 2026).

5. **AI Code Security Flaws:** 45% of LLM-generated code had security flaws, Java hit 72% failure rate (Veracode 2025 GenAI Code Security Report).

---

## REFERENCE — Zerg Key Features

For quick reference when creating additional content:

- **Three rush modes:** task, subprocess, container (different isolation levels)
- **Context engineering:** command splitting (30/70), security rule filtering by file extension, 4,000 token task budgets. 30-50% token reduction per worker.
- **Spec-driven execution:** workers read spec files not conversation history. Stateless and restartable.
- **Exclusive file ownership:** task graph assigns each file to one worker per level. Merge conflicts structurally impossible.
- **Level-gated execution:** all workers must pass quality gates before next level starts.
- **Crash recovery:** circuit breakers (5 failures, 60s cooldown), heartbeat monitoring, backpressure zones (green/yellow/red).
- **Security:** container isolation (UID 10001, LD_PRELOAD blocked), external OWASP rule fetching from TikiTribe repo, pre-commit hooks with secret detection, git worktree isolation per worker.
- **26 slash commands** with /z: shortcuts.
- **Diagnostics engine:** Bayesian hypothesis testing against 30+ known failure patterns across Python, JavaScript, Go, Rust.
- **Version:** 0.2.0, MIT license, pip install zerg-ai
