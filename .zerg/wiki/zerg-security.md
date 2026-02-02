# /zerg:security

Security review, vulnerability scanning, secure coding rules, and hardening recommendations.

## Synopsis

```
/zerg:security [--preset owasp|pci|hipaa|soc2]
               [--autofix]
               [--format text|json|sarif]
```

```
/zerg:security-rules detect
/zerg:security-rules list
/zerg:security-rules fetch
/zerg:security-rules integrate
```

## Description

The `security` command provides two capabilities: vulnerability scanning against compliance presets, and secure coding rule management integrated with the Claude Code agent.

### Vulnerability Scanning

Runs security scans against the codebase using the selected compliance preset. Capabilities include:

- **Secret detection**: API keys, passwords, tokens, private keys, AWS credentials, GitHub tokens.
- **Dependency CVE scanning**: Checks `requirements.txt` (Python), `package.json` (Node.js), `Cargo.toml` (Rust), and `go.mod` (Go) against known vulnerability databases.
- **Code analysis**: Injection vulnerabilities, XSS patterns, authentication issues, and access control problems.

### Secure Coding Rules

ZERG integrates with [TikiTribe/claude-secure-coding-rules](https://github.com/TikiTribe/claude-secure-coding-rules) to provide stack-specific security guidance. The subcommands manage rule lifecycle:

- `detect` -- Automatically detect the project technology stack (languages, frameworks, databases, infrastructure, AI/ML).
- `list` -- List all rules relevant to the detected stack.
- `fetch` -- Download rules from the upstream repository.
- `integrate` -- Store rules in `.claude/rules/security/` and add an informational summary to `CLAUDE.md`.

### Compliance Presets

| Preset | Description |
|--------|-------------|
| `owasp` (default) | OWASP Top 10 vulnerability checks covering broken access control, cryptographic failures, injection, insecure design, security misconfiguration, vulnerable components, authentication failures, data integrity failures, logging failures, and SSRF. |
| `pci` | PCI-DSS (Payment Card Industry Data Security Standard) compliance checks. |
| `hipaa` | HIPAA (Health Insurance Portability and Accountability Act) security requirements. |
| `soc2` | SOC 2 compliance checks. |

### Intelligent Rule Selection

Rules fetched depend on the detected stack:

| Stack | Rules Fetched |
|-------|---------------|
| Python | `owasp-2025.md`, `python.md` |
| Python + FastAPI | + `fastapi.md` |
| Python + LangChain | + `ai-security.md`, `langchain.md` |
| Python + Pinecone | + `rag-security.md`, `pinecone.md` |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--preset` | `owasp` | Compliance preset to scan against. Accepts `owasp`, `pci`, `hipaa`, or `soc2`. |
| `--autofix` | off | Generate and suggest automatic fix patches for detected vulnerabilities. |
| `--format` | `text` | Output format. Accepts `text`, `json`, or `sarif`. |

## Examples

Run an OWASP scan with defaults:

```
/zerg:security
```

Run a PCI compliance check:

```
/zerg:security --preset pci
```

Scan with auto-fix suggestions:

```
/zerg:security --autofix
```

Generate SARIF output for IDE integration:

```
/zerg:security --format sarif > security.sarif
```

Detect the project stack and fetch matching rules:

```
/zerg:security-rules detect
/zerg:security-rules fetch
/zerg:security-rules integrate
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No vulnerabilities found |
| 1 | Vulnerabilities detected |
| 2 | Scan error |

## Task Tracking

This command creates a Claude Code Task with the subject prefix `[Security]` on invocation, updates it to `in_progress` immediately, and marks it `completed` on success.

## See Also

- [[zerg-analyze]] -- General static analysis including a security check type
- [[zerg-review]] -- Code review with security considerations
- [[zerg-build]] -- Build verification after applying security fixes
