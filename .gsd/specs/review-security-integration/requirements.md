# Requirements: Review-Security Integration

**Feature**: Consolidate security into a unified engine and integrate as Stage 3 of `/z:review`
**Status**: APPROVED
**Created**: 2026-02-15
**Author**: ZERG Plan (Socratic mode, 3 rounds)

---

## 1. Problem Statement

Security logic is scattered across three locations with overlap and gaps:
- `zerg/security.py` — 27 secret patterns, sensitive files, large files, symlink escapes
- `zerg/security.py:HOOK_PATTERNS` — shell injection, code injection, unsafe deserialization (defined but **never called**)
- `zerg/commands/review.py:CodeAnalyzer` — duplicate hardcoded_secret pattern (weaker version)

Meanwhile, `/z:security` slash command *describes* OWASP presets, CVE scanning, injection/XSS analysis, and compliance frameworks — but these exist only as Claude-directed behaviors, not as Python functions callable by the CLI.

Result: `zerg review` CLI provides shallow security checks. The slash command promises deep security but the programmatic path can't deliver it.

## 2. Goals

1. **Consolidate** all security logic into a single `zerg/security/` package — zero duplication
2. **Deepen** security scanning with 10 new capability areas
3. **Integrate** security as always-on Stage 3 in `/z:review` (both slash command and CLI)
4. **Reuse** — `/z:security` and `/z:review` call the same engine. No parallel implementations
5. **Document** the integration across all touchpoints: command files, docs, website, wiki

## 3. Non-Goals

- Replacing external security tools (Snyk, Semgrep, Trivy) — ZERG supplements, doesn't replace
- Real-time monitoring or runtime security — this is static analysis only
- Modifying the `/z:rush` or `/z:worker` pipelines (future scope)

## 4. Functional Requirements

### FR-1: Consolidated Security Package

Promote `zerg/security.py` and `zerg/security_rules.py` into a `zerg/security/` package:

```
zerg/security/
  __init__.py      # Public API: run_security_scan(), SecurityResult
  scanner.py       # Main scanning engine (consolidates all patterns)
  patterns.py      # All detection patterns (secrets, injection, crypto, etc.)
  rules.py         # Stack detection, rule fetching, filtering (from security_rules.py)
  cve.py           # Dependency CVE scanning with API + heuristic fallback
  hooks.py         # Git hook installation/management (from security.py)
```

- **All existing callers** must be updated to import from `zerg.security` (package)
- **HOOK_PATTERNS** security patterns must be incorporated into the scanner, not just defined
- **CodeAnalyzer.hardcoded_secret** pattern in `review.py` must be removed — defer to security engine
- `run_security_scan()` returns a `SecurityResult` dataclass with structured findings

### FR-2: Deep Security Scanning Engine

The consolidated scanner must implement these capability areas:

| # | Capability | Description | Implementation |
|---|-----------|-------------|----------------|
| 1 | Secret detection | API keys, tokens, credentials, private keys | Existing 27 patterns + HOOK_PATTERNS |
| 2 | Injection detection | Shell injection, code injection (eval/exec), SQL injection patterns | From HOOK_PATTERNS + new patterns |
| 3 | Deserialization risks | Unsafe deserialization, unsafe YAML, insecure data loading | From HOOK_PATTERNS + new patterns |
| 4 | Cryptographic misuse | MD5/SHA1 for passwords, hardcoded IVs/salts, weak algorithms | New patterns |
| 5 | Error handling audit | Bare except, fail-open patterns, stack trace leakage in responses | New patterns |
| 6 | Input validation gaps | Unvalidated user input flowing to dangerous sinks | New patterns |
| 7 | Dependency CVE scanning | Check deps against known vulnerabilities | External API (osv.dev) + heuristic fallback |
| 8 | Lockfile integrity | Verify lockfile exists, hashes present, no unpinned deps | Heuristic checks |
| 9 | License compliance | Detect GPL/AGPL deps that could affect commercial use | Pattern-based detection |
| 10 | Git history scanning | Secrets in past commits (not just current files) | `git log` analysis |
| 11 | Sensitive file detection | .env, credentials.json, private keys in repo | Existing (from security.py) |
| 12 | File permission checks | World-writable files, overly permissive configs | New checks |
| 13 | Environment variable leakage | Logging/printing env vars containing secrets | New patterns |
| 14 | Dockerfile security | Running as root, no USER directive, privileged mode | Leverages existing `.claude/rules/security/containers/` |
| 15 | Symlink escape detection | Path traversal via symlinks | Existing (from security.py) |

### FR-3: SecurityResult Dataclass

```python
@dataclass
class SecurityFinding:
    category: str          # e.g., "secret", "injection", "crypto"
    severity: str          # "critical", "high", "medium", "low", "info"
    file: str
    line: int
    message: str
    cwe: str | None        # e.g., "CWE-798"
    remediation: str       # How to fix
    pattern_name: str      # Which pattern matched

@dataclass
class SecurityResult:
    findings: list[SecurityFinding]
    categories_scanned: list[str]
    files_scanned: int
    scan_duration_seconds: float
    passed: bool           # True if no critical/high findings
    summary: dict[str, int]  # severity -> count
```

### FR-4: Review Integration — Stage 3

**Slash command** (`review.md`):
- Review becomes 3-stage: Spec -> Quality -> Security
- Stage 3 invokes the same logic as `/z:security`
- Security findings appear in the review report
- Always-on by default

**CLI** (`review.py`):
- `ReviewCommand.run()` calls `zerg.security.run_security_scan()`
- `ReviewResult` gains `security_passed: bool` and `security_result: SecurityResult`
- `overall_passed` requires all 3 stages to pass
- Rich table output adds row: `Stage 3 (Security): check/cross`
- Security findings displayed by severity below the table

### FR-5: --no-security Flag

- Available on both slash command and CLI
- Default: security ON
- When used: prints warning `"WARNING: Security scan skipped. Use with caution."`
- Review output shows `Stage 3 (Security): SKIPPED` in table

### FR-6: CVE Scanning with Fallback

1. **Try external API first**: Query osv.dev API with dependency list
2. **Fallback to heuristics**: If offline or API fails, use pattern-based checks:
   - Unpinned versions (`>=`, `*`, no version specifier)
   - Missing lockfiles (requirements.txt without .lock, package.json without lockfile)
   - Known-bad version ranges from hardcoded database
3. **Supported ecosystems**: Python (pip), Node.js (npm), Rust (cargo), Go (go.mod)

### FR-7: Shared Engine — No Duplication

- `/z:security` slash command and `/z:review` Stage 3 use the same `run_security_scan()`
- `security_rules_cmd.py` CLI uses the same package for rule management
- `review.py:CodeAnalyzer` removes its `hardcoded_secret` pattern
- Single source of truth: `zerg/security/patterns.py`

## 5. Non-Functional Requirements

### NFR-1: Performance
- Full security scan of 50 files completes in < 5 seconds (excluding CVE API calls)
- CVE API calls have 5-second timeout with graceful fallback

### NFR-2: Extensibility
- New patterns can be added to `patterns.py` without modifying scanner logic
- Pattern registry pattern: each category registers its patterns declaratively

### NFR-3: Context Engineering Compatibility
- Package structure enables task-scoped context (workers load only needed submodules)
- Follows ZERG command splitting philosophy (if review.md grows > 300 lines, split to core/details)

### NFR-4: Test Coverage
- Unit tests for each capability area in `tests/unit/test_security_engine.py`
- Integration tests for review + security pipeline in `tests/integration/`
- Existing `test_review_cmd.py` updated to cover Stage 3
- Existing `test_security.py` migrated to new package structure

## 6. Acceptance Criteria

- [ ] `zerg review` CLI output shows 3-stage table (Spec, Quality, Security)
- [ ] `zerg review --no-security` skips Stage 3 with warning
- [ ] `/z:review` slash command describes 3-stage process with security
- [ ] `/z:security` and `/z:review` both call `zerg.security.run_security_scan()`
- [ ] All 15 capability areas have at least one detection pattern
- [ ] CVE scanning attempts API, falls back to heuristics
- [ ] No duplicate security patterns exist across codebase
- [ ] `CodeAnalyzer` in review.py no longer checks for secrets
- [ ] All existing tests pass after migration
- [ ] New tests cover consolidated security engine

## 7. Files to Create

| File | Purpose |
|------|---------|
| `zerg/security/__init__.py` | Public API surface |
| `zerg/security/scanner.py` | Main scanning engine |
| `zerg/security/patterns.py` | All detection patterns |
| `zerg/security/rules.py` | Migrated from `zerg/security_rules.py` |
| `zerg/security/cve.py` | CVE scanning with fallback |
| `zerg/security/hooks.py` | Git hook management (migrated) |
| `tests/unit/test_security_engine.py` | New consolidated tests |
| `tests/integration/test_review_security.py` | Integration tests |
| `docs/wiki/Security-Philosophy.md` | New wiki page |

## 8. Files to Modify

| File | Change |
|------|--------|
| `zerg/commands/review.py` | Add Stage 3, import security engine, extend ReviewResult, remove hardcoded_secret from CodeAnalyzer |
| `zerg/commands/security_rules_cmd.py` | Update imports to `zerg.security.rules` |
| `zerg/commands/__init__.py` | Update imports if needed |
| `zerg/cli.py` | No change expected (review and security-rules already registered) |
| `zerg/data/commands/review.md` | Add Stage 3 security, --no-security flag, 3-stage output |
| `zerg/data/commands/security.md` | Reference shared engine, note review integration |
| `docs/commands-quick.md` | Update review entry (3-stage), add --no-security flag |
| `docs/commands-deep.md` | Update review section (3-stage diagram), update security section |
| `docs/index.html` | Update review description, add security philosophy narrative |
| `tests/unit/test_review_cmd.py` | Add Stage 3 tests, update ReviewResult assertions |
| `tests/unit/test_security.py` | Migrate to new package imports |

## 9. Files to Delete

| File | Reason |
|------|--------|
| `zerg/security.py` | Migrated to `zerg/security/` package |
| `zerg/security_rules.py` | Migrated to `zerg/security/rules.py` |

## 10. Migration Plan

1. Create `zerg/security/` package with all modules
2. Migrate `security.py` functions to `scanner.py`, `patterns.py`, `hooks.py`
3. Migrate `security_rules.py` to `rules.py`
4. Update all callers (`review.py`, `security_rules_cmd.py`, any others)
5. Add new capabilities to `scanner.py` + `patterns.py`
6. Create `cve.py` with API + fallback
7. Integrate into `review.py` as Stage 3
8. Update slash commands (`review.md`, `security.md`)
9. Update docs and website
10. Delete old files
11. Run full test suite

## 11. Documentation Impact Analysis

| Document | Section | Change |
|----------|---------|--------|
| `zerg/data/commands/review.md` | Modes/Output/Help | Add Stage 3, --no-security flag |
| `zerg/data/commands/security.md` | Capabilities | Reference shared engine |
| `docs/commands-quick.md` | /zerg:review row | Add --no-security flag |
| `docs/commands-deep.md` | /zerg:review section | New 3-stage diagram, security stage details |
| `docs/commands-deep.md` | /zerg:security section | Note shared engine with review |
| `docs/index.html` | Command table + hero/features | Update review desc, add security narrative |
| `docs/wiki/Security-Philosophy.md` | New page | Security-as-core-value philosophy |
| `CHANGELOG.md` | [Unreleased] | Feature entry |

## 12. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Import breakage from package migration | Medium | High | Grep all imports before migration, update atomically |
| CVE API rate limiting | Low | Low | Graceful fallback to heuristics |
| False positives from new patterns | Medium | Medium | Start with high-confidence patterns, tune iteratively |
| Performance regression from deep scan | Low | Medium | Benchmark 50-file scan, set 5s budget |
| Scope creep from 15 capabilities | Medium | High | Implement in priority order, each independently testable |

## 13. Open Questions (RESOLVED)

1. **osv.dev vs pip-audit**: osv.dev API first, then shell out to `pip-audit`/`npm audit` as secondary source. Both, layered.
2. **Git history depth**: Configurable. Default: last 100 commits. Document the default clearly in help text and docs.
3. **License database**: Library integration (not hardcoded allowlist). Use a proper license detection library.
4. **Severity thresholds**: `--no-security` is never blocked, but critical findings trigger prominent red warnings prompting the user to reconsider. The scan still skips — the user has final say.

---

*Generated by /zerg:plan --socratic (3 rounds)*
