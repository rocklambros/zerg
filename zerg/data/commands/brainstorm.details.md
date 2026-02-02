<!-- SPLIT: details, parent: brainstorm.md -->
# ZERG Brainstorm: Details & Templates

Reference material for `/zerg:brainstorm`. See `brainstorm.core.md` for primary workflow.

---

## Research Phase Guidelines

### WebSearch Query Templates

Run 3-5 WebSearch queries tailored to the domain. Adapt these templates:

1. **Competitors**: `"{domain} alternatives comparison {current year}"`
2. **Pain points**: `"{domain} common problems user complaints"`
3. **Trends**: `"{domain} trends emerging features {current year}"`
4. **Best practices**: `"{domain} best practices architecture patterns"`
5. **Failures**: `"{domain} common mistakes pitfalls to avoid"`

### Research Summarization

For each query, extract:
- Key competitors and their differentiators (2-3 bullet points each)
- Recurring user pain points (ranked by frequency)
- Market gaps no one is addressing
- Emerging trends and technologies

### Research Output Template (research.md)

```markdown
# Research: {domain}

## Session
- **Session ID**: {session-id}
- **Date**: {timestamp}
- **Queries**: {N} searches conducted

---

## Competitive Landscape

| Competitor | Strengths | Weaknesses | Differentiator |
|------------|-----------|------------|----------------|
| {name} | {strengths} | {weaknesses} | {what sets apart} |

## User Pain Points (Ranked)

1. **{pain point}** -- Frequency: High/Medium/Low
   - Evidence: {source or quote}
2. **{pain point}** -- Frequency: High/Medium/Low
   - Evidence: {source or quote}

## Market Gaps

- {gap}: {why it matters}
- {gap}: {why it matters}

## Emerging Trends

- {trend}: {relevance to our project}
- {trend}: {relevance to our project}

## Key Takeaways

1. {insight}
2. {insight}
3. {insight}
```

---

## Socratic Round Templates

### Round 1: Problem Space (3-4 questions)

Present these via a single AskUserQuestion call. Adapt to the domain.

```
ROUND 1: PROBLEM SPACE
======================

I've completed initial research on {domain}. Before diving into solutions,
let me understand the problem landscape.

1. What specific problems or inefficiencies do you see in the current
   {domain} space? What frustrates users most?

2. Who are the primary users you want to serve, and what are their
   most critical workflows?

3. What existing solutions have you tried or evaluated?
   What falls short about them?

4. Are there opportunities you see that competitors are missing
   or ignoring entirely?

(Answer as much or as little as you like -- I'll follow up on anything unclear.)
```

### Round 2: Solution Ideation (3-4 questions)

```
ROUND 2: SOLUTION IDEATION
===========================

Based on the problems you described and my research findings, let me
explore the solution space.

1. If you could build the ideal solution with no constraints,
   what would it look like? What features would it have?

2. For each feature idea, roughly how would you rank them on a
   value-to-effort scale? (High value + low effort = quick wins)

3. Are there technical constraints or existing systems we need to
   integrate with? Any hard boundaries?

4. What would make this solution genuinely better than alternatives,
   not just different?

(Feel free to think big -- we'll narrow down in the next round.)
```

### Round 3: Prioritization (3-4 questions)

```
ROUND 3: PRIORITIZATION
========================

Now let's get concrete about what to build and in what order.

1. If you could only ship 2-3 features in the first version,
   which would they be and why?

2. How would you sequence the remaining features?
   Are there dependencies between them?

3. What does success look like? What metrics would tell you
   this is working?

4. Is there a timeline or milestone driving urgency for any
   particular feature?

(This will help me generate well-prioritized issues.)
```

### Additional Rounds (4-5, if --rounds > 3)

```
ROUND {N}: DEEP DIVE
=====================

Based on what we've discussed, I want to dig deeper into {specific area}.

1. {Follow-up question based on previous answers}
2. {Clarification on ambiguous requirement}
3. {Edge case or risk exploration}
4. {Integration or dependency question}
```

---

## Socratic Question Trees

Domain-specific question trees for `--socratic` mode. Each tree uses branch IDs to link answers to follow-up questions. When domain keywords match, start at Q1 of that tree.

### Domain: Auth & Authorization
Keywords: auth, login, session, jwt, oauth, password, token, 2fa

**Q1**: Who are your users and how will they authenticate?
  - a) Internal employees — corporate SSO/LDAP integration likely required -> Q2a
  - b) Public consumers — self-registration with email/social login -> Q2b
  - c) API clients (machine-to-machine) — service accounts with key-based auth -> Q2c
  (Other -> LLM follow-up)

**Q2a**: What identity provider will you federate with?
  - a) Active Directory / LDAP — on-prem directory, SAML or OIDC bridge needed -> Q3a
  - b) Okta / Auth0 / Azure AD — managed IdP, faster setup but vendor lock-in -> Q3a
  - c) Custom internal IdP — full control but high maintenance burden -> Q3b
  (Other -> LLM follow-up)

**Q2b**: How should sessions be managed after login?
  - a) Stateless JWT — scalable but harder to revoke mid-session -> Q3a
  - b) Server-side sessions (Redis/DB) — easy revocation but adds infra dependency -> Q3a
  - c) Short-lived tokens + refresh tokens — balanced security/UX trade-off -> Q3b
  (Other -> LLM follow-up)

**Q2c**: What credential type will API clients use?
  - a) API keys — simple but no built-in expiration or scoping -> Q3b
  - b) OAuth2 client credentials — standard, supports scopes and rotation -> Q3a
  - c) mTLS certificates — strongest auth but complex certificate management -> Q3b
  (Other -> LLM follow-up)

**Q3a**: What authorization model fits your access patterns?
  - a) Role-based (RBAC) — simple, suits most apps with fixed permission sets -> Q4
  - b) Attribute-based (ABAC) — flexible, handles complex contextual rules -> Q4
  - c) Permission-based (ACL) — granular per-resource control, can get unwieldy -> Q4
  (Other -> LLM follow-up)

**Q3b**: What are your token/key storage and rotation requirements?
  - a) Auto-rotate on schedule — reduces exposure window, needs automation -> Q4
  - b) Manual rotation on demand — simpler but prone to stale credentials -> Q4
  (Other -> LLM follow-up)

**Q4**: What level of multi-factor authentication is needed?
  - a) None — acceptable for low-risk internal tools -> END
  - b) Optional MFA (TOTP/SMS) — user choice, improves security posture -> Q5
  - c) Mandatory MFA for all users — strongest protection, higher onboarding friction -> Q5
  (Other -> LLM follow-up)

**Q5**: How will you handle account recovery when MFA is lost?
  - a) Backup codes generated at enrollment — self-service, must be stored securely -> END
  - b) Admin-assisted reset — secure but creates support burden -> END
  - c) Secondary verification (email/phone) — convenient but weaker than primary MFA -> END
  (Other -> LLM follow-up)

---

### Domain: API Design
Keywords: api, rest, graphql, endpoint, route, http

**Q1**: What API style best fits your client needs?
  - a) REST — well-understood, strong caching, best for CRUD-heavy services -> Q2a
  - b) GraphQL — flexible queries, reduces over-fetching, adds schema complexity -> Q2b
  - c) gRPC — high performance, strong typing, best for internal service-to-service -> Q2c
  (Other -> LLM follow-up)

**Q2a**: How will you version your REST API?
  - a) URL path versioning (/v1/) — explicit, easy to route, clutters URLs -> Q3a
  - b) Header-based versioning — clean URLs but less discoverable -> Q3a
  - c) No versioning (additive changes only) — simplest but limits breaking changes -> Q3a
  (Other -> LLM follow-up)

**Q2b**: How will you manage your GraphQL schema evolution?
  - a) Deprecation annotations + sunset period — gradual, client-friendly -> Q3a
  - b) Schema stitching / federation — scales across teams but adds orchestration -> Q3b
  - c) Monolithic schema with strict review — simple governance, bottleneck risk -> Q3a
  (Other -> LLM follow-up)

**Q2c**: How will clients consume your gRPC service?
  - a) Direct gRPC clients (internal only) — fastest, requires proto sharing -> Q3b
  - b) gRPC-Web gateway for browser clients — broader reach, adds proxy layer -> Q3a
  - c) REST transcoding via gRPC-Gateway — dual protocol support, extra maintenance -> Q3a
  (Other -> LLM follow-up)

**Q3a**: How should the API handle pagination for list endpoints?
  - a) Cursor-based — stable for real-time data, no page-skip support -> Q4
  - b) Offset/limit — simple, allows page jumping, inconsistent under writes -> Q4
  - c) Keyset pagination — performant at scale, requires sortable key -> Q4
  (Other -> LLM follow-up)

**Q3b**: How will you authenticate API requests?
  - a) Bearer tokens (JWT/opaque) — stateless verification, standard OAuth2 flow -> Q4
  - b) API keys in headers — simple for server-to-server, no user context -> Q4
  - c) Session cookies — works for same-origin browser clients, needs CSRF protection -> Q4
  (Other -> LLM follow-up)

**Q4**: What error response strategy will you use?
  - a) RFC 7807 Problem Details — standardized, machine-parseable, widely supported -> Q5
  - b) Custom error envelope — full control but clients must learn your format -> Q5
  - c) HTTP status codes + plain message — minimal, sufficient for simple APIs -> Q5
  (Other -> LLM follow-up)

**Q5**: What rate limiting strategy protects your API?
  - a) Fixed window per API key — simple to implement, allows burst at window edges -> END
  - b) Sliding window / token bucket — smoother traffic, slightly more complex -> END
  - c) Tiered limits by plan/role — monetization-friendly, requires plan management -> END
  (Other -> LLM follow-up)

---

### Domain: Data Pipeline
Keywords: data, pipeline, etl, streaming, batch, warehouse, analytics

**Q1**: What is your data processing latency requirement?
  - a) Batch (hourly/daily) — simpler ops, higher latency, cost-efficient -> Q2a
  - b) Near real-time (seconds to minutes) — micro-batch or streaming with windowing -> Q2b
  - c) Real-time (sub-second) — event streaming, highest infra complexity -> Q2b
  (Other -> LLM follow-up)

**Q2a**: What are your primary data sources?
  - a) Relational databases (CDC/dumps) — structured, use change data capture for freshness -> Q3a
  - b) Flat files (CSV/JSON/Parquet) — simple ingestion, schema drift risk -> Q3a
  - c) Third-party APIs — rate-limited, needs retry/backoff logic -> Q3b
  (Other -> LLM follow-up)

**Q2b**: What streaming platform will you use?
  - a) Kafka — highest throughput, strong ecosystem, operational overhead -> Q3a
  - b) Cloud-managed (Kinesis/Pub-Sub/EventHub) — less ops, vendor-coupled -> Q3a
  - c) Redis Streams — lightweight, good for moderate volume, limited durability -> Q3b
  (Other -> LLM follow-up)

**Q3a**: Where does transformation logic run?
  - a) SQL-based (dbt/Spark SQL) — accessible to analysts, limited for complex logic -> Q4
  - b) Python/Scala (Spark/Beam) — full flexibility, requires engineering skills -> Q4
  - c) ELT in warehouse (transform after load) — leverages warehouse compute, simpler pipeline -> Q4
  (Other -> LLM follow-up)

**Q3b**: How will you handle schema evolution and data quality?
  - a) Schema registry with compatibility checks — prevents breaking changes upstream -> Q4
  - b) Contract testing between producer/consumer — catches drift early, needs CI integration -> Q4
  - c) Validate on read (schema-on-read) — flexible but pushes errors downstream -> Q4
  (Other -> LLM follow-up)

**Q4**: Where will processed data land?
  - a) Cloud data warehouse (BigQuery/Snowflake/Redshift) — optimized for analytics queries -> Q5
  - b) Data lake (S3/GCS + catalog) — cheapest storage, requires query engine on top -> Q5
  - c) Operational database (Postgres/Mongo) — low-latency reads, not ideal for heavy analytics -> Q5
  (Other -> LLM follow-up)

**Q5**: How will you monitor pipeline health?
  - a) Row count + freshness checks (dbt tests / Great Expectations) — catches data issues -> END
  - b) End-to-end latency + throughput metrics (Datadog/Prometheus) — catches infra issues -> END
  - c) Data observability platform (Monte Carlo/Soda) — unified view, additional cost -> END
  (Other -> LLM follow-up)

---

### Domain: UI/Frontend
Keywords: ui, frontend, react, vue, angular, component, css, design

**Q1**: What framework fits your team and project needs?
  - a) React — largest ecosystem, flexible architecture, steeper learning curve -> Q2a
  - b) Vue — gentle learning curve, opinionated defaults, smaller talent pool -> Q2a
  - c) Angular — batteries-included, strong typing, heavier bundle baseline -> Q2a
  - d) No framework (vanilla/HTMX) — minimal JS, fast initial load, limited interactivity -> Q2b
  (Other -> LLM follow-up)

**Q2a**: What rendering strategy serves your content best?
  - a) Client-side rendering (SPA) — rich interactivity, poor SEO without extra work -> Q3a
  - b) Server-side rendering (Next/Nuxt) — good SEO + fast first paint, server cost -> Q3a
  - c) Static site generation — fastest delivery, only works for content that rarely changes -> Q3b
  - d) Hybrid (per-route choice) — optimal per page, more build complexity -> Q3a
  (Other -> LLM follow-up)

**Q2b**: How will you handle dynamic interactions?
  - a) HTMX / server-rendered partials — progressive enhancement, minimal JS -> Q3b
  - b) Web components — framework-agnostic, encapsulated, limited tooling -> Q3b
  (Other -> LLM follow-up)

**Q3a**: How will you manage client-side state?
  - a) Built-in (useState/Pinia/NgRx) — framework-native, sufficient for most apps -> Q4
  - b) External store (Redux/Zustand/MobX) — predictable, adds boilerplate -> Q4
  - c) Server state library (TanStack Query/SWR) — cache-first, reduces client state -> Q4
  (Other -> LLM follow-up)

**Q3b**: Will you adopt an existing design system or build custom?
  - a) Existing system (MUI/Tailwind/Shadcn) — fast start, customization limits -> Q4
  - b) Custom design system — full brand control, significant upfront investment -> Q4
  (Other -> LLM follow-up)

**Q4**: What are your accessibility requirements?
  - a) WCAG 2.1 AA (standard compliance) — covers most legal/ethical requirements -> Q5
  - b) WCAG 2.1 AAA (strict compliance) — highest standard, constrains design choices -> Q5
  - c) Best-effort (semantic HTML + ARIA basics) — minimum viable, may miss edge cases -> Q5
  (Other -> LLM follow-up)

**Q5**: How will you test the UI?
  - a) Unit + integration (Vitest/Jest + Testing Library) — fast feedback, limited visual coverage -> END
  - b) E2E (Playwright/Cypress) — real browser, slower but catches integration bugs -> END
  - c) Visual regression (Chromatic/Percy) — catches unintended style changes -> END
  (Other -> LLM follow-up)

---

### Domain: Infrastructure
Keywords: infra, deploy, ci, cd, docker, kubernetes, cloud, aws, gcp

**Q1**: Where will your application be hosted?
  - a) Major cloud provider (AWS/GCP/Azure) — full service catalog, learning curve -> Q2a
  - b) PaaS (Vercel/Railway/Fly.io) — minimal ops, limited customization -> Q2b
  - c) Self-hosted / on-prem — full control, full responsibility for everything -> Q2a
  (Other -> LLM follow-up)

**Q2a**: What compute model fits your workload?
  - a) Containers (ECS/GKE/AKS) — portable, consistent environments, orchestration overhead -> Q3a
  - b) Serverless functions (Lambda/Cloud Functions) — auto-scale to zero, cold start latency -> Q3b
  - c) VMs (EC2/Compute Engine) — maximum control, manual scaling and patching -> Q3a
  (Other -> LLM follow-up)

**Q2b**: What is your deployment trigger?
  - a) Git push to main — simple, fast iteration, needs strong branch protection -> Q3b
  - b) Manual promotion through environments — controlled, slower, audit-friendly -> Q3a
  (Other -> LLM follow-up)

**Q3a**: What does your CI/CD pipeline need to include?
  - a) Build + test + deploy (standard) — covers basics, sufficient for most teams -> Q4
  - b) Build + test + security scan + deploy + smoke test — comprehensive, slower pipeline -> Q4
  - c) Build + test + canary deploy + auto-rollback — progressive delivery, complex setup -> Q4
  (Other -> LLM follow-up)

**Q3b**: How will you handle environment configuration?
  - a) Environment variables (12-factor) — simple, works everywhere, no versioning -> Q4
  - b) Secrets manager (Vault/AWS SM/GCP SM) — audited, rotatable, adds dependency -> Q4
  - c) Config files per environment — explicit, versioned, risk of secret leakage in repo -> Q4
  (Other -> LLM follow-up)

**Q4**: What monitoring and observability do you need?
  - a) Metrics + logs (Prometheus/Grafana/ELK) — standard stack, self-hosted or managed -> Q5
  - b) Full observability (metrics + logs + traces) — deeper insight, higher cost/complexity -> Q5
  - c) Managed APM (Datadog/New Relic) — turnkey, expensive at scale -> Q5
  (Other -> LLM follow-up)

**Q5**: What is your scaling and disaster recovery strategy?
  - a) Horizontal auto-scaling + multi-AZ — handles load spikes, resilient to AZ failure -> END
  - b) Multi-region active-passive — disaster recovery, adds data replication complexity -> END
  - c) Multi-region active-active — highest availability, hardest to implement correctly -> END
  (Other -> LLM follow-up)

---

### Domain: General
Keywords: (fallback for unmatched domains)

**Q1**: What type of problem are you solving?
  - a) Building a new product/feature — greenfield, maximum design freedom -> Q2a
  - b) Improving an existing system — must work within current constraints -> Q2b
  - c) Migrating or replacing a system — continuity critical, risk management key -> Q2b
  (Other -> LLM follow-up)

**Q2a**: What is the scope of this project?
  - a) Single service or module — focused, can ship independently -> Q3a
  - b) Multi-service system — needs coordination, API contracts, shared infra -> Q3a
  - c) Full platform / product — large scope, phased delivery recommended -> Q3b
  (Other -> LLM follow-up)

**Q2b**: What are the biggest pain points with the current system?
  - a) Performance / scalability — need measurement before optimization -> Q3a
  - b) Maintainability / tech debt — refactoring scope must be bounded -> Q3a
  - c) Missing features / capability gaps — prioritization framework needed -> Q3b
  (Other -> LLM follow-up)

**Q3a**: Who are the primary users of this system?
  - a) Internal team members — known users, direct feedback loop -> Q4
  - b) External customers (B2C) — large scale, UX-critical, support cost matters -> Q4
  - c) Business clients (B2B) — SLA-driven, integration requirements, enterprise features -> Q4
  (Other -> LLM follow-up)

**Q3b**: How will you prioritize what to build first?
  - a) User impact (highest value first) — customer-centric, needs usage data -> Q4
  - b) Technical risk (hardest problems first) — de-risks early, delays visible progress -> Q4
  - c) Dependencies (unblock others first) — optimizes team throughput -> Q4
  (Other -> LLM follow-up)

**Q4**: What are your primary constraints?
  - a) Timeline (fixed deadline) — scope must flex, cut features not corners -> Q5
  - b) Budget (limited resources) — maximize ROI, prefer managed services -> Q5
  - c) Team size / skills — scope to capabilities, plan for learning curve -> Q5
  (Other -> LLM follow-up)

**Q5**: How will you measure success?
  - a) Quantitative metrics (latency, throughput, conversion) — measurable, needs instrumentation -> END
  - b) User satisfaction (NPS, task completion rate) — meaningful, harder to measure -> END
  - c) Business outcomes (revenue, cost reduction) — ultimate measure, lagging indicator -> END
  (Other -> LLM follow-up)

---

## Saturation Detection

**Definition**: Discovery is saturated when 2 consecutive answers introduce zero new entities, constraints, or requirements compared to what is already captured.

**Signal phrases**: "that's about it", "nothing else", "same as before", confirmations reiterating prior points without new information.

**Rules**:
- Minimum 3 questions before checking for saturation
- Count new entities/constraints/requirements per answer
- If count == 0 for 2 consecutive answers -> stop
- Announce: "Discovery complete -- your answers have converged."

**Entity tracking**: Maintain a running set of {entities, constraints, requirements} extracted from each answer. Compare each answer's extracted set against the cumulative set. New items = set difference.

---

## Trade-off Round Templates

Present architectural alternatives via AskUserQuestion. Each option carries a one-line pro and one-line con so the user can make an informed choice without leaving the conversation.

### Format

```
AskUserQuestion:
  header: "Trade-off {N}"
  question: "{description of architectural decision}"
  multiSelect: false
  options:
    - label: "{Option A}"
      description: "Pro: {benefit}. Con: {drawback}."
    - label: "{Option B}"
      description: "Pro: {benefit}. Con: {drawback}."
    - label: "{Option C}"
      description: "Pro: {benefit}. Con: {drawback}."
```

### When to trigger

- After Socratic discovery surfaces a decision with 2+ viable approaches
- Before validation checkpoints (trade-offs feed into what gets validated)
- Whenever the user says "not sure which" or "what do you recommend"

### Common Trade-offs by Domain

| Domain | Typical Decision | Options |
|--------|-----------------|---------|
| Auth | Session storage | JWT vs server-side sessions vs hybrid |
| API | Protocol | REST vs GraphQL vs gRPC |
| Data | Processing | Batch vs streaming vs hybrid |
| UI | Rendering | SSR vs CSR vs SSG vs ISR |
| Infra | Hosting | Managed vs self-hosted vs serverless |
| State | Management | Local vs global store vs server state |
| Storage | Database | SQL vs document vs graph vs key-value |
| Caching | Strategy | Client-side vs CDN vs server-side vs multi-layer |

### Recording

After the user selects an option, record the outcome in the transcript:
```
Trade-off {N}: {decision} -> Chose {label}. Rejected: {other labels}.
```

---

## Validation Checkpoint Templates

Run 4 checkpoints after discovery and trade-off rounds. Each checkpoint summarizes what was captured for one area and asks the user to confirm, revise, or add.

### Checkpoint 1: Scope

```
AskUserQuestion:
  header: "Validate: Scope"
  question: "{summary of project scope, boundaries, and out-of-scope items}\n\nDoes this match your vision?"
  multiSelect: false
  options:
    - label: "Confirmed"
      description: "This accurately captures my requirements for scope."
    - label: "Revise"
      description: "Some aspects need correction or adjustment."
    - label: "Add"
      description: "Missing important details I want to include."
```

### Checkpoint 2: Entities

```
AskUserQuestion:
  header: "Validate: Entities"
  question: "{list of entities, their attributes, and relationships}\n\nDoes this match your vision?"
  multiSelect: false
  options:
    - label: "Confirmed"
      description: "This accurately captures my requirements for entities."
    - label: "Revise"
      description: "Some aspects need correction or adjustment."
    - label: "Add"
      description: "Missing important details I want to include."
```

### Checkpoint 3: Workflows

```
AskUserQuestion:
  header: "Validate: Workflows"
  question: "{user flows and interaction sequences}\n\nDoes this match your vision?"
  multiSelect: false
  options:
    - label: "Confirmed"
      description: "This accurately captures my requirements for workflows."
    - label: "Revise"
      description: "Some aspects need correction or adjustment."
    - label: "Add"
      description: "Missing important details I want to include."
```

### Checkpoint 4: Non-Functional Requirements

```
AskUserQuestion:
  header: "Validate: NFRs"
  question: "{performance, security, scalability, and reliability requirements}\n\nDoes this match your vision?"
  multiSelect: false
  options:
    - label: "Confirmed"
      description: "This accurately captures my requirements for NFRs."
    - label: "Revise"
      description: "Some aspects need correction or adjustment."
    - label: "Add"
      description: "Missing important details I want to include."
```

### Revision loop

If the user selects "Revise" or "Add", ask a free-form follow-up, incorporate the changes, and re-present the same checkpoint. Continue until "Confirmed".

### Output: validated-design.md

```markdown
# Validated Design: {domain}

## Scope (Confirmed/Revised at checkpoint 1)
{scope description}

## Entities (Confirmed/Revised at checkpoint 2)
{entity list with relationships}

## Workflows (Confirmed/Revised at checkpoint 3)
{user flow descriptions}

## Non-Functional Requirements (Confirmed/Revised at checkpoint 4)
{performance, security, scalability requirements}
```

---

## YAGNI Gate Template

After validation, present all discovered features and let the user select which to build NOW. Unselected features are deferred, not discarded.

### Format

```
AskUserQuestion:
  header: "YAGNI Gate"
  question: "Select the features to build NOW. Unselected features will be deferred to a future iteration."
  multiSelect: true
  options:
    - label: "{Feature 1}"
      description: "{one-line summary of what it does}"
    - label: "{Feature 2}"
      description: "{one-line summary of what it does}"
    - label: "{Feature 3}"
      description: "{one-line summary of what it does}"
```

### Deferred Feature Log (deferred.md)

```markdown
# Deferred Features: {domain}

| Feature | Reason | Revisit When |
|---------|--------|--------------|
| {feature} | Deferred at YAGNI gate | Next iteration |
```

### Rules
- Present features in priority order (core first, nice-to-have last)
- Mark dependencies: if Feature B depends on Feature A, note it in the description
- Minimum 1 feature must be selected (empty selection triggers re-prompt)

---

### Socratic Transcript Template (transcript.md)

```markdown
# Discovery Transcript: {domain}

## Session
- **Session ID**: {session-id}
- **Date**: {timestamp}
- **Rounds**: {N}

---

### Round 1: Problem Space
- **Q1**: {question}
  **A**: {answer}
- **Q2**: {question}
  **A**: {answer}
- **Q3**: {question}
  **A**: {answer}
- **Q4**: {question}
  **A**: {answer}

### Round 2: Solution Ideation
- **Q1**: {question}
  **A**: {answer}
...

### Round 3: Prioritization
- **Q1**: {question}
  **A**: {answer}
...

### Socratic Discovery (--socratic mode)
- **Q{N}** [{domain} tree / LLM follow-up]: {question}
  **A**: {answer} | New entities: {count}

### Trade-off Outcomes
| Decision | Chosen | Alternatives Considered |
|----------|--------|------------------------|
| {decision} | {chosen option} | {other options} |

### Validation Results
| Checkpoint | Status | Notes |
|------------|--------|-------|
| Scope | Confirmed/Revised | {notes} |
| Entities | Confirmed/Revised | {notes} |
| Workflows | Confirmed/Revised | {notes} |
| NFRs | Confirmed/Revised | {notes} |

### YAGNI Gate
- **Kept**: {comma-separated list of features selected for this iteration}
- **Deferred**: {comma-separated list of features moved to deferred.md}
```

---

## Issue Template

For each identified feature, create a GitHub issue using `gh issue create`:

```bash
gh issue create \
  --title "{Feature Name}" \
  --label "brainstorm,{priority}" \
  --body "$(cat <<'ISSUE_EOF'
## Problem

{2-3 sentences describing the problem this feature solves, grounded in
research findings and user responses from the Socratic rounds.}

## Proposed Solution

{Description of the proposed feature and how it addresses the problem.
Include key capabilities and user-facing behavior.}

## Acceptance Criteria

- [ ] {Criterion 1}
- [ ] {Criterion 2}
- [ ] {Criterion 3}
- [ ] {Criterion 4}

## Competitive Context

{How competitors handle this. What gap this fills. Reference research.md findings.}

## Priority

**{P0/P1/P2}** -- {One-sentence justification}

- P0: Must-have for MVP, blocks other work
- P1: Important, should be in first release
- P2: Nice-to-have, can defer to later iteration

## Effort Estimate

**{Small/Medium/Large}** -- {Brief justification}

---

_Generated by `/zerg:brainstorm` session {session-id}_
ISSUE_EOF
)"
```

### Priority Assignment Guidelines

| Priority | Criteria | Label |
|----------|----------|-------|
| P0 | User identified as must-have, blocks other features, addresses critical pain point | `P0-critical` |
| P1 | High value, mentioned in MVP scope, strong competitive advantage | `P1-important` |
| P2 | Nice-to-have, future iteration, lower user urgency | `P2-nice-to-have` |

---

## Output Schemas

### brainstorm.md (Session Summary)

```markdown
# Brainstorm Summary: {domain}

## Session
- **Session ID**: {session-id}
- **Domain**: {domain}
- **Date**: {timestamp}
- **Rounds**: {N}
- **Issues Created**: {N}

---

## Key Insights

1. {Top insight from research and discovery}
2. {Second insight}
3. {Third insight}

## Features Identified (Ranked)

| Rank | Feature | Priority | Effort | Issue |
|------|---------|----------|--------|-------|
| 1 | {feature} | P0 | {S/M/L} | #{number} |
| 2 | {feature} | P1 | {S/M/L} | #{number} |
| 3 | {feature} | P2 | {S/M/L} | #{number} |

## Recommended Next Steps

1. `/zerg:plan {top-feature}` -- Start planning the highest-priority feature
2. Review and refine issues on GitHub
3. Share brainstorm summary with stakeholders

## Session Artifacts

- `research.md` -- Competitive analysis and market research
- `transcript.md` -- Full Socratic discovery transcript
- `issues.json` -- Machine-readable issue manifest
- `brainstorm.md` -- This summary
```

### issues.json (Machine-Readable Manifest)

```json
{
  "session_id": "{session-id}",
  "domain": "{domain}",
  "created": "{ISO-8601 timestamp}",
  "issues": [
    {
      "number": 42,
      "url": "https://github.com/{owner}/{repo}/issues/42",
      "title": "{Feature Name}",
      "priority": "P0",
      "effort": "Medium",
      "feature_name": "{feature-slug}",
      "labels": ["brainstorm", "P0-critical"]
    }
  ],
  "next_recommended": "{top-feature-slug}"
}
```

If `--dry-run` was used, `number` and `url` will be `null`.

---

## Handoff Prompt Template

```
=====================================================================
                    BRAINSTORM SESSION COMPLETE
=====================================================================

Domain: {domain}
Session: {session-id}

Issues Created: {N}
  P0 (Critical):    {count}
  P1 (Important):   {count}
  P2 (Nice-to-have): {count}

Top Recommendations:
  1. {feature} (P0, {effort}) -- #{issue-number}
  2. {feature} (P1, {effort}) -- #{issue-number}
  3. {feature} (P2, {effort}) -- #{issue-number}

Session Artifacts:
  .gsd/specs/{session-id}/research.md
  .gsd/specs/{session-id}/transcript.md
  .gsd/specs/{session-id}/brainstorm.md
  .gsd/specs/{session-id}/issues.json

---------------------------------------------------------------------

Suggested next step:
  /zerg:plan {top-feature}

=====================================================================
```

---

## Example Session

### Input
```
/zerg:brainstorm notification-system
```

### Phase 1: Research
WebSearch queries:
- "notification system alternatives comparison 2026"
- "push notification pain points user complaints"
- "notification system architecture best practices"

Findings saved to `.gsd/specs/brainstorm-20260201-143022/research.md`.

### Phase 2: Socratic Discovery

**Round 1 (Problem Space)**:
- Q: What problems do you see in the notification space?
- A: Users get too many irrelevant notifications and miss the important ones.

**Round 2 (Solution Ideation)**:
- Q: What would the ideal notification system look like?
- A: Smart filtering with user preferences, digest mode, and priority channels.

**Round 3 (Prioritization)**:
- Q: Which 2-3 features are must-haves?
- A: Priority channels, user preference settings, and digest mode.

### Phase 3: Issue Generation
Created 5 issues:
- #101: Priority Channels (P0)
- #102: User Notification Preferences (P0)
- #103: Digest Mode (P1)
- #104: Smart Filtering with ML (P2)
- #105: Notification Analytics Dashboard (P2)

### Phase 4: Handoff
Presented summary, suggested `/zerg:plan priority-channels` as next step.
