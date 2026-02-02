# Socratic Question Trees

Six domain-specific question trees for `--socratic` mode in `/zerg:brainstorm`.
Each tree uses branch IDs (Q1, Q2a, Q2b, etc.) to link options to follow-up questions.

---

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
