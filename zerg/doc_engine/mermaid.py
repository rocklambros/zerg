"""Mermaid diagram syntax generation for ZERG documentation."""

from __future__ import annotations

import os
import re


def _sanitize_id(name: str) -> str:
    """Convert an arbitrary string into a safe Mermaid node identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def _strip_common_prefix(names: list[str]) -> dict[str, str]:
    """Map fully-qualified module names to short forms by stripping the shared prefix.

    Returns a mapping of ``{original: short}``.
    """
    if not names:
        return {}

    parts_list = [n.split(".") for n in names]
    prefix_len = 0
    for segments in zip(*parts_list):
        if len(set(segments)) == 1:
            prefix_len += 1
        else:
            break

    return {name: ".".join(parts[prefix_len:]) or parts[-1] for name, parts in zip(names, parts_list)}


class MermaidGenerator:
    """Produces Mermaid diagram syntax strings for various diagram types."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def dependency_graph(
        self,
        modules: dict[str, list[str]],
        title: str = "",
    ) -> str:
        """Generate a ``graph TD`` dependency diagram.

        Parameters
        ----------
        modules:
            Adjacency list mapping each module name to the list of modules
            it imports / depends on.
        title:
            Optional title rendered as a comment at the top of the diagram.

        Returns
        -------
        str
            Mermaid source wrapped in a ``mermaid`` code fence.
        """
        all_names = sorted({name for name in modules} | {dep for deps in modules.values() for dep in deps})
        short = _strip_common_prefix(all_names)

        lines: list[str] = ["graph TD"]

        if title:
            lines.insert(0, f"%% {title}")

        # Group nodes by first segment of the short name (package grouping)
        packages: dict[str, list[str]] = {}
        for full_name in all_names:
            sname = short[full_name]
            pkg = sname.split(".")[0] if "." in sname else ""
            packages.setdefault(pkg, []).append(full_name)

        # Emit subgraphs for multi-member packages
        for pkg, members in sorted(packages.items()):
            if pkg and len(members) > 1:
                lines.append(f"    subgraph {_sanitize_id(pkg)}[{pkg}]")
                for m in members:
                    sid = _sanitize_id(short[m])
                    lines.append(f'        {sid}["{short[m]}"]')
                lines.append("    end")
            else:
                for m in members:
                    sid = _sanitize_id(short[m])
                    lines.append(f'    {sid}["{short[m]}"]')

        # Emit edges
        for source, deps in sorted(modules.items()):
            src_id = _sanitize_id(short[source])
            for dep in sorted(deps):
                if dep in short:
                    lines.append(f"    {src_id} --> {_sanitize_id(short[dep])}")

        return _wrap(lines)

    def workflow(self, steps: list[dict[str, str]]) -> str:
        """Generate a ``sequenceDiagram`` from actor/action/target steps.

        Parameters
        ----------
        steps:
            List of dicts each containing ``actor``, ``action``, and
            ``target`` keys describing one interaction.

        Returns
        -------
        str
            Mermaid source wrapped in a ``mermaid`` code fence.
        """
        lines: list[str] = ["sequenceDiagram"]
        for step in steps:
            actor = step.get("actor", "Unknown")
            action = step.get("action", "")
            target = step.get("target", "Unknown")
            lines.append(f"    {actor}->>+{target}: {action}")
        return _wrap(lines)

    def state_machine(
        self,
        states: list[str],
        transitions: list[tuple[str, str, str]],
    ) -> str:
        """Generate a ``stateDiagram-v2``.

        Parameters
        ----------
        states:
            List of state names.
        transitions:
            List of ``(from_state, to_state, label)`` tuples.

        Returns
        -------
        str
            Mermaid source wrapped in a ``mermaid`` code fence.
        """
        lines: list[str] = ["stateDiagram-v2"]
        for state in states:
            sid = _sanitize_id(state)
            lines.append(f"    {sid} : {state}")
        for src, dst, label in transitions:
            lines.append(f"    {_sanitize_id(src)} --> {_sanitize_id(dst)}: {label}")
        return _wrap(lines)

    def data_flow(
        self,
        nodes: list[dict[str, str]],
        edges: list[dict[str, str]],
    ) -> str:
        """Generate a ``flowchart LR`` data-flow diagram.

        Parameters
        ----------
        nodes:
            List of dicts with ``id``, ``label``, and ``type`` keys.
            Supported types: ``process`` (rectangle), ``store``
            (cylinder), ``external`` (stadium/rounded).
        edges:
            List of dicts with ``from``, ``to``, and optional ``label``
            keys.

        Returns
        -------
        str
            Mermaid source wrapped in a ``mermaid`` code fence.
        """
        lines: list[str] = ["flowchart LR"]

        shape_map: dict[str, tuple[str, str]] = {
            "process": ("[", "]"),
            "store": ("[(", ")]"),
            "external": ("([", "])"),
        }

        for node in nodes:
            nid = _sanitize_id(node["id"])
            label = node.get("label", node["id"])
            ntype = node.get("type", "process")
            left, right = shape_map.get(ntype, ("[", "]"))
            lines.append(f'    {nid}{left}"{label}"{right}')

        for edge in edges:
            src = _sanitize_id(edge["from"])
            dst = _sanitize_id(edge["to"])
            label = edge.get("label", "")
            if label:
                lines.append(f"    {src} -->|{label}| {dst}")
            else:
                lines.append(f"    {src} --> {dst}")

        return _wrap(lines)

    def class_diagram(self, classes: list[dict[str, object]]) -> str:
        """Generate a ``classDiagram``.

        Parameters
        ----------
        classes:
            List of dicts with ``name``, ``methods`` (list[str]),
            ``attributes`` (list[str]), and ``bases`` (list[str]) keys.

        Returns
        -------
        str
            Mermaid source wrapped in a ``mermaid`` code fence.
        """
        lines: list[str] = ["classDiagram"]

        all_names: set[str] = set()
        for cls in classes:
            all_names.add(str(cls["name"]))
            for base in cls.get("bases", []) or []:
                all_names.add(str(base))

        for cls in classes:
            name = str(cls["name"])
            lines.append(f"    class {name} {{")
            for attr in cls.get("attributes", []) or []:
                lines.append(f"        {attr}")
            for method in cls.get("methods", []) or []:
                lines.append(f"        {method}()")
            lines.append("    }")

        # Inheritance edges
        for cls in classes:
            name = str(cls["name"])
            for base in cls.get("bases", []) or []:
                lines.append(f"    {base} <|-- {name}")

        return _wrap(lines)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _wrap(lines: list[str]) -> str:
    """Wrap diagram lines in a Mermaid code fence."""
    body = os.linesep.join(lines)
    return f"```mermaid\n{body}\n```"
