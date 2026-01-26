# ZERG Security

Security review, vulnerability scanning, secure coding rules, and hardening recommendations.

## Usage

```bash
# Vulnerability scanning
/zerg:security [--preset owasp|pci|hipaa|soc2]
               [--autofix]
               [--format text|json|sarif]

# Secure coding rules management
zerg security-rules detect      # Detect project stack
zerg security-rules list        # List rules for your stack
zerg security-rules fetch       # Download rules
zerg security-rules integrate   # Full integration with CLAUDE.md
```

## Secure Coding Rules

ZERG integrates with [TikiTribe/claude-secure-coding-rules](https://github.com/TikiTribe/claude-secure-coding-rules) to provide stack-specific security guidance.

### Automatic Stack Detection

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

### Intelligent Rule Selection

Only fetches rules relevant to your stack:

| Stack | Rules Fetched |
|-------|---------------|
| Python | `owasp-2025.md`, `python.md` |
| Python + FastAPI | + `fastapi.md` |
| Python + LangChain | + `ai-security.md`, `langchain.md` |
| Python + Pinecone | + `rag-security.md`, `pinecone.md` |

### Integration with CLAUDE.md

Rules are automatically imported into your project's `CLAUDE.md`:

```markdown
<!-- SECURITY_RULES_START -->
# Security Rules
@.claude/security-rules/_core/owasp-2025.md
@.claude/security-rules/languages/python.md
<!-- SECURITY_RULES_END -->
```

## Presets

### OWASP (default)
OWASP Top 10 vulnerability checks:
- A01: Broken Access Control
- A02: Cryptographic Failures
- A03: Injection
- A04: Insecure Design
- A05: Security Misconfiguration
- A06: Vulnerable Components
- A07: Authentication Failures
- A08: Data Integrity Failures
- A09: Logging Failures
- A10: SSRF

### PCI-DSS
Payment Card Industry Data Security Standard compliance checks.

### HIPAA
Health Insurance Portability and Accountability Act security requirements.

## Capabilities

### Secret Detection
- API keys
- Passwords
- Tokens
- Private keys
- AWS credentials
- GitHub tokens

### Dependency CVE Scanning
- Python (requirements.txt)
- Node.js (package.json)
- Rust (Cargo.toml)
- Go (go.mod)

### Code Analysis
- Injection vulnerabilities
- XSS patterns
- Authentication issues
- Access control problems

## Examples

```bash
# Run OWASP scan
/zerg:security

# PCI compliance check
/zerg:security --preset pci

# With auto-fix suggestions
/zerg:security --autofix

# SARIF for IDE integration
/zerg:security --format sarif > security.sarif
```

## Exit Codes

- 0: No vulnerabilities found
- 1: Vulnerabilities detected
- 2: Scan error
