# Feature Requirements: production-dogfooding

## Metadata
- **Feature**: production-dogfooding
- **Status**: APPROVED
- **Created**: 2026-01-29T10:00:00
- **Author**: Socratic Discovery (3 rounds)

---

## 1. Problem Statement

### 1.1 Background
ZERG has never been tested end-to-end against a real feature build. All existing E2E tests are heavily mocked.

### 1.2 Problem
No confidence that the full plan -> design -> rush -> merge pipeline works in production conditions.

### 1.3 Impact
Bugs in orchestration, state IPC, merge coordination, and worker lifecycle remain undiscovered.

---

## 2. Deliverables

### Deliverable 1: E2E Test Harness
- MockWorker that patches invoke_claude_code with pathlib file ops
- E2EHarness that sets up real git repos and runs Orchestrator
- Mock mode (CI-safe, no API key) and real mode (Claude API)
- 5 workers, multi-level task graphs

### Deliverable 2: Plugin System (built by ZERG dogfooding itself)
- QualityGatePlugin ABC — custom lint/test/check after merge
- LifecycleHookPlugin ABC — react to task/level/merge/rush events
- LauncherPlugin ABC — custom worker launchers (K8s, SSH, cloud VMs)
- PluginRegistry — loads from YAML config + Python entry_points
- Security: strictly additive, read-only state views, timeout enforcement

---

## 3. Scope

### In Scope
- E2E test harness with mock and real modes
- Plugin ABCs, registry, config models
- Integration into orchestrator, worker_protocol, gates, launcher
- Unit tests, integration tests, E2E pipeline tests
- Plugin documentation

### Out of Scope
- Actual K8s/SSH launcher implementations (just the plugin interface)
- Plugin marketplace or distribution
- Hot-reload of plugins during rush

---

## 4. Acceptance Criteria
- All 20 tasks pass verification
- All 4 levels merge cleanly
- Full test suite regression passes (4874+ tests)
- Lint clean (ruff)
- All imports verify
