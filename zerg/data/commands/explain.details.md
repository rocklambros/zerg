<!-- SPLIT: details, parent: explain.md -->
# ZERG Explain — Details

Reference material for `/zerg:explain`. See `explain.core.md` for workflow and flags.

---

## Python Inline Extraction Snippets

### Symbol Extraction
```bash
python -c "
import sys, json; sys.path.insert(0, '.')
from pathlib import Path
from zerg.doc_engine.extractor import SymbolExtractor
s = SymbolExtractor().extract(Path('$TARGET_FILE'))
print(json.dumps({
  'module_docstring': s.module_docstring,
  'classes': [{'name': c.name, 'lineno': c.lineno, 'bases': c.bases,
    'methods': [{'name': m.name, 'args': m.args, 'return_type': m.return_type,
      'docstring': m.docstring, 'decorators': m.decorators, 'is_async': m.is_async} for m in c.methods],
    'docstring': c.docstring, 'decorators': c.decorators} for c in s.classes],
  'functions': [{'name': f.name, 'args': f.args, 'return_type': f.return_type,
    'docstring': f.docstring, 'decorators': f.decorators, 'is_async': f.is_async} for f in s.functions],
  'imports': [{'module': i.module, 'names': i.names, 'is_from': i.is_from} for i in s.imports],
  'constants': s.constants, 'type_aliases': s.type_aliases
}, indent=2))
"
```

### Component Detection
```bash
python -c "
import sys; sys.path.insert(0, '.')
from pathlib import Path
from zerg.doc_engine.detector import ComponentDetector
print(ComponentDetector().detect(Path('$TARGET_FILE')).value)
"
```

### Dependency Graph
```bash
python -c "
import sys, json; sys.path.insert(0, '.')
from pathlib import Path
from zerg.doc_engine.dependencies import DependencyMapper
g = DependencyMapper.build(Path('$PROJECT_ROOT'), package='$PACKAGE')
chain = g.get_dependency_chain('$MODULE_NAME')
importers = g.get_importers('$MODULE_NAME')
direct = g.get_imports('$MODULE_NAME')
print(json.dumps({'direct_imports': direct, 'transitive_imports': chain, 'imported_by': importers}))
"
```

### Mermaid Dependency Diagram
```bash
python -c "
import sys; sys.path.insert(0, '.')
from pathlib import Path
from zerg.doc_engine.mermaid import MermaidGenerator
from zerg.doc_engine.dependencies import DependencyMapper
g = DependencyMapper.build(Path('$PROJECT_ROOT'), package='$PACKAGE')
adj = DependencyMapper.to_adjacency_list(g)
target = '$MODULE_NAME'
filtered = {k: [v2 for v2 in v if v2 == target or k == target] for k, v in adj.items() if k == target or target in v}
filtered = {k: v for k, v in filtered.items() if v or k == target}
print(MermaidGenerator().dependency_graph(filtered, title='$TARGET Dependencies'))
"
```

### Class Diagram (OOP targets)
```bash
python -c "
import sys; sys.path.insert(0, '.')
from pathlib import Path
from zerg.doc_engine.extractor import SymbolExtractor
from zerg.doc_engine.mermaid import MermaidGenerator
s = SymbolExtractor().extract(Path('$TARGET_FILE'))
classes = [{'name': c.name, 'methods': [m.name for m in c.methods],
  'attributes': [], 'bases': c.bases} for c in s.classes]
print(MermaidGenerator().class_diagram(classes))
"
```

---

## Layer Output Templates

### Layer 1: Summary
```
─────────────────────────────────────────
 LAYER 1: SUMMARY
─────────────────────────────────────────
{One paragraph from module_docstring or synthesized from symbols.}

Responsibilities:
  - {from public functions/classes}

Public API:
  - {function_name}({args}) -> {return_type}
  - {ClassName}: {one-line purpose}

Component Type: {module|command|config|types|api}
Stats: {N} classes, {N} functions, {N} imports, {N} constants
```
**Sources**: ComponentDetector.detect(), SymbolExtractor.extract()

### Layer 2: Logic Flow
```
─────────────────────────────────────────
 LAYER 2: LOGIC FLOW
─────────────────────────────────────────
Execution Path:
  1. {Entry point}  2. {Validation}  3. {Core}  4. {Output}

Control Flow:
  - {Branch}: {condition} -> {A} | {B}
  - {Loop}: iterates {collection} doing {action}
  - {Error}: {exception} -> {recovery}

Data Transformations:
  {input} -> [{step}] -> {intermediate} -> [{step}] -> {output}

{Mermaid diagram: dependency_graph or data_flow}
```
**Sources**: SymbolExtractor, DependencyMapper, MermaidGenerator, source reading

### Layer 3: Implementation Details
```
─────────────────────────────────────────
 LAYER 3: IMPLEMENTATION DETAILS
─────────────────────────────────────────
Key Data Structures:
  - {ClassName}: {purpose, key attributes}

Algorithms:
  - {name}: {what, complexity}

Type Contracts:
  - {func}({param}: {type}) -> {return}
    Raises: {exception} when {condition}

Internal Helpers:
  - _{name}: {purpose, callers}

Performance: Time: {O(n)}  Space: {chars}  I/O: {ops}
```
**Sources**: SymbolExtractor (args, return_type, is_async), source reading

### Layer 4: Design Decisions
```
─────────────────────────────────────────
 LAYER 4: DESIGN DECISIONS
─────────────────────────────────────────
Patterns:
  - {Pattern}: {evidence} -- Why: {rationale}

Abstractions:
  - {ABC/Protocol}: abstracts {what}, impls: {classes}

Trade-offs:
  - {choice}: {evidence}

Dependency Direction:
  - Imports: {from get_imports()}
  - Importers: {from get_importers()}
  - Coupling: {tight/loose}
```
**Sources**: SymbolExtractor (classes/bases), DependencyMapper (chain + importers), source reading

---

## Full Output Template
```
EXPLANATION: {target}
=======================================================
Scope: {function|file|module|system}  |  Type: {component_type}

{Layer 1}
{Layer 2}
{Layer 3}
{Layer 4}

=======================================================
{if --save} Saved to: claudedocs/explanations/{target_name}.md
```

---

## --save File Format

Write to `claudedocs/explanations/{target_name}.md`:

```markdown
# Explanation: {target}

**Generated**: {timestamp}  **Scope**: {scope}  **Component Type**: {type}

---
## Layer 1: Summary
{content}
## Layer 2: Logic Flow
{content}
{mermaid in fenced code block}
## Layer 3: Implementation Details
{content}
## Layer 4: Design Decisions
{content}
---
*Generated by `/zerg:explain`*
```

### Save Path Resolution

| Target | Save Path |
|--------|-----------|
| `zerg/launcher.py` | `claudedocs/explanations/launcher.md` |
| `zerg/launcher.py:spawn` | `claudedocs/explanations/launcher-spawn.md` |
| `zerg/doc_engine/` | `claudedocs/explanations/doc_engine.md` |
| `zerg.orchestrator` | `claudedocs/explanations/orchestrator.md` |

---

## Scope-Specific Behavior

| Scope | Extraction | Layer 2 Focus | Layer 3 Focus | Layer 4 Focus |
|-------|-----------|---------------|---------------|---------------|
| function | Single function from SymbolExtractor | Internal logic step-by-step | Args, return, exceptions | Caller context via get_importers |
| file | Full symbol table | Module init + workflows | All public symbols | Module patterns + coupling |
| module | ComponentDetector.detect_all(dir) | Inter-file data flow | Package API surface | Package architecture |
| system | Multiple packages | Cross-package flow (Mermaid) | System-wide API | Architectural patterns |

---

## Edge Cases

### Non-Python Files
- Skip `python -c` extraction (SymbolExtractor is Python-only)
- Fall back to Read tool on source directly
- Log: "Non-Python target -- using source code analysis only"
- Still generate all 4 layers from Claude's analysis

### doc_engine Import Failure
- Log: "doc_engine not available -- using direct source analysis"
- Fall back to Read tool; generate all layers from native analysis
- Skip Mermaid diagrams or build manually

### Empty/Minimal Files (< 5 lines, no functions/classes)
- Layer 1: brief summary only
- Layer 2: "Minimal file -- no significant logic flow"
- Layer 3: list constants/imports only
- Layer 4: "No significant design patterns"

### Binary/Non-Text Files
- Error: "Cannot explain binary files" -- exit code 1

### Target Not Found
- Error: "Target '{target}' not found. Check path and try again."
- Suggest closest match if similar file exists -- exit code 1

---

## Task Tracking (Details)

TaskCreate subject uses scope-specific format:

| Scope | Subject |
|-------|---------|
| function | `[Explain] Function explanation for {file}:{function}` |
| file | `[Explain] File explanation for {file}` |
| module | `[Explain] Module explanation for {directory}` |
| system | `[Explain] System explanation for {target}` |

TaskUpdate on completion summary:
- "Generated 4-layer explanation for {target}. {N} classes, {N} functions analyzed. {Saved to path | Terminal only}."
