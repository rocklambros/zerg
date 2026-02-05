# Security

This guide explains how ZERG keeps your development environment safe and why each protection matters.

---

## Why Security Matters in AI Assistants

AI coding assistants are incredibly powerful. They can:

- **Write code** that runs directly on your machine
- **Access files** anywhere on your filesystem
- **Execute commands** in your terminal
- **Make network requests** to external services

This power comes with responsibility. Without guardrails, a mistake (or a cleverly-crafted malicious prompt) could:

- Delete important files
- Expose sensitive credentials
- Install unwanted software
- Leak proprietary code

**ZERG adds layers of protection** so you can harness AI assistance confidently. The goal is not to limit what you can do, but to ensure you're always in control.

---

## Understanding the Threat Model

Before diving into protections, let's understand what could go wrong. Security experts think in terms of **threats** — who might cause harm, how they might do it, and what the impact would be.

### What Could Go Wrong?

| Risk | Example | Impact |
|------|---------|--------|
| **Accidental file deletion** | AI misunderstands "clean up temp files" and deletes source code | Lost work, potentially unrecoverable |
| **Secret exposure** | API keys accidentally committed to git | Financial loss, compromised accounts |
| **Command injection** | Malicious input tricks the system into running harmful commands | System compromise |
| **Dependency vulnerabilities** | Outdated packages with known security holes | Your application becomes exploitable |
| **Prompt injection** | Malicious content in files tricks the AI into harmful actions | Unintended code execution |

### Who Might Exploit This?

- **Accidental misuse** — Most common. You or a teammate make a mistake.
- **Supply chain attacks** — Compromised dependencies bring hidden vulnerabilities.
- **Malicious inputs** — Untrusted files or repositories contain hidden payloads.

### What's the Impact?

The severity depends on what's compromised:

- **Low**: Minor annoyance, easily recoverable
- **Medium**: Lost time, need to rotate credentials
- **High**: Data breach, financial loss, reputation damage

---

## How ZERG Addresses Each Threat

### 1. Shift-Left Security — Catch Issues Early

**Threat addressed**: Vulnerabilities slip into production because they're found too late.

**How it works**: ZERG embeds security guidance directly into your development workflow:

1. **Auto-detection** — Scans your project to detect languages, frameworks, and infrastructure
2. **Intelligent rule fetching** — Downloads only rules relevant to your stack
3. **Claude Code integration** — Rules are stored where Claude automatically reads them
4. **Pre-commit enforcement** — Validates security on every commit

**What you need to do**: Run `/zerg:init` once. ZERG handles the rest.

### 2. Stack-Aware Security Rules

**Threat addressed**: Generic security advice doesn't catch language-specific vulnerabilities.

**How it works**: ZERG detects your tech stack and fetches targeted rules:

```
Your Project                    Rules Fetched
├── Python code          →      Python security rules (CWE-502, CWE-78, etc.)
├── JavaScript code      →      JavaScript rules (XSS, prototype pollution, etc.)
├── Dockerfile           →      Container security (non-root, secrets, etc.)
└── AI/ML imports        →      AI-specific rules (prompt injection, etc.)
```

Rules are stored in `.claude/rules/security/` where Claude Code automatically loads them:

```
.claude/
└── rules/
    └── security/
        ├── _core/
        │   └── owasp-2025.md        # Core OWASP Top 10 rules
        ├── languages/
        │   ├── python/CLAUDE.md     # Python-specific rules
        │   └── javascript/CLAUDE.md # JavaScript-specific rules
        └── containers/
            └── docker/CLAUDE.md     # Docker security rules
```

**What you need to do**: Run `zerg security-rules integrate` to fetch rules for your stack.

### 3. OWASP Top 10 Coverage

**Threat addressed**: Common web vulnerabilities that affect most applications.

**How it works**: ZERG includes comprehensive coverage of **OWASP Top 10:2025**, the industry standard for web application security risks.

| Category | What It Prevents | Example Attack |
|----------|-----------------|----------------|
| **A01: Broken Access Control** | Unauthorized data access | User A reads User B's data |
| **A02: Security Misconfiguration** | Insecure default settings | Debug mode left on in production |
| **A03: Supply Chain Failures** | Compromised dependencies | Malicious package update |
| **A04: Cryptographic Failures** | Weak encryption | Passwords stored in plain text |
| **A05: Injection** | Malicious input execution | SQL injection, command injection |
| **A06: Insecure Design** | Fundamental architecture flaws | No rate limiting on login |
| **A07: Authentication Failures** | Account compromise | Weak session management |
| **A08: Integrity Failures** | Data tampering | Unsigned software updates |
| **A09: Logging Failures** | Blind spots in monitoring | Attacks go undetected |
| **A10: Error Handling** | Information leakage | Stack traces shown to users |

Each rule has an enforcement level:

| Level | What It Means |
|-------|---------------|
| `strict` | Must follow. Violations are security vulnerabilities. |
| `warning` | Should follow. Violations may indicate security weaknesses. |
| `advisory` | Recommended. Improves security posture. |

**What you need to do**: Review the rules in `.claude/rules/security/` to understand what's being enforced.

### 4. Secret Detection

**Threat addressed**: Accidentally committing API keys, passwords, or tokens to version control.

**How it works**: ZERG scans for high-entropy strings and known secret patterns:

- API keys (AWS, Google, GitHub, etc.)
- Passwords and tokens
- Private keys (RSA, SSH, PGP)
- Database connection strings

**What you need to do**:
1. Add secret detection to your pre-commit hooks
2. Run `detect-secrets scan > .secrets.baseline` to create a baseline
3. Never commit files matching `.env*` or `*.key`

### 5. Dependency Vulnerability Scanning

**Threat addressed**: Using packages with known security holes.

**How it works**: ZERG scans your dependency files for CVEs (Common Vulnerabilities and Exposures):

| Package Manager | Files Scanned |
|----------------|---------------|
| Python | `requirements.txt`, `Pipfile.lock` |
| Node.js | `package.json`, `package-lock.json` |
| Rust | `Cargo.toml`, `Cargo.lock` |
| Go | `go.mod`, `go.sum` |

**What you need to do**: Run `/zerg:security` regularly and address flagged vulnerabilities.

### 6. Container Security

**Threat addressed**: Insecure Docker configurations that could compromise your system.

**How it works**: ZERG enforces container security best practices:

| Rule | Why It Matters |
|------|---------------|
| **Minimal base images** | Fewer packages = fewer vulnerabilities |
| **Non-root user** | Limits damage if container is compromised |
| **No secrets in layers** | Secrets in images are extractable forever |
| **Multi-stage builds** | Build tools don't end up in production |
| **Drop all capabilities** | Limits what the container can do |
| **Read-only filesystem** | Prevents persistent modifications |

**What you need to do**: Follow the Dockerfile rules in `.claude/rules/security/containers/docker/CLAUDE.md`.

---

## Security Commands

### `/zerg:security` — Run Security Scan

```bash
# Run OWASP vulnerability scan (default)
/zerg:security

# Use specific compliance preset
/zerg:security --preset pci

# Enable auto-fix suggestions
/zerg:security --autofix

# Output for IDE integration
/zerg:security --format sarif > security.sarif
```

| Preset | Purpose |
|--------|---------|
| `owasp` | General web application security (default) |
| `pci` | Payment card industry compliance |
| `hipaa` | Healthcare data security |
| `soc2` | Trust service criteria |

### `zerg security-rules` — Manage Security Rules

```bash
# See what stack ZERG detected
zerg security-rules detect

# Preview which rules would be fetched
zerg security-rules list

# Download rules for your stack
zerg security-rules fetch

# Full setup: detect, fetch, update CLAUDE.md
zerg security-rules integrate
```

---

## Security Best Practices

The most important actions you can take:

### Before Every Commit

1. **No secrets in code** — Use environment variables or a secret manager
2. **Validate user input** — Never trust external data
3. **Use parameterized queries** — Prevent SQL injection
4. **Pin dependencies** — Use lockfiles with exact versions

### Set Up Once, Benefit Forever

1. **Install pre-commit hooks** — Catch issues automatically
   ```bash
   pip install pre-commit
   pre-commit install
   ```

2. **Run security integration** — Fetch rules for your stack
   ```bash
   zerg security-rules integrate
   ```

3. **Create a secret baseline** — Avoid false positives
   ```bash
   detect-secrets scan > .secrets.baseline
   detect-secrets audit .secrets.baseline
   ```

### During Code Review

- [ ] Authentication and authorization checks present
- [ ] Error handling doesn't leak sensitive information
- [ ] Logging doesn't include passwords or tokens
- [ ] Cryptographic operations use approved algorithms

---

## Language-Specific Quick Reference

### Python Security Essentials

| Do This | Not This | Why |
|---------|----------|-----|
| `secrets.token_urlsafe(32)` | `random.random()` | Predictable tokens can be guessed |
| `bcrypt.hashpw(password)` | `hashlib.md5(password)` | MD5 is trivially crackable |
| `json.loads(data)` | `pickle.loads(data)` | Pickle executes arbitrary code |
| `subprocess.run(['ls', path])` | `os.system(f'ls {path}')` | Shell injection risk |

### JavaScript Security Essentials

| Do This | Not This | Why |
|---------|----------|-----|
| `crypto.randomBytes(32)` | `Math.random()` | Predictable tokens |
| `element.textContent = x` | Direct DOM HTML insertion | XSS vulnerability |
| `JSON.parse(data)` | Dynamic code execution | Arbitrary code execution |
| Use `helmet` middleware | No headers | Missing security protections |

### Docker Security Essentials

| Do This | Not This | Why |
|---------|----------|-----|
| `FROM python:3.12-alpine` | `FROM ubuntu:latest` | Smaller attack surface |
| `USER appuser` | (no USER directive) | Runs as root by default |
| `--cap-drop=ALL` | `--privileged` | Limit container capabilities |
| BuildKit secrets | `ENV API_KEY=xxx` | Secrets visible in history |

---

## Reporting Security Issues

If you discover a vulnerability in ZERG:

1. **Do NOT** open a public GitHub issue
2. Email security concerns to the maintainers privately
3. Include: description, reproduction steps, potential impact

| Phase | Timeline |
|-------|----------|
| Initial response | 48 hours |
| Assessment | 7 days |
| Patch development | 30 days |
| Public disclosure | After patch release |

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
