# Technical Design: Pre-release Documentation

## Metadata
- **Feature**: pre-release-docs
- **Status**: DRAFT
- **Created**: 2026-02-01

---

## 1. Overview

### 1.1 Summary
Create 4 governance/architecture documents required for open-source release: LICENSE (MIT), CONTRIBUTING.md, SECURITY.md, and docs/design-principles.md. Add cross-references from README.md.

### 1.2 Goals
- Satisfy legal requirements for open-source release (LICENSE)
- Enable external contributions with clear guidelines (CONTRIBUTING.md)
- Establish responsible vulnerability disclosure (SECURITY.md)
- Codify context management as first-class design constraint (design-principles.md)

### 1.3 Non-Goals
- No code changes
- No CI/CD changes (covered by separate issues #19, #23)
- No pyproject.toml changes (already declares MIT)

---

## 2. Key Decisions

### Decision: design-principles.md location

**Context**: Should design principles go in root (PRINCIPLES.md) or docs/?

**Decision**: `docs/design-principles.md`

**Rationale**: Root is for governance docs (LICENSE, CONTRIBUTING, SECURITY). Architectural guidance belongs in docs/ alongside context-engineering.md and commands.md.

---

## 3. File Ownership

| File | Task | Operation |
|------|------|-----------|
| LICENSE | DOC-001 | create |
| CONTRIBUTING.md | DOC-002 | create |
| SECURITY.md | DOC-003 | create |
| docs/design-principles.md | DOC-004 | create |
| README.md | DOC-005 | modify |

---

## 4. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Stale tooling info in CONTRIBUTING | Low | Low | Read pyproject.toml for exact config |
| Missing README link location | Low | Low | Grep for existing section structure |

---

## 5. Parallel Execution Notes

- Level 1: 4 tasks, fully parallel, zero file overlap
- Level 2: 1 task (README cross-refs), depends on all L1
- Optimal: 4 workers
