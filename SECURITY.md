# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

**Do not file public GitHub issues for security vulnerabilities.**

Report vulnerabilities privately through [GitHub Security Advisories](https://github.com/rocklambros/zerg/security/advisories/new).

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 72 hours
- **Initial assessment**: Within 1 week
- **Critical fixes**: Within 30 days
- **Non-critical fixes**: Next scheduled release

## Scope

The following are considered security issues:

- Subprocess command injection or escape
- Docker container escape or privilege escalation
- Unauthorized host filesystem access
- Credential exposure (API keys, OAuth tokens)
- Path traversal in file operations
- Insecure deserialization

The following are NOT security issues (file as regular issues):

- Slash command logic bugs
- Documentation errors
- Feature requests
- Performance issues

## Credit

We credit responsible disclosure in our CHANGELOG. If you'd like to be credited, include your preferred name and optional link in your report.

## Security Architecture

ZERG integrates security rules from [OWASP Top 10 2025](https://owasp.org/Top10/) and language-specific rulesets (Python, JavaScript, Docker). Rules are auto-fetched during project initialization and filtered per file type to minimize token overhead. See [docs/context-engineering.md](docs/context-engineering.md) for details.

## Key Security Controls

### Subprocess Execution

ZERG spawns subprocess commands with the following protections:

- **Argument validation**: Worker tasks pass arguments through the Task system, preventing shell metacharacter injection
- **No shell=True by default**: Commands execute directly without shell interpretation
- **Timeout enforcement**: All subprocess calls have configurable timeouts to prevent infinite hangs
- **Output sanitization**: Stderr and stdout are captured and logged without interpretation

### Docker Container Isolation

Containers executed with `--mode container` enforce these controls:

- **Non-root user**: Containers run as UID 10001 (appuser) instead of root
- **Capability dropping**: All Linux capabilities dropped except NET_BIND_SERVICE if required
- **Read-only filesystem**: Root filesystem mounted read-only with tmpfs for writable directories
- **Resource limits**: Memory, CPU, and PID limits enforced via configuration
- **No privileged flag**: Never use `--privileged` mode

See [.claude/rules/security/containers/docker/CLAUDE.md](.claude/rules/security/containers/docker/CLAUDE.md) for complete Docker security ruleset.

### Host Filesystem Access

ZERG mounts host directories into containers with these restrictions:

- **Explicit mount paths**: Only directories specified in task configuration are mounted
- **No root mounts**: Never mount `/`, `/etc`, `/sys`, or `/proc` directories
- **Read-write validation**: Mount permissions (ro/rw) explicitly controlled and documented
- **Path traversal prevention**: Symlinks and `../` sequences validated before mounting
- **Volume cleanup**: Temporary volumes automatically removed after task completion

### Credential Management

API keys and secrets are handled securely:

- **Environment variable injection**: Secrets passed via `ANTHROPIC_API_KEY` and `CLAUDE_CODE_TASK_LIST_ID` only
- **No secrets in task descriptions**: Never include credentials in task titles or descriptions
- **BuildKit secret mounting**: Docker build secrets mounted via `--mount=type=secret` to avoid layer storage
- **OAuth token caching**: Tokens stored in `~/.claude/` directory with restricted permissions (0600)
- **Credential rotation**: Stale tokens automatically cleared during cleanup phases

### File Operation Safety

Python and JavaScript code execution follows these principles:

- **Parameterized queries**: Database operations use parameterized statements (SQLAlchemy, prepared statements)
- **Safe deserialization**: Deserialization limited to JSON and safe loaders only
- **Command safety**: Uses `subprocess.run()` with argument lists, never shell interpretation
- **Path validation**: File operations validated against allowlist of safe directories

See language-specific rulesets:
- [.claude/rules/security/languages/python/CLAUDE.md](.claude/rules/security/languages/python/CLAUDE.md)
- [.claude/rules/security/languages/javascript/CLAUDE.md](.claude/rules/security/languages/javascript/CLAUDE.md)

## Common Vulnerabilities and Mitigations

### Command Injection

**Vulnerability**: Unvalidated task arguments passed to shell commands.

**Mitigation**: Arguments passed through Task system undergo validation before execution. Subprocess calls use argument arrays, not string interpolation.

```python
# Secure (subprocess with args list)
subprocess.run(['grep', pattern, filename], check=True)

# Insecure (shell interpolation)
subprocess.run(f'grep {pattern} {filename}', shell=True)
```

### Container Escape

**Vulnerability**: Running containers in privileged mode or with excessive capabilities.

**Mitigation**: Strict enforcement of least-privilege container configuration. See Docker security controls above.

### Path Traversal

**Vulnerability**: File operations accepting `../` sequences leading to unauthorized access.

**Mitigation**: All file paths resolved to absolute paths and validated against allowlist.

```python
# Secure
from pathlib import Path
safe_dir = Path('/app/uploads').resolve()
requested = (safe_dir / filename).resolve()
if not requested.is_relative_to(safe_dir):
    raise ValueError("Path traversal attempt")
```

### Credential Exposure

**Vulnerability**: API keys or tokens stored in plaintext or logged.

**Mitigation**: Credentials only passed through secure channels (environment variables, mounted secrets). Stdout/stderr sanitized before logging.

## Compliance

ZERG security practices align with:

- **OWASP Top 10 2025**: Core web security vulnerabilities addressed
- **CIS Docker Benchmark**: Container hardening guidelines followed
- **NIST 800-190**: Container security best practices implemented
- **OWASP A01:2025**: Access control and authorization enforced at subprocess execution layer
- **OWASP A03:2025**: Injection prevention via argument validation and parameterized queries
- **OWASP A06:2025**: Secure design with threat modeling for parallel execution scenarios

## Threat Model

### Threat Actor: Malicious Task Input

**Scenario**: User provides a task with crafted arguments to inject arbitrary commands.

**Impact**: Arbitrary code execution on host or container.

**Mitigation**: Task arguments validated by Task system. Subprocess calls use argument arrays. No shell interpolation.

### Threat Actor: Compromised Container

**Scenario**: Application inside container is compromised and attempts privilege escalation or escape.

**Impact**: Access to host system and other containers.

**Mitigation**: Containers run as non-root with capabilities dropped. Read-only root filesystem. Resource limits prevent fork bombs.

### Threat Actor: Malicious Host Directory

**Scenario**: User mounts a host directory containing symbolic links or untrusted files.

**Impact**: TOCTOU attacks, symlink escalation, unauthorized file access.

**Mitigation**: Mount paths validated. Symlinks detected during mounting. Task file ownership restrictions enforce sandboxing.

### Threat Actor: Secret Exposure

**Scenario**: ANTHROPIC_API_KEY or other credentials exposed in logs or task descriptions.

**Impact**: Unauthorized API access, token abuse.

**Mitigation**: Credentials only passed through secure environment variables. Stdout/stderr sanitized. Credentials never logged.

## Testing and Validation

### Security Testing Checklist

Before each release, validate:

- [ ] Subprocess argument validation tests pass
- [ ] Docker container non-root execution verified
- [ ] File path traversal attempts rejected
- [ ] Credential environment variables never logged
- [ ] Symlink mount detection functional
- [ ] Resource limits enforced on containers

### Running Security Tests

```bash
# Run security rule validation
python -m pytest tests/security/ -v

# Check for common vulnerabilities
bandit -r zerg/ -f json

# Lint Dockerfiles
hadolint Dockerfile

# Scan dependencies for vulnerabilities
pip-audit requirements.txt
npm audit
```

## Dependencies and Supply Chain

ZERG depends on:

- **Python libraries**: Validated against `pip-audit` for known vulnerabilities
- **Base Docker images**: Alpine and distroless images used for minimal attack surface
- **Language runtimes**: Python 3.10+ and Node.js 18+ required, pinned in Dockerfile

All dependencies are pinned to exact versions in lockfiles. Updates validated through security scanning before merging.

## Questions or Concerns?

For security clarification (non-disclosure), file a discussion in [GitHub Discussions](https://github.com/rocklambros/zerg/discussions).
