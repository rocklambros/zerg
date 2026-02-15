"""Security scanning functions for ZERG.

Migrated from zerg/security.py — contains all scan functions and constants.
Upgraded in TASK-004 to use PATTERN_REGISTRY from patterns.py and return
SecurityResult with structured findings.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from zerg.logging import get_logger
from zerg.security.patterns import PATTERN_REGISTRY, SecurityPattern

logger = get_logger("security")

# ---------------------------------------------------------------------------
# Code extensions recognized for content scanning
# ---------------------------------------------------------------------------
_CODE_EXTENSIONS: set[str] = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".md",
    ".txt",
    ".sh",
    ".bash",
    ".env",
    ".html",
    ".css",
    ".toml",
    ".cfg",
    ".dockerfile",
}

# Directories to skip during file collection
_SKIP_DIRS: set[str] = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
}

# Patterns for detecting potential secrets
SECRET_PATTERNS = [
    re.compile(r"password\s*[=:]\s*['\"][^'\"]{8,}['\"]", re.IGNORECASE),
    re.compile(r"secret\s*[=:]\s*['\"][^'\"]{8,}['\"]", re.IGNORECASE),
    re.compile(r"api_?key\s*[=:]\s*['\"][^'\"]{16,}['\"]", re.IGNORECASE),
    re.compile(r"access_?token\s*[=:]\s*['\"][^'\"]{16,}['\"]", re.IGNORECASE),
    re.compile(r"auth_?token\s*[=:]\s*['\"][^'\"]{16,}['\"]", re.IGNORECASE),
    re.compile(r"private_?key\s*[=:]\s*['\"][^'\"]{16,}['\"]", re.IGNORECASE),
    re.compile(r"-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"ghp_[A-Za-z0-9]{36}", re.IGNORECASE),  # GitHub Personal Access Token
    re.compile(r"gho_[A-Za-z0-9]{36}", re.IGNORECASE),  # GitHub OAuth Token
    re.compile(r"sk-[A-Za-z0-9]{48}", re.IGNORECASE),  # OpenAI API Key
    re.compile(r"AKIA[A-Z0-9]{16}", re.IGNORECASE),  # AWS Access Key ID
]

# Hook patterns for pre-commit checks
# These patterns are used by both the bash hook and Python validation
HOOK_PATTERNS = {
    # Security patterns (BLOCK on violation)
    "security": {
        "aws_key": r"AKIA[0-9A-Z]{16}",
        "github_pat": r"(ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9]{20,}_[a-zA-Z0-9]{40,})",
        "openai_key": r"sk-[a-zA-Z0-9]{48}",
        "anthropic_key": r"sk-ant-[a-zA-Z0-9\-]{90,}",
        "private_key": r"-----BEGIN (RSA|DSA|EC|OPENSSH|PGP) PRIVATE KEY-----",
        "generic_secret": (
            r"(password|secret|api_key|apikey|access_token|auth_token)" r"\s*[=:]\s*['\"][^'\"]{8,}['\"]"
        ),
        "shell_injection": r"(shell\s*=\s*True|os\.system\s*\(|os\.popen\s*\()",
        "code_injection": r"^[^#]*\b(eval|exec)\s*\(",
        # Detect unsafe deserialization usage
        "unsafe_deserialization": r"pickle\.(load|loads)\s*\(",
    },
    # Quality patterns (WARN on violation)
    "quality": {
        "debugger": r"(breakpoint\s*\(\)|pdb\.set_trace\s*\(\)|import\s+i?pdb)",
        "merge_conflict": r"^(<{7}|={7}|>{7})",
        "print_stmt": r"^[^#]*\bprint\s*\(",
    },
    # ZERG-specific patterns
    "zerg": {
        "branch_name": r"^zerg/[a-z0-9-]+/worker-[0-9]+$",
        "localhost": r"(localhost|127\.0\.0\.1|0\.0\.0\.0):[0-9]+",
    },
}

# Sensitive file names to warn about
SENSITIVE_FILES = [
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "credentials.json",
    "service-account.json",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    ".npmrc",
    ".pypirc",
]


def check_for_secrets(content: str) -> list[tuple[int, str, str]]:
    """Check content for potential secrets.

    Args:
        content: Text content to check

    Returns:
        List of (line_number, pattern_name, matched_text) tuples
    """
    findings = []

    for line_num, line in enumerate(content.split("\n"), start=1):
        for pattern in SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                # Mask the actual secret value
                masked = line[:50] + "..." if len(line) > 50 else line
                findings.append((line_num, pattern.pattern[:30] + "...", masked))

    return findings


def check_for_non_ascii_filenames(files: list[str]) -> list[str]:
    """Check for non-ASCII characters in filenames.

    Args:
        files: List of file paths to check

    Returns:
        List of files with non-ASCII characters
    """
    non_ascii = []

    for filepath in files:
        # Check if any character is non-ASCII
        try:
            filepath.encode("ascii")
        except UnicodeEncodeError:
            non_ascii.append(filepath)

    return non_ascii


def check_sensitive_files(files: list[str]) -> list[str]:
    """Check for sensitive files in the list.

    Args:
        files: List of file paths to check

    Returns:
        List of sensitive files found
    """
    sensitive = []

    for filepath in files:
        filename = Path(filepath).name
        if filename in SENSITIVE_FILES:
            sensitive.append(filepath)

    return sensitive


def validate_commit_message(message: str) -> tuple[bool, str | None]:
    """Validate commit message format.

    Args:
        message: Commit message to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not message:
        return False, "Commit message is empty"

    first_line = message.split("\n")[0].strip()

    if len(first_line) < 10:
        return False, "Commit message too short (minimum 10 characters)"

    if len(first_line) > 72:
        return False, "Commit message first line too long (maximum 72 characters)"

    # Check for conventional commit format
    conventional_pattern = re.compile(r"^(feat|fix|docs|style|refactor|test|chore|build|ci|perf|revert)(\(.+\))?!?: .+")

    if not conventional_pattern.match(first_line) and not first_line.startswith("Merge "):
        return False, (
            "Commit message doesn't follow conventional commit format. "
            "Use: feat|fix|docs|style|refactor|test|chore|build|ci|perf|revert"
        )

    return True, None


def check_file_size(filepath: str | Path, max_size_mb: float = 5.0) -> bool:
    """Check if file exceeds maximum size.

    Args:
        filepath: Path to file
        max_size_mb: Maximum size in megabytes

    Returns:
        True if file is within size limit
    """
    path = Path(filepath)
    if not path.exists():
        return True

    size_bytes = path.stat().st_size
    max_bytes = max_size_mb * 1024 * 1024

    return size_bytes <= max_bytes


def get_large_files(files: list[str], max_size_mb: float = 5.0) -> list[tuple[str, float]]:
    """Get list of files exceeding size limit.

    Args:
        files: List of file paths to check
        max_size_mb: Maximum size in megabytes

    Returns:
        List of (filepath, size_mb) tuples for large files
    """
    large = []
    max_bytes = max_size_mb * 1024 * 1024

    for filepath in files:
        path = Path(filepath)
        if path.exists():
            size_bytes = path.stat().st_size
            if size_bytes > max_bytes:
                size_mb = size_bytes / (1024 * 1024)
                large.append((filepath, round(size_mb, 2)))

    return large


# ---------------------------------------------------------------------------
# Legacy scan (backward compatibility)
# ---------------------------------------------------------------------------


def _legacy_scan(path: str | Path = ".") -> dict[str, Any]:
    """Run a security scan returning a dict (legacy API).

    This is the original run_security_scan() preserved for backward
    compatibility.  The primary API is now :func:`run_security_scan`
    which returns a :class:`SecurityResult`.

    Args:
        path: Path to scan

    Returns:
        Dictionary with scan results
    """
    scan_path = Path(path).resolve()
    results: dict[str, Any] = {
        "secrets_found": [],
        "sensitive_files": [],
        "non_ascii_files": [],
        "large_files": [],
        "symlink_violations": [],
        "passed": True,
    }

    # Collect all files
    all_files = []
    for root, dirs, files in os.walk(scan_path, followlinks=False):
        # Skip git and cache directories
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]

        for f in files:
            filepath = os.path.join(root, f)

            # Validate path stays within scan boundary (defense against symlink escapes)
            try:
                resolved = Path(filepath).resolve()
                if not resolved.is_relative_to(scan_path):
                    logger.warning("Symlink escape detected, skipping: %s", filepath)
                    results["symlink_violations"].append(filepath)
                    continue
            except (OSError, ValueError) as e:
                logger.warning("Path resolution error, skipping %s: %s", filepath, e)
                continue

            all_files.append(str(resolved))

    # Check for sensitive files
    results["sensitive_files"] = check_sensitive_files(all_files)

    # Check for non-ASCII filenames
    results["non_ascii_files"] = check_for_non_ascii_filenames(all_files)

    # Check for large files
    results["large_files"] = get_large_files(all_files)

    # Check for secrets in text files
    text_extensions = {".py", ".js", ".ts", ".json", ".yaml", ".yml", ".md", ".txt", ".sh", ".env"}
    for filepath in all_files:
        if Path(filepath).suffix in text_extensions:
            try:
                file_content = Path(filepath).read_text(encoding="utf-8", errors="ignore")
                secrets = check_for_secrets(file_content)
                if secrets:
                    results["secrets_found"].append(
                        {
                            "file": filepath,
                            "findings": secrets,
                        }
                    )
            except OSError:
                pass  # Best-effort file read

    # Determine if scan passed
    results["passed"] = not (results["secrets_found"] or results["sensitive_files"])

    return results


# ---------------------------------------------------------------------------
# File collection helpers
# ---------------------------------------------------------------------------


def _collect_files(
    scan_path: Path,
    explicit_files: list[str] | None = None,
) -> list[str]:
    """Collect files to scan within the project tree.

    Args:
        scan_path: Resolved root directory of the scan.
        explicit_files: If provided, use this list instead of walking the tree.
            Paths are resolved and boundary-checked against *scan_path*.

    Returns:
        Sorted list of absolute file paths (strings) that passed boundary checks.
    """
    if explicit_files is not None:
        collected: list[str] = []
        for fp in explicit_files:
            try:
                resolved = Path(fp).resolve()
                if resolved.is_relative_to(scan_path) and resolved.is_file():
                    collected.append(str(resolved))
                else:
                    logger.debug("Skipping file outside scan boundary: %s", fp)
            except (OSError, ValueError):
                logger.debug("Could not resolve path: %s", fp)
        return sorted(collected)

    collected = []
    for root, dirs, filenames in os.walk(scan_path, followlinks=False):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for fname in filenames:
            filepath = os.path.join(root, fname)
            try:
                resolved = Path(filepath).resolve()
                if not resolved.is_relative_to(scan_path):
                    logger.warning("Symlink escape detected, skipping: %s", filepath)
                    continue
            except (OSError, ValueError) as exc:
                logger.warning("Path resolution error, skipping %s: %s", filepath, exc)
                continue

            # Accept files with recognized code extensions or no extension
            # (e.g. Dockerfile, Makefile)
            ext = resolved.suffix.lower()
            if ext in _CODE_EXTENSIONS or ext == "":
                collected.append(str(resolved))
    return sorted(collected)


# ---------------------------------------------------------------------------
# Pattern-based content scanning
# ---------------------------------------------------------------------------


def _scan_file_with_patterns(
    filepath: str,
    categories: list[str] | None,
    registry: dict[str, list[SecurityPattern]],
) -> list[Any]:
    """Scan a single file against pattern registry categories.

    Args:
        filepath: Absolute path to the file to scan.
        categories: Categories to scan (None = all).
        registry: The PATTERN_REGISTRY dict.

    Returns:
        List of SecurityFinding objects for matches found.
    """
    # Lazy import to avoid circular import (scanner.py is imported by __init__.py
    # before SecurityFinding is fully available in the zerg.security namespace)
    from zerg.security import SecurityFinding

    ext = Path(filepath).suffix.lower()
    findings: list[SecurityFinding] = []

    try:
        content = Path(filepath).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings

    lines = content.split("\n")
    cats_to_scan = categories if categories is not None else list(registry.keys())

    for cat_name in cats_to_scan:
        patterns = registry.get(cat_name, [])
        for pattern in patterns:
            # Skip if pattern is extension-specific and file doesn't match
            if pattern.file_extensions is not None and ext not in pattern.file_extensions:
                continue

            # The "sensitive_files" category matches against file paths, not content
            if cat_name == "sensitive_files":
                if pattern.regex.search(filepath):
                    findings.append(
                        SecurityFinding(
                            category=pattern.category,
                            severity=pattern.severity,
                            file=filepath,
                            line=0,
                            message=pattern.message,
                            cwe=pattern.cwe,
                            remediation=pattern.remediation,
                            pattern_name=pattern.name,
                        )
                    )
                continue

            # Content-based scanning: check each line
            for line_num, line in enumerate(lines, start=1):
                if pattern.regex.search(line):
                    # Mask sensitive content in the message
                    masked_line = line.strip()[:80]
                    findings.append(
                        SecurityFinding(
                            category=pattern.category,
                            severity=pattern.severity,
                            file=filepath,
                            line=line_num,
                            message=f"{pattern.message} [{masked_line}]",
                            cwe=pattern.cwe,
                            remediation=pattern.remediation,
                            pattern_name=pattern.name,
                        )
                    )

    return findings


# ---------------------------------------------------------------------------
# Git history scanning
# ---------------------------------------------------------------------------

# Secret patterns used for git history scanning — pulled from the
# secret_detection category of PATTERN_REGISTRY at call time.


def _scan_git_history(
    scan_path: Path,
    depth: int,
    secret_patterns: list[SecurityPattern],
) -> list[Any]:
    """Scan recent git commit diffs for secret patterns.

    Uses ``git log --diff-filter=A -p`` to inspect added lines in the
    last *depth* commits.

    Args:
        scan_path: Root directory of the git repository.
        depth: Number of commits to scan.
        secret_patterns: Patterns from the secret_detection category.

    Returns:
        List of SecurityFinding objects for any secrets found in history.
    """
    from zerg.security import SecurityFinding

    findings: list[SecurityFinding] = []

    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--diff-filter=A",
                "-p",
                "--no-color",
                "-n",
                str(depth),
            ],
            capture_output=True,
            text=True,
            cwd=str(scan_path),
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.warning("Git history scan failed: %s", exc)
        return findings

    if result.returncode != 0:
        logger.debug("git log returned non-zero exit code: %d", result.returncode)
        return findings

    current_file = "<unknown>"
    for line in result.stdout.split("\n"):
        # Track which file the diff belongs to
        if line.startswith("+++ b/"):
            current_file = line[6:]
            continue

        # Only inspect added lines (starting with "+", not "+++")
        if not line.startswith("+") or line.startswith("+++"):
            continue

        added_content = line[1:]  # strip leading "+"
        for pattern in secret_patterns:
            if pattern.regex.search(added_content):
                masked = added_content.strip()[:80]
                findings.append(
                    SecurityFinding(
                        category="git_history",
                        severity=pattern.severity,
                        file=current_file,
                        line=0,
                        message=f"Secret found in git history: {pattern.message} [{masked}]",
                        cwe=pattern.cwe,
                        remediation=(
                            f"{pattern.remediation}. Consider using git-filter-repo to purge secrets from history."
                        ),
                        pattern_name=f"git_history_{pattern.name}",
                    )
                )

    return findings


# ---------------------------------------------------------------------------
# Primary scan API
# ---------------------------------------------------------------------------


def run_security_scan(
    path: str | Path = ".",
    categories: list[str] | None = None,
    files: list[str] | None = None,
    git_history_depth: int = 100,
) -> Any:
    """Run a comprehensive security scan on the specified path.

    Iterates all pattern categories from :data:`PATTERN_REGISTRY`, runs
    CVE dependency scanning via :func:`~zerg.security.cve.scan_dependencies`,
    and scans recent git history for leaked secrets.

    Args:
        path: Root directory to scan.
        categories: Restrict scan to these category names. ``None`` scans all.
        files: Explicit file list to scan. ``None`` discovers files from *path*.
        git_history_depth: Number of git commits to scan for secrets (default 100).

    Returns:
        A :class:`~zerg.security.SecurityResult` with structured findings.
    """
    # Lazy imports to avoid circular dependency (scanner.py is imported by
    # __init__.py before SecurityFinding / SecurityResult are available)
    from zerg.security import SecurityFinding, SecurityResult
    from zerg.security.cve import scan_dependencies

    start = time.time()
    scan_path = Path(path).resolve()
    all_findings: list[SecurityFinding] = []

    # 1. Collect files
    collected_files = _collect_files(scan_path, explicit_files=files)

    # Determine which categories to scan
    cats_to_scan: list[str] = (
        [c for c in categories if c in PATTERN_REGISTRY] if categories is not None else list(PATTERN_REGISTRY.keys())
    )

    # 2. Pattern scan — iterate files and apply registry patterns
    for filepath in collected_files:
        file_findings = _scan_file_with_patterns(filepath, cats_to_scan, PATTERN_REGISTRY)
        all_findings.extend(file_findings)

    # 3. CVE / dependency scan
    cve_category = "cve"
    run_cve = categories is None or cve_category in categories
    if run_cve:
        try:
            cve_findings = scan_dependencies(scan_path)
            all_findings.extend(cve_findings)
        except Exception as exc:  # noqa: BLE001
            logger.warning("CVE dependency scan failed: %s", exc)
        if cve_category not in cats_to_scan:
            cats_to_scan.append(cve_category)

    # 4. Git history scan (secret patterns only)
    git_category = "git_history"
    run_git = categories is None or git_category in categories
    if run_git:
        secret_patterns = PATTERN_REGISTRY.get("secret_detection", [])
        git_findings = _scan_git_history(scan_path, git_history_depth, secret_patterns)
        all_findings.extend(git_findings)
        if git_category not in cats_to_scan:
            cats_to_scan.append(git_category)

    # 5. Existing utility checks (coexist with pattern scan)
    #    These produce legacy-format output but we convert to SecurityFinding
    non_ascii = check_for_non_ascii_filenames(collected_files)
    for fp in non_ascii:
        all_findings.append(
            SecurityFinding(
                category="filename_hygiene",
                severity="low",
                file=fp,
                line=0,
                message="Non-ASCII characters in filename",
                cwe=None,
                remediation="Rename the file using only ASCII characters",
                pattern_name="non_ascii_filename",
            )
        )

    large = get_large_files(collected_files)
    for fp, size_mb in large:
        all_findings.append(
            SecurityFinding(
                category="file_size",
                severity="medium",
                file=fp,
                line=0,
                message=f"File exceeds size limit: {size_mb} MB",
                cwe=None,
                remediation="Consider using Git LFS for large files or exclude from repository",
                pattern_name="large_file",
            )
        )

    # 6. Assemble result
    elapsed = time.time() - start
    severity_counts: dict[str, int] = {}
    for f in all_findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

    has_critical_or_high = severity_counts.get("critical", 0) + severity_counts.get("high", 0) > 0

    return SecurityResult(
        findings=all_findings,
        categories_scanned=sorted(cats_to_scan),
        files_scanned=len(collected_files),
        scan_duration_seconds=round(elapsed, 3),
        passed=not has_critical_or_high,
        summary=severity_counts,
    )
