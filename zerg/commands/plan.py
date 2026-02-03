"""ZERG plan command - capture feature requirements."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from zerg.logging import get_logger

console = Console()
logger = get_logger("plan")


@click.command()
@click.argument("feature", required=False)
@click.option("--template", "-t", default="default", help="Template: default, minimal, detailed")
@click.option("--interactive/--no-interactive", default=True, help="Interactive mode")
@click.option("--from-issue", help="Import from GitHub issue URL")
@click.option("--socratic", "-s", is_flag=True, help="Use structured 3-round discovery mode")
@click.option("--rounds", default=3, type=int, help="Number of rounds for socratic mode (max: 5)")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def plan(
    ctx: click.Context,
    feature: str | None,
    template: str,
    interactive: bool,
    from_issue: str | None,
    socratic: bool,
    rounds: int,
    verbose: bool,
) -> None:
    """Capture feature requirements.

    Creates .gsd/specs/{feature}/requirements.md with comprehensive
    requirements documentation.

    Examples:

        zerg plan user-auth

        zerg plan user-auth --socratic

        zerg plan --from-issue https://github.com/org/repo/issues/123

        zerg plan user-auth --template minimal --no-interactive
    """
    try:
        console.print("\n[bold cyan]ZERG Plan[/bold cyan]\n")

        # Validate feature name
        if not feature and not from_issue:
            if interactive:
                feature = Prompt.ask("Feature name")
            else:
                console.print("[red]Error:[/red] Feature name required")
                console.print("Usage: zerg plan <feature-name>")
                raise SystemExit(1)

        # Handle GitHub issue import
        if from_issue:
            feature = import_from_github_issue(from_issue)
            if not feature:
                raise SystemExit(1)

        # Sanitize feature name
        assert feature is not None  # guaranteed by above logic
        feature = sanitize_feature_name(feature)
        console.print(f"Feature: [cyan]{feature}[/cyan]\n")

        # Create spec directory
        spec_dir = Path(f".gsd/specs/{feature}")
        spec_dir.mkdir(parents=True, exist_ok=True)

        # Set current feature
        current_feature_file = Path(".gsd/.current-feature")
        current_feature_file.write_text(feature)

        # Write start timestamp
        from datetime import datetime

        started_file = spec_dir / ".started"
        started_file.write_text(datetime.now(UTC).isoformat())

        # Check for existing requirements
        requirements_path = spec_dir / "requirements.md"
        if requirements_path.exists():
            console.print(f"[yellow]Found existing requirements at {requirements_path}[/yellow]")
            if interactive and not Confirm.ask("Overwrite?", default=False):
                console.print("[dim]Keeping existing requirements[/dim]")
                return

        if not interactive:
            # Non-interactive mode: create template
            create_requirements_template(spec_dir, feature, template)
            console.print(f"\n[green]✓[/green] Created {requirements_path}")
            console.print("\nEdit the requirements file, then run [cyan]zerg design[/cyan]")
            return

        # Interactive mode
        if socratic:
            # Socratic 3-round discovery
            rounds = min(rounds, 5)
            requirements = run_socratic_discovery(feature, rounds)
        else:
            # Standard requirements elicitation
            requirements = run_interactive_discovery(feature, template)

        # Write requirements
        write_requirements(spec_dir, feature, requirements)

        console.print(f"\n[green]✓[/green] Requirements saved to {requirements_path}")
        console.print("\nNext steps:")
        console.print("  1. Review and edit requirements.md")
        console.print("  2. Change Status to [cyan]APPROVED[/cyan] when ready")
        console.print("  3. Run [cyan]zerg design[/cyan] to generate task graph")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise SystemExit(130) from None
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        if verbose:
            console.print_exception()
        raise SystemExit(1) from e


def sanitize_feature_name(name: str) -> str:
    """Sanitize feature name to lowercase with hyphens.

    Args:
        name: Raw feature name

    Returns:
        Sanitized feature name
    """
    import re

    # Lowercase, replace spaces with hyphens, remove invalid chars
    name = name.lower().replace(" ", "-")
    name = re.sub(r"[^a-z0-9-]", "", name)
    return name


def import_from_github_issue(url: str) -> str | None:
    """Import requirements from a GitHub issue.

    Args:
        url: GitHub issue URL

    Returns:
        Feature name or None on error
    """
    import subprocess

    console.print(f"[dim]Importing from {url}[/dim]")

    try:
        # Use gh CLI to fetch issue
        result = subprocess.run(
            ["gh", "issue", "view", url, "--json", "title,body,labels"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            console.print(f"[red]Error:[/red] Failed to fetch issue: {result.stderr}")
            return None

        import json

        data = json.loads(result.stdout)

        # Extract feature name from title
        title = data.get("title", "")
        feature = sanitize_feature_name(title)

        console.print(f"[green]✓[/green] Imported issue: {title}")
        return feature

    except FileNotFoundError:
        console.print("[red]Error:[/red] GitHub CLI (gh) not installed")
        return None
    except subprocess.TimeoutExpired:
        console.print("[red]Error:[/red] Timed out fetching issue")
        return None
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        return None


def create_requirements_template(spec_dir: Path, feature: str, template: str) -> None:
    """Create requirements template file.

    Args:
        spec_dir: Spec directory path
        feature: Feature name
        template: Template type (default, minimal, detailed)
    """
    from datetime import datetime

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")

    if template == "minimal":
        content = f"""# Feature Requirements: {feature}

## Metadata
- **Feature**: {feature}
- **Status**: DRAFT
- **Created**: {timestamp}

## Problem Statement

_What problem does this feature solve?_

## Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-001 | | Must |

## Acceptance Criteria

- [ ] Criterion 1

## Out of Scope

- _Item 1_
"""
    elif template == "detailed":
        content = get_detailed_template(feature, timestamp)
    else:
        content = get_default_template(feature, timestamp)

    requirements_path = spec_dir / "requirements.md"
    requirements_path.write_text(content)


def get_default_template(feature: str, timestamp: str) -> str:
    """Get default requirements template."""
    return f"""# Feature Requirements: {feature}

## Metadata
- **Feature**: {feature}
- **Status**: DRAFT
- **Created**: {timestamp}
- **Author**: ZERG Plan

---

## 1. Problem Statement

### 1.1 Background
_Context and background information_

### 1.2 Problem
_Clear statement of the problem being solved_

### 1.3 Impact
_What happens without this feature_

---

## 2. Users

### 2.1 Primary Users
_Who will use this feature most_

### 2.2 User Stories
- As a [user], I want to [action] so that [benefit]

---

## 3. Functional Requirements

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| FR-001 | | Must | |

### 3.1 Inputs
_What the feature accepts_

### 3.2 Outputs
_What the feature produces_

---

## 4. Non-Functional Requirements

### 4.1 Performance
- Response time: _target_
- Throughput: _target_

### 4.2 Security
- Authentication: _requirements_
- Authorization: _requirements_

---

## 5. Scope

### 5.1 In Scope
- _item_

### 5.2 Out of Scope
- _item_ (reason: _why_)

### 5.3 Assumptions
- _assumption_

---

## 6. Dependencies

| Dependency | Type | Status |
|------------|------|--------|
| | Required | |

---

## 7. Acceptance Criteria

### 7.1 Definition of Done
- [ ] All functional requirements implemented
- [ ] All tests passing
- [ ] Code reviewed
- [ ] Documentation updated

### 7.2 Test Scenarios

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| TC-001 | | | | |

---

## 8. Open Questions

| ID | Question | Status |
|----|----------|--------|
| Q-001 | | Open |

---

## 9. Approval

| Role | Status |
|------|--------|
| Product | PENDING |
| Engineering | PENDING |
"""


def get_detailed_template(feature: str, timestamp: str) -> str:
    """Get detailed requirements template."""
    # Same as default but with more sections
    base = get_default_template(feature, timestamp)

    additional = """
---

## 10. Technical Constraints

### 10.1 Technology Stack
- _technology requirements_

### 10.2 Integration Points
- _external systems_

### 10.3 Data Requirements
- _data models and schemas_

---

## 11. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| | Low/Med/High | Low/Med/High | |

---

## 12. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| | | |
"""
    return base + additional


def run_socratic_discovery(feature: str, rounds: int) -> dict[str, Any]:
    """Run Socratic 3-round discovery process.

    Args:
        feature: Feature name
        rounds: Number of rounds (1-5)

    Returns:
        Requirements dictionary
    """
    requirements: dict[str, Any] = {
        "feature": feature,
        "transcript": [],
        "problem_space": {},
        "solution_space": {},
        "implementation_space": {},
    }

    # Round 1: Problem Space
    if rounds >= 1:
        console.print(Panel("[bold]ROUND 1: PROBLEM SPACE[/bold]", style="cyan"))
        problem_questions = [
            "What specific problem does this feature solve?",
            "Who are the primary users affected by this problem?",
            "What happens today without this feature?",
            "Why is solving this problem important now?",
            "How will we know when the problem is solved?",
        ]
        requirements["problem_space"] = ask_questions(problem_questions, "Problem")
        requirements["transcript"].append(("Problem Space", requirements["problem_space"]))

    # Round 2: Solution Space
    if rounds >= 2:
        console.print(Panel("[bold]ROUND 2: SOLUTION SPACE[/bold]", style="cyan"))
        solution_questions = [
            "What does the ideal solution look like?",
            "What constraints must we work within?",
            "What are the non-negotiable requirements?",
            "What similar solutions exist? What can we learn?",
            "What should this solution explicitly NOT do?",
        ]
        requirements["solution_space"] = ask_questions(solution_questions, "Solution")
        requirements["transcript"].append(("Solution Space", requirements["solution_space"]))

    # Round 3: Implementation Space
    if rounds >= 3:
        console.print(Panel("[bold]ROUND 3: IMPLEMENTATION SPACE[/bold]", style="cyan"))
        impl_questions = [
            "What is the minimum viable version?",
            "What can be deferred to future iterations?",
            "What are the biggest technical risks?",
            "How should we verify this works correctly?",
            "What documentation or training is needed?",
        ]
        impl_answers = ask_questions(impl_questions, "Implementation")
        requirements["implementation_space"] = impl_answers
        requirements["transcript"].append(("Implementation Space", impl_answers))

    return requirements


def run_interactive_discovery(feature: str, template: str) -> dict[str, Any]:
    """Run standard interactive discovery.

    Args:
        feature: Feature name
        template: Template type

    Returns:
        Requirements dictionary
    """
    requirements = {"feature": feature}

    console.print("[bold]Requirements Elicitation[/bold]\n")

    # Core questions
    requirements["problem"] = Prompt.ask("What problem does this feature solve?")
    requirements["users"] = Prompt.ask("Who are the primary users?")
    requirements["inputs"] = Prompt.ask("What inputs does the feature accept?")
    requirements["outputs"] = Prompt.ask("What outputs does it produce?")
    requirements["out_of_scope"] = Prompt.ask("What is explicitly out of scope?")
    requirements["acceptance"] = Prompt.ask("How will we know it's complete?")

    return requirements


def ask_questions(questions: list[str], category: str) -> dict[str, str]:
    """Ask a series of questions and collect answers.

    Args:
        questions: List of questions
        category: Category name for display

    Returns:
        Dictionary of question -> answer
    """
    answers = {}
    for i, question in enumerate(questions, 1):
        console.print(f"\n[dim]{category} Q{i}:[/dim] {question}")
        answer = Prompt.ask(">")
        answers[question] = answer
    return answers


def write_requirements(spec_dir: Path, feature: str, requirements: dict[str, Any]) -> None:
    """Write requirements to markdown file.

    Args:
        spec_dir: Spec directory
        feature: Feature name
        requirements: Requirements dictionary
    """
    from datetime import datetime

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")

    # Check if socratic mode was used
    if "transcript" in requirements:
        content = format_socratic_requirements(feature, timestamp, requirements)
    else:
        content = format_standard_requirements(feature, timestamp, requirements)

    requirements_path = spec_dir / "requirements.md"
    requirements_path.write_text(content)


def format_socratic_requirements(feature: str, timestamp: str, req: dict[str, Any]) -> str:
    """Format socratic discovery results as requirements.md."""
    content = f"""# Feature Requirements: {feature}

## Metadata
- **Feature**: {feature}
- **Status**: DRAFT
- **Created**: {timestamp}
- **Method**: Socratic Discovery

---

## Discovery Transcript

"""
    # Add transcript
    for round_name, answers in req.get("transcript", []):
        content += f"### {round_name}\n\n"
        for q, a in answers.items():
            content += f"**Q:** {q}\n**A:** {a}\n\n"

    # Synthesize from problem space
    problem = req.get("problem_space", {})
    content += """---

## 1. Problem Statement

### 1.1 Problem
"""
    content += next(iter(problem.values()), "_To be defined_") + "\n"

    # Add solution constraints
    solution = req.get("solution_space", {})
    content += """
---

## 2. Solution Constraints

"""
    for q, a in solution.items():
        content += f"- **{q}**: {a}\n"

    # Add implementation notes
    impl = req.get("implementation_space", {})
    content += """
---

## 3. Implementation Notes

"""
    for q, a in impl.items():
        content += f"- **{q}**: {a}\n"

    content += """
---

## 4. Acceptance Criteria

- [ ] Core problem addressed
- [ ] All constraints satisfied
- [ ] Tests passing
- [ ] Documentation complete

---

## 5. Approval

| Role | Status |
|------|--------|
| Product | PENDING |
| Engineering | PENDING |
"""

    return content


def format_standard_requirements(feature: str, timestamp: str, req: dict[str, Any]) -> str:
    """Format standard discovery results as requirements.md."""
    return f"""# Feature Requirements: {feature}

## Metadata
- **Feature**: {feature}
- **Status**: DRAFT
- **Created**: {timestamp}
- **Author**: ZERG Plan

---

## 1. Problem Statement

{req.get("problem", "_To be defined_")}

---

## 2. Users

{req.get("users", "_To be defined_")}

---

## 3. Functional Requirements

### 3.1 Inputs
{req.get("inputs", "_To be defined_")}

### 3.2 Outputs
{req.get("outputs", "_To be defined_")}

---

## 4. Scope

### 4.1 Out of Scope
{req.get("out_of_scope", "_To be defined_")}

---

## 5. Acceptance Criteria

{req.get("acceptance", "_To be defined_")}

- [ ] All requirements implemented
- [ ] Tests passing
- [ ] Documentation complete

---

## 6. Approval

| Role | Status |
|------|--------|
| Product | PENDING |
| Engineering | PENDING |
"""
