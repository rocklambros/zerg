"""Dependency CVE scanning with osv.dev API and heuristic fallback.

Scans project dependency files for known vulnerabilities:
- requirements.txt (Python/pip)
- package.json (Node.js/npm)
- Cargo.toml (Rust/cargo)
- go.mod (Go)

Strategy: query osv.dev API first (5s timeout), fall back to
heuristic checks (unpinned versions, missing lockfiles) on failure.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from collections.abc import Callable  # noqa: F401 (used in type annotation)
from dataclasses import dataclass
from pathlib import Path
from typing import Any  # noqa: F401 (used in type annotation)

from zerg.security import SecurityFinding

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ecosystem configuration
# ---------------------------------------------------------------------------

_LOCKFILE_COMPANIONS: dict[str, list[str]] = {
    "requirements.txt": [
        "requirements.lock",
        "poetry.lock",
        "Pipfile.lock",
    ],
    "package.json": [
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
    ],
    "Cargo.toml": [
        "Cargo.lock",
    ],
    "go.mod": [
        "go.sum",
    ],
}

OSV_API_URL = "https://api.osv.dev/v1/querybatch"
OSV_TIMEOUT_SECONDS = 5


# ---------------------------------------------------------------------------
# Parsed dependency representation
# ---------------------------------------------------------------------------


@dataclass
class _Dependency:
    """A single parsed dependency from a manifest file."""

    name: str
    version: str | None  # None means unpinned / unresolvable
    ecosystem: str  # osv.dev ecosystem identifier
    source_file: str  # relative path to the manifest
    line: int  # 1-based line number in manifest


# ---------------------------------------------------------------------------
# Dependency parsers
# ---------------------------------------------------------------------------

# requirements.txt: name==1.0.0, name>=1.0.0, name~=1.0, name
_REQ_LINE_RE = re.compile(
    r"""
    ^(?P<name>[A-Za-z0-9][\w.\-]*)   # package name
    (?:\[.*?\])?                       # optional extras  [security]
    \s*
    (?:(?P<op>==|>=|<=|~=|!=|>|<|===)\s*(?P<ver>[^\s;,#]+))?  # version spec
    """,
    re.VERBOSE,
)


def _parse_requirements_txt(path: Path) -> list[_Dependency]:
    """Parse a requirements.txt file into dependencies."""
    deps: list[_Dependency] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return deps

    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()
        # Skip blanks, comments, flags (-r, --index-url, etc.)
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        m = _REQ_LINE_RE.match(line)
        if not m:
            continue
        name = m.group("name")
        op = m.group("op")
        ver = m.group("ver")
        # Only == gives an exact pinned version suitable for CVE lookup
        pinned_version = ver if op == "==" else None
        deps.append(
            _Dependency(
                name=name,
                version=pinned_version,
                ecosystem="PyPI",
                source_file=str(path),
                line=lineno,
            )
        )
    return deps


def _parse_package_json(path: Path) -> list[_Dependency]:
    """Parse a package.json file into dependencies."""
    deps: list[_Dependency] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return deps

    for section in ("dependencies", "devDependencies"):
        entries: dict[str, str] = data.get(section, {})
        if not isinstance(entries, dict):
            continue
        for name, version_spec in entries.items():
            # Extract exact version: strip ^, ~, >= prefixes
            cleaned = re.sub(r"^[\^~>=<]*\s*", "", version_spec)
            # Consider it pinned only if it looks like a semver
            pinned = cleaned if re.match(r"^\d+\.\d+", cleaned) else None
            # If original spec had range operators, still pass cleaned for lookup
            # but flag as imprecise
            deps.append(
                _Dependency(
                    name=name,
                    version=pinned,
                    ecosystem="npm",
                    source_file=str(path),
                    line=0,  # JSON doesn't have meaningful line numbers
                )
            )
    return deps


# Cargo.toml [dependencies] patterns
_CARGO_DEP_RE = re.compile(r'^(?P<name>[\w-]+)\s*=\s*"(?P<ver>[^"]+)"', re.MULTILINE)
_CARGO_DEP_TABLE_RE = re.compile(
    r'^(?P<name>[\w-]+)\s*=\s*\{.*?version\s*=\s*"(?P<ver>[^"]+)"',
    re.MULTILINE,
)


def _parse_cargo_toml(path: Path) -> list[_Dependency]:
    """Parse a Cargo.toml file into dependencies."""
    deps: list[_Dependency] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return deps

    lines = text.splitlines()
    in_deps = False
    for lineno, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        # Track section headers
        if stripped.startswith("["):
            in_deps = stripped in (
                "[dependencies]",
                "[dev-dependencies]",
                "[build-dependencies]",
            )
            continue
        if not in_deps or not stripped or stripped.startswith("#"):
            continue

        # Match: name = "version"
        m = _CARGO_DEP_RE.match(stripped)
        if not m:
            # Match: name = { version = "...", ... }
            m = _CARGO_DEP_TABLE_RE.match(stripped)
        if m:
            name = m.group("name")
            ver = m.group("ver")
            # Cargo uses semver; exact pin only if no range operators
            pinned = ver if ver and not any(c in ver for c in "^~><=*") else None
            deps.append(
                _Dependency(
                    name=name,
                    version=pinned,
                    ecosystem="crates.io",
                    source_file=str(path),
                    line=lineno,
                )
            )
    return deps


# go.mod require block patterns
_GO_REQUIRE_SINGLE_RE = re.compile(r"^require\s+(?P<mod>\S+)\s+(?P<ver>\S+)", re.MULTILINE)


def _parse_go_mod(path: Path) -> list[_Dependency]:
    """Parse a go.mod file into dependencies."""
    deps: list[_Dependency] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return deps

    lines = text.splitlines()
    in_require_block = False

    for lineno, raw in enumerate(lines, start=1):
        stripped = raw.strip()

        # Single-line require
        m = _GO_REQUIRE_SINGLE_RE.match(stripped)
        if m:
            deps.append(
                _Dependency(
                    name=m.group("mod"),
                    version=m.group("ver"),
                    ecosystem="Go",
                    source_file=str(path),
                    line=lineno,
                )
            )
            continue

        # Block require
        if stripped == "require (" or stripped.startswith("require("):
            in_require_block = True
            continue
        if in_require_block:
            if stripped == ")":
                in_require_block = False
                continue
            if stripped.startswith("//") or not stripped:
                continue
            parts = stripped.split()
            if len(parts) >= 2:
                mod_path = parts[0]
                version = parts[1]
                # Skip indirect comment, but still record the dep
                deps.append(
                    _Dependency(
                        name=mod_path,
                        version=version,
                        ecosystem="Go",
                        source_file=str(path),
                        line=lineno,
                    )
                )
    return deps


# ---------------------------------------------------------------------------
# Parser dispatch
# ---------------------------------------------------------------------------

_PARSERS: dict[str, Callable[[Path], list[_Dependency]]] = {
    "requirements.txt": _parse_requirements_txt,
    "package.json": _parse_package_json,
    "Cargo.toml": _parse_cargo_toml,
    "go.mod": _parse_go_mod,
}


def _collect_dependencies(project_path: Path) -> list[_Dependency]:
    """Collect all dependencies from supported manifest files."""
    all_deps: list[_Dependency] = []
    for filename, parser in _PARSERS.items():
        manifest = project_path / filename
        if manifest.is_file():
            all_deps.extend(parser(manifest))
    return all_deps


# ---------------------------------------------------------------------------
# osv.dev API query
# ---------------------------------------------------------------------------


def _query_osv(deps: list[_Dependency]) -> list[SecurityFinding]:
    """Query osv.dev for known vulnerabilities in the given dependencies.

    Sends a single batch request. Returns findings for any reported CVEs.
    Raises on network / API failure so caller can fall back to heuristics.
    """
    if not deps:
        return []

    # Build query — only include deps with a resolved version
    queries: list[dict[str, Any]] = []
    dep_index: list[_Dependency] = []  # parallel list for result mapping
    for dep in deps:
        if dep.version:
            queries.append(
                {
                    "package": {
                        "name": dep.name,
                        "ecosystem": dep.ecosystem,
                    },
                    "version": dep.version,
                }
            )
            dep_index.append(dep)

    if not queries:
        return []

    payload = json.dumps({"queries": queries}).encode("utf-8")
    req = urllib.request.Request(
        OSV_API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=OSV_TIMEOUT_SECONDS) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    findings: list[SecurityFinding] = []
    results = body.get("results", [])

    for idx, result in enumerate(results):
        if idx >= len(dep_index):
            break
        vulns = result.get("vulns", [])
        dep = dep_index[idx]
        for vuln in vulns:
            vuln_id = vuln.get("id", "UNKNOWN")
            summary = vuln.get("summary", "Known vulnerability")
            aliases = vuln.get("aliases", [])
            # Prefer CVE alias if available
            cve_id = next((a for a in aliases if a.startswith("CVE-")), None)
            severity_str = _osv_severity(vuln)
            findings.append(
                SecurityFinding(
                    category="cve",
                    severity=severity_str,
                    file=dep.source_file,
                    line=dep.line,
                    message=(f"{dep.name}=={dep.version}: {vuln_id} — {summary}"),
                    cwe=None,
                    remediation=f"Update {dep.name} to a patched version. See https://osv.dev/vulnerability/{vuln_id}",
                    pattern_name=cve_id or vuln_id,
                )
            )
    return findings


def _osv_severity(vuln: dict[str, Any]) -> str:
    """Extract a severity string from an OSV vulnerability record."""
    # OSV severity is in database_specific or severity array
    severity_list = vuln.get("severity", [])
    for sev in severity_list:
        score_str = sev.get("score", "")
        # CVSS score ranges
        try:
            score = float(score_str)
            if score >= 9.0:
                return "critical"
            if score >= 7.0:
                return "high"
            if score >= 4.0:
                return "medium"
            return "low"
        except (ValueError, TypeError):
            pass  # Non-numeric severity; skip
    # Default based on whether there's a CVE
    aliases = vuln.get("aliases", [])
    if any(a.startswith("CVE-") for a in aliases):
        return "high"
    return "medium"


# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------


def _heuristic_scan(project_path: Path, deps: list[_Dependency]) -> list[SecurityFinding]:
    """Produce findings via heuristics when the API is unavailable.

    Checks:
    1. Unpinned dependency versions (>=, *, ~=, ^, or no version)
    2. Missing lockfiles
    3. Known-bad version ranges (small hardcoded database)
    """
    findings: list[SecurityFinding] = []

    # --- 1. Unpinned versions ---
    for dep in deps:
        if dep.version is None:
            findings.append(
                SecurityFinding(
                    category="cve",
                    severity="medium",
                    file=dep.source_file,
                    line=dep.line,
                    message=(
                        f"Unpinned dependency: {dep.name} "
                        f"(ecosystem: {dep.ecosystem}). "
                        "Cannot verify against known CVEs."
                    ),
                    cwe="CWE-1104",
                    remediation=(
                        f"Pin {dep.name} to an exact version "
                        f"(e.g., {dep.name}==X.Y.Z) and verify "
                        "it is free of known vulnerabilities."
                    ),
                    pattern_name="unpinned_dependency",
                )
            )

    # --- 2. Missing lockfiles ---
    for manifest, companions in _LOCKFILE_COMPANIONS.items():
        manifest_path = project_path / manifest
        if not manifest_path.is_file():
            continue
        has_lockfile = any((project_path / lock).is_file() for lock in companions)
        if not has_lockfile:
            findings.append(
                SecurityFinding(
                    category="lockfile_integrity",
                    severity="medium",
                    file=str(manifest_path),
                    line=0,
                    message=(f"No lockfile found for {manifest}. Expected one of: {', '.join(companions)}"),
                    cwe="CWE-829",
                    remediation=(
                        "Generate a lockfile to pin transitive dependency versions and enable reproducible builds."
                    ),
                    pattern_name="missing_lockfile",
                )
            )

    # --- 3. Known-bad version ranges ---
    findings.extend(_check_known_bad_versions(deps))

    return findings


# Small database of packages with well-known critical vulnerabilities.
# Format: (ecosystem, name, bad_version_prefix, vuln_id, description)
_KNOWN_BAD_VERSIONS: list[tuple[str, str, str, str, str]] = [
    (
        "PyPI",
        "urllib3",
        "1.25.",
        "CVE-2021-33503",
        "ReDoS via URL authority parsing",
    ),
    (
        "PyPI",
        "requests",
        "2.3.",
        "CVE-2014-1829",
        "Redirect to different host leaks credentials",
    ),
    (
        "npm",
        "lodash",
        "4.17.1",
        "CVE-2021-23337",
        "Prototype pollution in lodash",
    ),
    (
        "npm",
        "minimist",
        "0.",
        "CVE-2020-7598",
        "Prototype pollution in minimist",
    ),
    (
        "npm",
        "node-fetch",
        "2.",
        "CVE-2022-0235",
        "Exposure of sensitive information in node-fetch",
    ),
    (
        "crates.io",
        "hyper",
        "0.13.",
        "CVE-2021-32714",
        "Integer overflow in header parsing",
    ),
    (
        "Go",
        "golang.org/x/text",
        "v0.3.0",
        "CVE-2020-14040",
        "Infinite loop in encoding",
    ),
]


def _check_known_bad_versions(
    deps: list[_Dependency],
) -> list[SecurityFinding]:
    """Check deps against a small hardcoded database of known-bad versions."""
    findings: list[SecurityFinding] = []
    for dep in deps:
        if dep.version is None:
            continue
        for eco, name, bad_prefix, vuln_id, description in _KNOWN_BAD_VERSIONS:
            if dep.ecosystem == eco and dep.name.lower() == name.lower() and dep.version.startswith(bad_prefix):
                findings.append(
                    SecurityFinding(
                        category="cve",
                        severity="high",
                        file=dep.source_file,
                        line=dep.line,
                        message=(f"{dep.name}=={dep.version}: {vuln_id} — {description} (heuristic match)"),
                        cwe=None,
                        remediation=(
                            f"Update {dep.name} to the latest patched "
                            f"version. See https://osv.dev/vulnerability/{vuln_id}"
                        ),
                        pattern_name=vuln_id,
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_dependencies(project_path: Path) -> list[SecurityFinding]:
    """Scan project dependencies for known CVEs and supply-chain risks.

    Args:
        project_path: Root directory of the project to scan.

    Returns:
        List of SecurityFinding instances. Empty list means no issues found.

    Strategy:
        1. Parse dependency manifests (requirements.txt, package.json,
           Cargo.toml, go.mod).
        2. Query osv.dev batch API with a 5-second timeout.
        3. On API failure, fall back to heuristic checks (unpinned versions,
           missing lockfiles, known-bad version ranges).
    """
    project_path = Path(project_path).resolve()
    deps = _collect_dependencies(project_path)

    # Always run heuristic checks for lockfile and unpinned-version findings.
    heuristic_findings = _heuristic_scan(project_path, deps)

    # Attempt API-based CVE lookup for deps that have pinned versions.
    api_findings: list[SecurityFinding] = []
    try:
        api_findings = _query_osv(deps)
        logger.debug("osv.dev returned %d vulnerability findings", len(api_findings))
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        OSError,
        json.JSONDecodeError,
        KeyError,
        ValueError,
    ) as exc:
        logger.warning(
            "osv.dev API query failed (%s); using heuristic fallback only",
            exc,
        )
        # Heuristic known-bad checks are already in heuristic_findings,
        # so we just skip API results gracefully.

    # Merge: API findings + heuristic findings, deduplicate by pattern_name+file
    seen: set[tuple[str, str]] = set()
    merged: list[SecurityFinding] = []
    for finding in api_findings + heuristic_findings:
        key = (finding.pattern_name, finding.file)
        if key not in seen:
            seen.add(key)
            merged.append(finding)

    return merged
