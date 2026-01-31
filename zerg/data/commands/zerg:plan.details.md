<!-- SPLIT: details, parent: zerg:plan.md -->
# ZERG Plan: Details & Templates

Reference material for `/zerg:plan`. See `zerg:plan.core.md` for primary workflow.

---

## Socratic Mode (--socratic)

If `--socratic` flag is used, follow this structured 3-round discovery process:

### Round 1: Problem Space (5 questions max)

Focus on understanding the problem before jumping to solutions.

```
ROUND 1: PROBLEM SPACE
══════════════════════

1. What specific problem does this feature solve?
   (Describe the pain point or gap)

2. Who are the primary users affected by this problem?
   (Be specific about user roles/personas)

3. What happens today without this feature?
   (Current workarounds, manual processes, or blocked workflows)

4. Why is solving this problem important now?
   (Business impact, urgency, opportunity cost)

5. How will we know when the problem is solved?
   (Observable changes, success indicators)
```

Wait for user responses before proceeding.

### Round 2: Solution Space (5 questions max)

Explore solution boundaries and constraints.

```
ROUND 2: SOLUTION SPACE
═══════════════════════

1. What does the ideal solution look like?
   (Describe the vision without constraints)

2. What constraints must we work within?
   (Technical, time, budget, compatibility)

3. What are the non-negotiable requirements?
   (Must-haves vs nice-to-haves)

4. What similar solutions exist? What can we learn from them?
   (Prior art, competitors, analogies)

5. What should this solution explicitly NOT do?
   (Scope boundaries, anti-patterns)
```

Wait for user responses before proceeding.

### Round 3: Implementation Space (5 questions max)

Get concrete about execution.

```
ROUND 3: IMPLEMENTATION SPACE
═════════════════════════════

1. What is the minimum viable version of this feature?
   (First releasable increment)

2. What can be deferred to future iterations?
   (Nice-to-haves, enhancements)

3. What are the biggest technical risks?
   (Unknowns, dependencies, complexity)

4. How should we verify this works correctly?
   (Test scenarios, acceptance criteria)

5. What documentation or training is needed?
   (User guides, API docs, runbooks)
```

After completing all rounds, synthesize into requirements.md.

### Socratic Mode Output

After completing the rounds, generate a transcript section:

```markdown
## Discovery Transcript

### Round 1: Problem Space
- Q1: {question}
  A: {answer}
- Q2: {question}
  A: {answer}
...

### Round 2: Solution Space
- Q1: {question}
  A: {answer}
...

### Round 3: Implementation Space
- Q1: {question}
  A: {answer}
...
```

---

## Phase 2: Question Categories (Full Reference)

### Problem Space
- What problem does this feature solve?
- Who are the users of this feature?
- What happens if this feature doesn't exist?

### Functional Requirements
- What are the core capabilities?
- What inputs does the feature accept?
- What outputs does the feature produce?
- What are the edge cases?

### Non-Functional Requirements
- Performance requirements (latency, throughput)?
- Security requirements (authentication, authorization)?
- Scalability requirements?
- Reliability requirements?

### Scope Boundaries
- What is explicitly OUT of scope?
- What are acceptable compromises?
- What can be deferred to future iterations?

### Dependencies
- Does this depend on other features?
- Are there external API dependencies?
- Are there data dependencies?

### Acceptance Criteria
- How will we know this feature is complete?
- What are the test scenarios?
- What does success look like?

---

## Phase 3: requirements.md Template

```markdown
# Feature Requirements: {feature}

## Metadata
- **Feature**: {feature}
- **Status**: DRAFT | REVIEW | APPROVED
- **Created**: {timestamp}
- **Author**: Factory Plan Mode

---

## 1. Problem Statement

### 1.1 Background
{Context and background information}

### 1.2 Problem
{Clear statement of the problem being solved}

### 1.3 Impact
{What happens without this feature}

---

## 2. Users

### 2.1 Primary Users
{Who will use this feature most}

### 2.2 Secondary Users
{Other stakeholders}

### 2.3 User Stories
- As a {user}, I want to {action} so that {benefit}
- As a {user}, I want to {action} so that {benefit}

---

## 3. Functional Requirements

### 3.1 Core Capabilities

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| FR-001 | {requirement} | Must | {notes} |
| FR-002 | {requirement} | Should | {notes} |
| FR-003 | {requirement} | Could | {notes} |

### 3.2 Inputs
{What the feature accepts}

### 3.3 Outputs
{What the feature produces}

### 3.4 Business Rules
{Logic and constraints}

---

## 4. Non-Functional Requirements

### 4.1 Performance
- Response time: {target}
- Throughput: {target}
- Resource usage: {constraints}

### 4.2 Security
- Authentication: {requirements}
- Authorization: {requirements}
- Data protection: {requirements}

### 4.3 Reliability
- Availability: {target}
- Error handling: {strategy}
- Recovery: {strategy}

### 4.4 Scalability
- Expected load: {estimate}
- Growth expectations: {estimate}

---

## 5. Scope

### 5.1 In Scope
- {item}
- {item}

### 5.2 Out of Scope
- {item} (reason: {why})
- {item} (deferred to: {when})

### 5.3 Assumptions
- {assumption}
- {assumption}

### 5.4 Constraints
- {constraint}
- {constraint}

---

## 6. Dependencies

### 6.1 Internal Dependencies
| Dependency | Type | Status |
|------------|------|--------|
| {feature/system} | Required | {status} |

### 6.2 External Dependencies
| Dependency | Type | Owner |
|------------|------|-------|
| {API/service} | {type} | {owner} |

---

## 7. Acceptance Criteria

### 7.1 Definition of Done
- [ ] All functional requirements implemented
- [ ] All tests passing
- [ ] Code reviewed
- [ ] Documentation updated

### 7.2 Test Scenarios

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| TC-001 | {name} | {precondition} | {action} | {expected} |
| TC-002 | {name} | {precondition} | {action} | {expected} |

### 7.3 Success Metrics
- {metric}: {target}
- {metric}: {target}

---

## 8. Open Questions

| ID | Question | Owner | Due | Status |
|----|----------|-------|-----|--------|
| Q-001 | {question} | {who} | {when} | Open |

---

## 9. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Product | | | PENDING |
| Engineering | | | PENDING |
```

---

## Phase 4: Infrastructure Template

```markdown
## Infrastructure Additions for {feature}

### New Services Required
| Service | Version | Purpose |
|---------|---------|---------|
| {service} | {version} | {why} |

### New MCP Servers
| Server | Purpose |
|--------|---------|
| {server} | {why} |

### New Environment Variables
| Variable | Description |
|----------|-------------|
| {VAR} | {description} |

### Resource Impact
- Additional CPU: {estimate}
- Additional Memory: {estimate}
- Additional Storage: {estimate}
```

Update `.gsd/INFRASTRUCTURE.md` if needed.

---

## Phase 5: Approval Prompt Template

```
═══════════════════════════════════════════════════════════════
                 REQUIREMENTS READY FOR REVIEW
═══════════════════════════════════════════════════════════════

Feature: {feature}

Summary:
  • {N} functional requirements ({must}/{should}/{could})
  • {N} non-functional requirements
  • {N} test scenarios
  • {N} open questions

Files Created:
  • .gsd/specs/{feature}/requirements.md

───────────────────────────────────────────────────────────────

Please review the requirements document.

Reply with:
  • "APPROVED" - to proceed to design phase
  • "REJECTED" - describe what needs to change
  • Specific questions or concerns

═══════════════════════════════════════════════════════════════
```

---

## Example Output

```markdown
## Metadata
- **Feature**: user-authentication
- **Status**: APPROVED
- **Created**: 2026-01-25T10:30:00
- **Approved**: 2026-01-25T11:45:00
- **Author**: Factory Plan Mode
```
