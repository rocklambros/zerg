# ZERG Security

Security review, vulnerability scanning, and hardening recommendations.

## Usage

```bash
/zerg:security [--preset owasp|pci|hipaa|soc2]
               [--autofix]
               [--format text|json|sarif]
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
