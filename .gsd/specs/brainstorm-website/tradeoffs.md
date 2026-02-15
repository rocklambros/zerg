# Trade-off Decisions: ZERG Website

## 1. Tailwind Loading
**Decision**: CDN (Play CDN)
**Rationale**: Zero build step, GitHub Pages deploys static files as-is. No node_modules, no Tailwind CLI. Cached after first load. Most supportable.

## 2. Deployment Workflow
**Decision**: Repurpose existing docs.yml
**Rationale**: Workflow already has Pages permissions, environments, and concurrency config. Just change the build step from mkdocs to a simple file copy. Less churn.
