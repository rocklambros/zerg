
Your goal is to have ZERB be the ultimate parallel execution system for Claude Code that accelerates feature development by spawning multiple Claude instances to work simultaneously. You describe a feature, ZERG captures requirements and designs an architecture that breaks the work into atomic tasks with exclusive file ownership, meaning no two workers ever touch the same file. Workers execute in dependency-ordered waves: all complete Level 1 (types, schemas) before any start Level 2 (business logic), with the orchestrator merging branches and running quality gates between levels. Each worker operates in its own git worktree, reads shared spec files instead of conversation history, and can be restarted without losing progress. The result is 3-4x throughput on parallelizable features with zero merge conflicts.

an ultimate base workflow would spin up relevant connected mcp servers and plugins and agents and subagents and look like the following:

##PLAN (socratic Interactive requirements discovery and project planning)

┌─────────────────────────────────────────────────────────────┐
│  /zerg:plan user-auth                                    │
│  ─────────────────────────────────────────────────────────  │
│  • Enters plan mode (Shift+Tab x2)                          │
│  • Researches codebase via Explore subagents                 │
│  • Asks clarifying questions                                │
│  • Outputs: .gsd/specs/user-auth/requirements.md            │
│  • Waits for "approved"                                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  /zerg:design                                            │
│  ─────────────────────────────────────────────────────────  │
│  • Generates architecture with decision rationale           │
│  • Maps files to create/modify                              │
│  • Identifies risks and mitigations
   • Identifies devcontainer build requirements
   • Establishes impeccible code quality and secure coding rules│
│  • Outputs: .gsd/specs/user-auth/design.md                  │
│  • Waits for "approved"                                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  /zerg:tasks                                             │
│  ─────────────────────────────────────────────────────────  │
│  • Breaks design into atomic tasks (max 3 per plan)
   • Creates task specs and tdd      │
│  • Creates in native Tasks system (persistent)              │
│  • Sets CLAUDE_CODE_TASK_LIST_ID for multi-session          │
│  • Each task has verification command 
   • Each task is tested for functionality, complete integrations, code qualty and security│
│  • Outputs: ~/.claude/tasks/user-auth/ + tasks.md           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  /zerg:gsd                                               │
│  ─────────────────────────────────────────────────────────  │
│  • Picks next task with satisfied dependencies              │
│  • Executes in fresh subagent (prevents context rot)        │
│  • Runs verification command                                │
│  • Commits on pass, retries on fail (3x max)                │
│  • Loops until complete or blocked                          │
└─────────────────────────────────────────────────────────────┘

do a deep dive analysis on the following github repos and websites:

https://github.com/block/goose
https://github.com/obra/packnplay
https://github.com/obra/superpowers
https://github.com/SuperClaude-Org/SuperClaude_Framework
https://github.com/TikiTribe/claude-secure-coding-rules
https://github.com/fr0gger/nova-claude-code-protector
https://github.com/promyze/best-coding-practices
https://github.com/Kristories/awesome-guidelines
https://github.com/github/codeql-coding-standards
https://superclaude.netlify.app/docs

scrape and visit all external links referenced in those repos, too. For instance, the Kristories/awesome-guidelines repo has links to many high-quality coding style conventions and standards

I want zerg have the best and complete combined capabilities of ALL of these and have it be deployable via the claude plugin marketplace. 

I want zerg to automatically pull in the appropriate code quality, styling and security rules based on project requirements and build the docker devcontainer and recommend to the user how many instances to launch based on the project requirements. I want to automate as much of the initial project setup process as possible for the user which is the bane of many people's existence.

The devcontainer will be an isolate container. Mounted volumes limited to specific project directories. No access to ~/.ssh, ~/.aws, or ~/.config. If the agent gets compromised, blast radius stays contained.

Zerg needs to also force the following: 

• Enable all security warnings. Claude Code added explicit warnings for JSON schema exfiltration and settings file modifications. These exist because Anthropic knows the attack surface.
• Add pre-commit hooks for hidden characters. Prompt injections hide in pasted URLs, READMEs, and file names using invisible Unicode. Flag non-ASCII characters in any file the agent might ingest.

Zerg must also enforce never mentioning zerg or claude code in any commit messages.

I want zerg have the BEST capabilities best of ALL of these and have it be deployable via the claude plugin marketplace. The pre-defined workflow I mentioned above likely needs to be redefined.

Since zerg is not developed yet, we cannot use zerg to develop zerg, so we will probably use the traditional GSD methodology and system How would you suggest I go about doing this?

###PHASE 1: REPOSITORY ANALYSIS###

<task>
Analyze the chats in this project, existing ZERG codebase with the filesystem-with-morph mcp server/connector and specified external repositories to extract capabilities, patterns, and implementation approaches for evolving ZERG into a production-ready parallel execution orchestration system for Claude Code.
</task>

<step_1_local_analysis>
Before external research, analyze the existing ZERG implementation at /Users/klambros/PycharmProjects/ZERG.

Extract:
1. Directory structure and module organization
2. Current workflow commands and their implementations
3. Task decomposition approach (if any)
4. State persistence mechanism
5. Worker isolation model (git worktrees, containers, or other)
6. Dependencies and their purposes
7. Configuration schema
8. Test coverage and verification approach
9. Known limitations or TODOs in comments
10. Gap analysis: What the design document promises vs. what's implemented

Output as: Current State Assessment with sections for Architecture, Capabilities, Technical Debt, and Foundation to Preserve.
</step_1_local_analysis>

<step_2_external_research>
After completing local analysis, analyze external repositories in priority order:

Tier 1 - Core Architecture Patterns:
- https://github.com/block/goose
- https://github.com/obra/packnplay
- https://github.com/obra/superpowers
- https://github.com/SuperClaude-Org/SuperClaude_Framework
- https://superclaude.netlify.app/docs

Tier 2 - Code Quality and Security:
- https://github.com/TikiTribe/claude-secure-coding-rules
- https://github.com/fr0gger/nova-claude-code-protector
- https://github.com/promyze/best-coding-practices
- https://github.com/github/codeql-coding-standards

Tier 3 - Style Guidelines Reference:
- https://github.com/Kristories/awesome-guidelines (index only, do not chase all links)
</step_2_external_research>

<extraction_criteria>
For each external repository, extract:

1. Core capability: What problem does it solve? One sentence.
2. Architecture pattern: How is it structured? (monolith, plugin, multi-agent, etc.)
3. Task decomposition approach: How does it break work into units?
4. Concurrency model: How does it handle parallel execution?
5. State persistence: How does it maintain progress across sessions?
6. Integration points: What external tools or APIs does it connect to?
7. Security controls: What isolation, sandboxing, or access controls exist?
8. Reusable components: What modules could be adapted for ZERG?
9. Delta from current ZERG: What does this repo offer that ZERG lacks?
</extraction_criteria>

<investigate_before_answering>
Read local files completely before assessing current state. Fetch and read each external repository's README, core source files, and configuration before extracting capabilities. Base all claims on actual file contents. If a repository is inaccessible or archived, note this and proceed to the next.
</investigate_before_answering>

<parallel_execution>
Execute local analysis first (requires sequential file reading for dependency understanding). Then fetch external repositories simultaneously when possible. Process Tier 1 repositories in parallel, then Tier 2, then Tier 3.
</parallel_execution>

<state_management>
Checkpoints after each major section:

Checkpoint 1: Local analysis complete
- Current architecture summary
- Capabilities inventory
- Technical debt identified
- Foundation worth preserving

Checkpoint 2-4: After each external tier
- Repositories analyzed: [list]
- Key patterns identified: [list]
- Gaps filled by this tier: [list]
- Conflicts with current ZERG approach: [list]

Save all checkpoint outputs to /Users/klambros/PycharmProjects/ZERG/.gsd/specs/phase1/ as markdown files.
</state_management>

<output_format>
Final deliverable: Capability matrix as markdown table with current ZERG as first row, external repositories as subsequent rows, extraction criteria as columns.

Follow with synthesis section identifying:
1. Converging patterns: Approaches in 3+ sources (including current ZERG)
2. Unique innovations: Capabilities in only one source
3. Conflicts: Approaches that contradict each other
4. Gaps: Required capabilities no analyzed source provides
5. Migration path: What current ZERG code to preserve, refactor, or replace
</output_format>

<scope_boundary>
Do not chase external links from Kristories/awesome-guidelines. Index the categories of guidelines it references, but do not fetch each linked resource. That scope belongs to a separate research phase if needed.
</scope_boundary>



###PHASE 2: ARCHITECTURE SYNTHESIS###
<task>
Design ZERG architecture based on Phase 1 capability extraction. Produce a deployable specification for a Claude Code plugin that orchestrates parallel feature development.
</task>

<context>
Reference the capability matrix and synthesis from Phase 1. Build on proven patterns while addressing identified gaps.
</context>

<zerg_requirements>
design command structure and flags for all features of the capability matrics. all commands will be "/zerg" slash commands

Execution model:
- Workers operate in isolated git worktrees
- No two workers modify the same file
- Dependency-ordered waves: Level N completes before Level N+1 starts
- Orchestrator merges branches and runs quality gates between levels
- Workers read shared spec files rather than conversation history
- Failed workers restart without losing progress

Security constraints:
- Devcontainer isolation with mounted volumes limited to project directories only
- Security warnings enabled for JSON schema exfiltration and settings modifications
- Pre-commit hooks flag non-ASCII characters in agent-ingested files
- Commit messages describe changes without referencing tooling names
</zerg_requirements>

<output_structure>
1. System architecture diagram (mermaid)
2. Component specifications for each /zerg command
3. Worker isolation model with devcontainer configuration
4. State persistence schema for multi-session continuity
5. Quality gate definitions between execution levels
6. Security control implementation details
7. Plugin manifest structure for Claude marketplace deployment
8. Instance scaling recommendations based on task graph analysis
</output_structure>

<investigate_before_answering>
Reference the Phase 1 artifact before proposing architecture. Ground all design decisions in patterns that proved effective in analyzed repositories.
</investigate_before_answering>



###PHASE 3: IMPLEMENTATION PLANNING###
<task>
Produce a development plan for building ZERG using conventional single-instance execution, since ZERG cannot build itself. Use the new claude tasks feature and save tasks in the task directory
</task>

<planning_approach>
Apply ZERG's own methodology manually:
1. Break implementation into atomic tasks with exclusive file ownership
2. Order tasks by dependency level
3. Define verification command for each task
4. Estimate parallelization potential for future ZERG self-improvement
</planning_approach>

<output>
Task backlog in markdown with (created in the tasks directory):
- Task ID, description, files owned, dependencies, verification command
- Grouped by implementation level
- Critical path highlighted
- Total estimated sessions to completion
</output>

<state_management>
Output task backlog as persistent artifact. Update after each development session with completion status and blockers.
</state_management>

/sc:implement ZERG-BUILD: Implement ZERG to completion by executing all sessions in .gsd/tasks/claude-code-prompts.md sequentially.

Instructions:
1. Read .gsd/tasks/claude-code-prompts.md for session definitions
2. Read .gsd/tasks/session-tracker.md for current progress
3. Identify the next incomplete session
4. Execute all tasks in that session
5. Run each verification command - stop if any fails
6. Update .gsd/tasks/session-tracker.md marking completed tasks
7. Repeat from step 3 until all 13 sessions complete

Reference docs:
- Architecture: .gsd/specs/phase2/architecture_synthesis.md
- Task specs: .gsd/specs/phase3/implementation_backlog.md
- Task graph: .gsd/tasks/task-graph.json

On verification failure:
- Log the failure in session-tracker.md blockers section
- Attempt to fix the issue
- Re-run verification
- If still failing after 3 attempts, stop and report

On session completion:
- Run all verification commands for that session
- Update session-tracker.md with COMPLETE status
- Proceed to next session

Continue until SESSION 13 final verification passes or a blocking failure occurs. --ultrathink


/sc:document create detailed documentation for this project in README.md and other files that gives users step-by-step instructions for how to install and use with  
  a sample worflow for designing a fictitious e-commerce site that sells coffee. All commands and flags must be documented.   


<task>
Produce a development plan for remediating all critical gaps and importang gaps identified between the current state implementation vs. the architecture spec using superclaude workflows to maximize parallelization. Use the new claude tasks feature and save tasks in the task directory
</task>

<planning_approach>
Apply ZERG's own methodology manually:
1. Break implementation into atomic tasks with exclusive file ownership
2. Order tasks by dependency level
3. Define verification command for each task
4. Estimate parallelization potential for future ZERG self-improvement
</planning_approach>

<output>
Task backlog in markdown with (created in the tasks directory):
- Task ID, description, files owned, dependencies, verification command
- Grouped by implementation level
- Critical path highlighted
- Total estimated sessions to completion
</output>

<state_management>
Output task backlog as persistent artifact. Update after each development session with completion status and blockers.
</state_management>