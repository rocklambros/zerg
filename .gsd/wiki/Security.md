# Security

ZERG integrates automated security rules that are fetched based on your project's detected tech stack. This page covers security rules integration, OWASP Top 10 2025 coverage, language-specific rules, and vulnerability reporting.

---

## Overview

ZERG takes a **shift-left security** approach, embedding security guidance directly into the development workflow:

1. **Auto-detection** — ZERG scans your project to detect languages, frameworks, databases, and infrastructure
2. **Intelligent fetching** — Only rules relevant to your stack are downloaded
3. **Claude Code integration** — Rules are stored where Claude Code automatically loads them
4. **Continuous enforcement** — Pre-commit hooks validate security on every commit

Security rules are sourced from [TikiTribe/claude-secure-coding-rules](https://github.com/TikiTribe/claude-secure-coding-rules), a curated repository of secure coding guidelines for AI-assisted development.

---

## Security Rules Integration

### How It Works

ZERG fetches security rules from the TikiTribe repository and stores them in `.claude/rules/security/`. Claude Code automatically loads files from `.claude/` directories, making security guidance available in every session.

```
.claude/
└── rules/
    └── security/
        ├── _core/
        │   └── owasp-2025.md        # Core OWASP Top 10 rules
        ├── languages/
        │   ├── python/
        │   │   └── CLAUDE.md        # Python-specific rules
        │   └── javascript/
        │       └── CLAUDE.md        # JavaScript-specific rules
        └── containers/
            └── docker/
                └── CLAUDE.md        # Docker security rules
```

### CLAUDE.md Integration

An informational summary is added to your project's `CLAUDE.md`:

```markdown
<!-- SECURITY_RULES_START -->
# Security Rules

Auto-generated from [TikiTribe/claude-secure-coding-rules](https://github.com/TikiTribe/claude-secure-coding-rules)

## Detected Stack

- **Languages**: python, javascript
- **Infrastructure**: docker

## Fetched Rules

- `_core/owasp-2025.md`
- `languages/python/CLAUDE.md`
- `languages/javascript/CLAUDE.md`
- `containers/docker/CLAUDE.md`

<!-- SECURITY_RULES_END -->
```

---

## OWASP Top 10 2025

ZERG includes comprehensive coverage of the **OWASP Top 10:2025** (Release Candidate, November 2025), the latest standard for web application security risks based on 589 CWEs across 248 categories.

### Categories

| Category | Risk Level | Key Control |
|----------|------------|-------------|
| **A01: Broken Access Control** | Critical | Server-side authorization |
| **A02: Security Misconfiguration** | High | Secure defaults |
| **A03: Supply Chain Failures** | Critical | Integrity verification |
| **A04: Cryptographic Failures** | High | Strong algorithms |
| **A05: Injection** | High | Parameterized queries |
| **A06: Insecure Design** | High | Threat modeling |
| **A07: Authentication Failures** | High | Secure sessions |
| **A08: Integrity Failures** | High | Signature verification |
| **A09: Logging Failures** | Medium | Comprehensive logging |
| **A10: Error Handling** | Medium | Fail closed |

### Rule Levels

Each security rule has an enforcement level:

| Level | Meaning |
|-------|---------|
| `strict` | Must be followed. Violations are security vulnerabilities. |
| `warning` | Should be followed. Violations may indicate security weaknesses. |
| `advisory` | Recommended practice. Improves security posture. |

### Example: Injection Prevention (A05)

```python
# DO: Parameterized queries
cursor.execute(
    "SELECT * FROM users WHERE username = %s",
    (username,)
)

# DON'T: String interpolation (SQL injection)
cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
```

---

## Language-Specific Rules

### Python Security Rules

Located in `.claude/rules/security/languages/python/CLAUDE.md`

| Rule | Level | CWE |
|------|-------|-----|
| Avoid unsafe deserialization | strict | CWE-502 |
| Safe subprocess | strict | CWE-78 |
| Path traversal prevention | strict | CWE-22 |
| Secure temp files | warning | CWE-377 |
| Cryptographic randomness | strict | CWE-330 |
| Password hashing | strict | CWE-916 |
| Parameterized queries | strict | CWE-89 |
| URL scheme validation | strict | CWE-918 |
| Secure cookies | strict | CWE-614 |
| No stack traces in responses | warning | CWE-209 |

**Key Points:**

- Use `secrets` module for tokens, never `random`
- Use `bcrypt` or `argon2` for password hashing, never MD5/SHA1
- Use `json.loads()` or `yaml.safe_load()` for untrusted data
- Use `subprocess.run()` with argument lists for shell commands

### JavaScript Security Rules

Located in `.claude/rules/security/languages/javascript/CLAUDE.md`

| Rule | Level | CWE |
|------|-------|-----|
| No dynamic code execution | strict | CWE-94 |
| Prototype pollution | strict | CWE-1321 |
| Sanitize HTML | strict | CWE-79 |
| Validate URLs | strict | CWE-601 |
| Command injection | strict | CWE-78 |
| Path traversal | strict | CWE-22 |
| Secure dependencies | warning | CWE-1104 |
| Crypto randomness | strict | CWE-330 |
| Security headers | warning | — |
| CORS configuration | strict | CWE-942 |

**Key Points:**

- Never execute dynamic code with user input
- Use `DOMPurify.sanitize()` before `innerHTML`, or prefer `textContent`
- Use `crypto.randomBytes()` for tokens, never `Math.random()`
- Use `helmet` for security headers in Express applications
- Pin exact versions in `package.json`, run `npm audit` regularly

### Docker Container Security

Located in `.claude/rules/security/containers/docker/CLAUDE.md`

| Rule | Level |
|------|-------|
| Minimal base images | strict |
| Non-root user directive | strict |
| Multi-stage builds | strict |
| No secrets in layers | strict |
| Image vulnerability scanning | strict |
| Content trust/signing | warning |
| Read-only root filesystem | warning |
| Drop all capabilities | strict |
| No privileged containers | strict |
| Container health checks | advisory |
| Resource limits | warning |
| Secure .dockerignore | warning |

**Key Points:**

- Use distroless or Alpine base images, never full Ubuntu
- Always include `USER` directive with non-root user
- Never embed secrets in `ARG`, `ENV`, or `COPY` — use BuildKit secrets
- Always `--cap-drop=ALL` and add back only what's needed
- Never use `--privileged` flag

---

## Stack Detection

ZERG automatically detects your project's tech stack by scanning:

| Detection Target | Files Scanned |
|-----------------|---------------|
| Languages | `*.py`, `*.js`, `*.ts`, `*.go`, `*.rs`, `*.java` |
| Frameworks | `requirements.txt`, `package.json`, `go.mod`, `Cargo.toml` |
| Databases | Connection strings, ORM configs, client libraries |
| Infrastructure | `Dockerfile`, `docker-compose.yml`, `.github/workflows/` |
| AI/ML | LangChain, OpenAI, HuggingFace imports |
| RAG | Vector DB clients (Pinecone, Weaviate, Chroma) |

### Detection Example

```bash
$ zerg security-rules detect

Detected Project Stack:
  Languages:      python, javascript
  Frameworks:     fastapi, react
  Databases:      postgresql
  Infrastructure: docker, github-actions
  AI/ML:          yes (langchain)
  RAG:            yes (pinecone)
```

### Rules Selection Matrix

| Stack | Rules Fetched |
|-------|---------------|
| Python | `owasp-2025.md`, `python.md` |
| Python + FastAPI | + `fastapi.md` |
| Python + LangChain | + `ai-security.md`, `langchain.md` |
| Python + Pinecone | + `rag-security.md`, `pinecone.md` |
| JavaScript | `owasp-2025.md`, `javascript.md` |
| JavaScript + Express | + `express.md` |
| Docker | + `docker.md` |

---

## `/zerg:security` Command

### Basic Usage

```bash
# Run OWASP vulnerability scan (default)
/zerg:security

# Use specific compliance preset
/zerg:security --preset pci

# Enable auto-fix suggestions
/zerg:security --autofix

# Output in SARIF format for IDE integration
/zerg:security --format sarif > security.sarif
```

### Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--preset` | Security preset: `owasp`, `pci`, `hipaa`, `soc2` | `owasp` |
| `--autofix` | Apply auto-fix suggestions | false |
| `--format` | Output format: `text`, `json`, `sarif` | `text` |
| `--help` | Show help message | — |

### Presets

| Preset | Description |
|--------|-------------|
| `owasp` | OWASP Top 10 vulnerability checks (default) |
| `pci` | PCI-DSS payment card industry compliance |
| `hipaa` | HIPAA healthcare data security requirements |
| `soc2` | SOC 2 trust service criteria |

### Capabilities

**Secret Detection:**
- API keys
- Passwords and tokens
- Private keys (RSA, SSH, PGP)
- AWS credentials
- GitHub tokens
- Generic high-entropy strings

**Dependency CVE Scanning:**
- Python (`requirements.txt`, `Pipfile.lock`)
- Node.js (`package.json`, `package-lock.json`)
- Rust (`Cargo.toml`, `Cargo.lock`)
- Go (`go.mod`, `go.sum`)

**Code Analysis:**
- Injection vulnerabilities (SQL, command, XSS)
- Authentication issues
- Access control problems
- Cryptographic weaknesses

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No vulnerabilities found |
| 1 | Vulnerabilities detected |
| 2 | Scan error |

---

## Security Rules CLI

Manage security rules outside of Claude Code sessions:

```bash
# Detect project stack
zerg security-rules detect

# List rules available for your stack
zerg security-rules list

# Fetch rules from TikiTribe repository
zerg security-rules fetch

# Full integration: detect, fetch, and update CLAUDE.md
zerg security-rules integrate
```

### `zerg security-rules detect`

Scans the project and reports detected stack components:

```bash
$ zerg security-rules detect

Detected Project Stack:
  Languages:      python
  Frameworks:     fastapi, langchain
  Databases:      pinecone
  Infrastructure: docker, github-actions
  AI/ML:          yes
  RAG:            yes
```

### `zerg security-rules list`

Shows which rules would be fetched for your stack:

```bash
$ zerg security-rules list

Rules for detected stack:
  _core/owasp-2025.md
  languages/python/CLAUDE.md
  frameworks/fastapi/CLAUDE.md
  ai/langchain/CLAUDE.md
  containers/docker/CLAUDE.md
```

### `zerg security-rules fetch`

Downloads rules to `.claude/rules/security/`:

```bash
$ zerg security-rules fetch

Fetching rules from TikiTribe/claude-secure-coding-rules...
  [OK] _core/owasp-2025.md
  [OK] languages/python/CLAUDE.md
  [OK] frameworks/fastapi/CLAUDE.md
  [OK] ai/langchain/CLAUDE.md
  [OK] containers/docker/CLAUDE.md

5 rules fetched to .claude/rules/security/
```

### `zerg security-rules integrate`

Full integration: detect, fetch, and update CLAUDE.md:

```bash
$ zerg security-rules integrate

[1/3] Detecting project stack...
  Languages: python
  Infrastructure: docker

[2/3] Fetching security rules...
  3 rules fetched

[3/3] Updating CLAUDE.md...
  Added SECURITY_RULES section

Integration complete!
```

---

## Pre-commit Hooks

ZERG integrates with [pre-commit](https://pre-commit.com/) to enforce security on every commit.

### Setup

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install
```

### Configuration

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  # Secret detection
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']

  # Python security linting
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ['-c', 'pyproject.toml']
        additional_dependencies: ['bandit[toml]']

  # Dockerfile linting
  - repo: https://github.com/hadolint/hadolint
    rev: v2.12.0
    hooks:
      - id: hadolint

  # Dependency vulnerability scanning
  - repo: https://github.com/pyupio/safety
    rev: 2.3.5
    hooks:
      - id: safety
        args: ['--full-report']
```

### Bandit Configuration

Add to `pyproject.toml`:

```toml
[tool.bandit]
exclude_dirs = ["tests", "venv", ".venv"]
skips = ["B101"]  # Skip assert warnings in production code

[tool.bandit.assert_used]
skips = ["*_test.py", "test_*.py"]
```

### Secret Baseline

Initialize secret detection baseline:

```bash
# Create baseline of existing secrets (to avoid false positives)
detect-secrets scan > .secrets.baseline

# Audit baseline
detect-secrets audit .secrets.baseline
```

---

## Vulnerability Reporting

### Reporting Security Issues

If you discover a security vulnerability in ZERG:

1. **Do NOT** open a public GitHub issue
2. Email security concerns to the maintainers privately
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

| Phase | Timeline |
|-------|----------|
| Initial response | 48 hours |
| Vulnerability assessment | 7 days |
| Patch development | 30 days |
| Public disclosure | After patch release |

### Security Advisories

Security advisories are published via:
- GitHub Security Advisories
- CHANGELOG.md security section
- Release notes

---

## Security Checklist

Quick reference for developers:

### Before Committing

- [ ] No secrets in code (API keys, passwords, tokens)
- [ ] No hardcoded credentials
- [ ] User input is validated and sanitized
- [ ] SQL queries use parameterization
- [ ] File paths are validated against traversal
- [ ] Dependencies are pinned with lockfiles
- [ ] Dockerfile uses non-root user

### Before Deployment

- [ ] `zerg security-rules integrate` has been run
- [ ] `/zerg:security` scan passes
- [ ] Pre-commit hooks are installed
- [ ] Dependency vulnerabilities are addressed
- [ ] Container images are scanned
- [ ] Secrets are in environment variables or secret manager

### Code Review Security Items

- [ ] Authentication and authorization checks present
- [ ] Error handling doesn't leak sensitive information
- [ ] Logging doesn't include sensitive data
- [ ] Cryptographic operations use approved algorithms
- [ ] Session management follows best practices

---

## Related Pages

- [Configuration](Configuration) — Security-related configuration options
- [Command-Reference](Command-Reference) — Full `/zerg:security` documentation
- [Plugins](Plugins) — Security-focused quality gates
- [Troubleshooting](Troubleshooting) — Security scanning issues

---

## External Resources

- [TikiTribe/claude-secure-coding-rules](https://github.com/TikiTribe/claude-secure-coding-rules) — Source repository for security rules
- [OWASP Top 10:2025](https://owasp.org/Top10/) — Official OWASP documentation
- [CWE Database](https://cwe.mitre.org/) — Common Weakness Enumeration
- [NIST Secure Software Development Framework](https://csrc.nist.gov/projects/ssdf) — NIST SSDF guidelines
