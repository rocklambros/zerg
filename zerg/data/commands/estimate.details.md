<!-- SPLIT: details, parent: estimate.md -->
# ZERG Estimate — Details

Reference material for `/zerg:estimate`. See `estimate.core.md` for workflow and flags.

---

## PERT Formula with Risk Weighting

### Per-Task PERT Derivation

For each task `t` with `estimate_minutes` (base) and `risk_score` (0.0–1.0 from RiskScorer):

```
optimistic  = base * (1 - 0.3 * (1 - risk_score))
most_likely = base
pessimistic = base * (1 + 0.5 + risk_score * 1.0)

pert_mean   = (optimistic + 4 * most_likely + pessimistic) / 6
pert_stddev = (pessimistic - optimistic) / 6
```

**Risk weighting logic**:
- Low risk (A, score < 0.25): tight bounds — optimistic is close to base, pessimistic mild
- High risk (D, score > 0.75): wide bounds — pessimistic can be 2.25x base

### Confidence Intervals

```
P50 = pert_mean                          (50% confidence)
P80 = pert_mean + 0.84 * pert_stddev    (80% confidence)
P95 = pert_mean + 1.65 * pert_stddev    (95% confidence)
```

### Risk Grade Mapping

| Grade | Score Range | Optimistic Factor | Pessimistic Factor |
|-------|------------|-------------------|-------------------|
| A | 0.00–0.24 | 0.78–0.70x | 1.50–1.74x |
| B | 0.25–0.49 | 0.85–0.78x | 1.75–1.99x |
| C | 0.50–0.74 | 0.92–0.85x | 2.00–2.24x |
| D | 0.75–1.00 | 1.00–0.92x | 2.25–2.50x |

---

## Python Inline Computation Snippets

### Risk Scoring

```bash
python -c "
import sys, json
sys.path.insert(0, '.')
from zerg.risk_scoring import RiskScorer

with open('$SPEC_DIR/task-graph.json') as f:
    graph = json.load(f)

scorer = RiskScorer()
report = scorer.score(graph)

for task_id, risk in report.task_risks.items():
    print(json.dumps({'id': task_id, 'score': round(risk.score, 3), 'grade': risk.grade}))
print('---')
print(json.dumps({'overall_grade': report.grade, 'critical_path': report.critical_path}))
"
```

### Cost Projection

```bash
python -c "
import sys, json
sys.path.insert(0, '.')
sys.path.insert(0, '.zerg')
from estimate import TaskGraphAnalyzer, ResourceEstimator, EstimateConfig

analyzer = TaskGraphAnalyzer()
analysis = analyzer.analyze('$SPEC_DIR/task-graph.json' if '$SPEC_DIR' else None)

config = EstimateConfig(workers=$WORKERS, include_cost=True)
resources = ResourceEstimator().estimate(analysis, config)

print(json.dumps(resources.to_dict()))
"
```

### WhatIf Simulation (Level Wall-Clock)

```bash
python -c "
import sys, json
sys.path.insert(0, '.')
from zerg.whatif import WhatIfEngine

with open('$SPEC_DIR/task-graph.json') as f:
    graph = json.load(f)

engine = WhatIfEngine(graph)
report = engine.compare_workers([$WORKERS])

for scenario in report.scenarios:
    print(json.dumps({
        'workers': scenario.workers,
        'wall_time': scenario.wall_time,
        'efficiency': round(scenario.efficiency, 2),
        'per_level': scenario.per_level_wall
    }))
"
```

---

## Pre-Execution Output Template

```
ESTIMATION: {feature}
═════════════════════════════════════════════════════

Task Analysis:
  Tasks: {total} across {levels} levels
  Critical path: {cp_tasks} tasks ({cp_minutes}m sequential)
  Max parallelization: {max_parallel}

Time Estimates ({workers} workers):
  Confidence │ Wall-Clock │ Sequential │ Sessions
  ───────────┼────────────┼────────────┼─────────
  P50        │   {w50}m   │   {s50}m   │   {ses50}
  P80        │   {w80}m   │   {s80}m   │   {ses80}
  P95        │   {w95}m   │   {s95}m   │   {ses95}

Cost Projection:
  Tokens: ~{tokens}K │ Cost: ~${cost}

Level Breakdown:
  Level │ Tasks │ P50  │ P80  │ Critical │ Risk
  ──────┼───────┼──────┼──────┼──────────┼─────
  L{n}  │  {t}  │ {m}m │ {m}m │  {y/n}   │  {g}
  ...

{if calibration applied}
Calibration: {factor}x applied (from {N} prior features)
{endif}

Risk Grade: {grade} ({description})
```

### Per-Task Verbose Output (--verbose)

```
Per-Task Breakdown:
  Task ID    │ Title              │ Base │ P50  │ P80  │ P95  │ Risk │ Critical
  ───────────┼────────────────────┼──────┼──────┼──────┼──────┼──────┼─────────
  {id}       │ {title:18}         │ {b}m │ {m}m │ {m}m │ {m}m │  {g} │  {y/n}
  ...
```

---

## Post-Execution Comparison Template

```
ESTIMATE vs ACTUAL: {feature}
═════════════════════════════════════════════════════

Workers: {N}
Duration: estimated {est}m → actual {act}m ({accuracy}%)

Level Comparison:
  Level │ Est (P80) │ Actual │ Accuracy │ Notes
  ──────┼───────────┼────────┼──────────┼──────
  L{n}  │   {est}m  │ {act}m │  {pct}%  │ {note}
  ...
  Total │   {est}m  │ {act}m │  {pct}%  │

Outliers (>50% deviation):
  {task_id} "{title}" — Est: {est}m, Actual: {act}m ({ratio}x) [Risk: {grade}]
  ...

{if no outliers}
No significant outliers. Estimates well calibrated.
{endif}
```

---

## Calibration Algorithm

### Step 1: Collect History

Scan all `.gsd/estimates/*-estimate.json` files. Filter to those with both `"type": "pre"` and `"type": "post"` snapshots.

### Step 2: Compute Bias Factor

```
For each feature f with pre and post snapshots:
  ratio_f = post.totals.actual_wall_minutes / pre.totals.wall_p80

overall_bias = mean(ratio_f for all f)
```

### Step 3: Per-Risk-Grade Bias

```
For each task across all features:
  group by risk_grade (A, B, C, D)
  per_grade_bias[grade] = mean(actual_minutes / pert_p80) for tasks in grade
```

### Step 4: Mean Absolute Error

```
mae = mean(abs(actual - estimated) / estimated * 100) across all tasks
```

### Step 5: Save Calibration

Write to `.gsd/estimates/calibration.json`.

### Calibration Output Template

```
CALIBRATION REPORT
═════════════════════════════════════════════════════

Features analyzed: {N}
Overall bias: {factor}x (estimates are {pct}% too {optimistic|pessimistic})
MAE: {mae}%

By Risk Grade:
  Grade │ Bias   │ Interpretation
  ──────┼────────┼───────────────
  A     │ {f}x   │ {description}
  B     │ {f}x   │ {description}
  C     │ {f}x   │ {description}
  D     │ {f}x   │ {description}

Trend: {improving|worsening|stable} (last {N} features)

Recommendations:
  - Apply {factor}x multiplier to future estimates
  - Apply {factor}x to risk grade {grade} tasks specifically
  {if bias > 1.3}
  - Consider breaking high-risk tasks into smaller units
  {endif}

Saved to: .gsd/estimates/calibration.json
```

---

## History JSON Schema

File: `.gsd/estimates/{feature}-estimate.json`

```json
{
  "schema": "zerg-estimate-v1",
  "feature": "{feature-name}",
  "snapshots": [
    {
      "type": "pre",
      "timestamp": "2026-01-31T10:00:00Z",
      "workers": 5,
      "tasks": [
        {
          "id": "TASK-L1-001",
          "title": "Create types",
          "level": 1,
          "estimate_minutes": 15,
          "risk_score": 0.35,
          "risk_grade": "B",
          "pert_optimistic": 12.2,
          "pert_most_likely": 15,
          "pert_pessimistic": 23.3,
          "pert_mean": 15.6,
          "pert_stddev": 1.85,
          "pert_p50": 15.6,
          "pert_p80": 17.2,
          "pert_p95": 18.7
        }
      ],
      "levels": [
        {
          "level": 1,
          "task_count": 3,
          "wall_p50": 15,
          "wall_p80": 18,
          "wall_p95": 21,
          "risk_grade": "B"
        }
      ],
      "totals": {
        "sequential_minutes": 90,
        "wall_p50": 32,
        "wall_p80": 38,
        "wall_p95": 45,
        "critical_path_minutes": 40,
        "calibration_factor": 1.0,
        "tokens": 240000,
        "cost_usd": 3.60
      }
    },
    {
      "type": "post",
      "timestamp": "2026-01-31T12:30:00Z",
      "tasks": [
        {
          "id": "TASK-L1-001",
          "actual_minutes": 18,
          "accuracy_ratio": 1.16
        }
      ],
      "levels": [
        {
          "level": 1,
          "actual_wall_minutes": 20,
          "accuracy_ratio": 1.11
        }
      ],
      "totals": {
        "actual_wall_minutes": 35,
        "overall_accuracy": 0.92
      }
    }
  ]
}
```

## Calibration JSON Schema

File: `.gsd/estimates/calibration.json`

```json
{
  "schema": "zerg-calibration-v1",
  "bias_factor": 1.15,
  "per_grade": {
    "A": 1.05,
    "B": 1.12,
    "C": 1.45,
    "D": 1.80
  },
  "mae_percent": 24,
  "features_analyzed": 3,
  "trend": "improving",
  "updated": "2026-01-31T12:45:00Z"
}
```

---

## Edge Cases

### No task-graph.json
- Pre mode: error with "Run /zerg:design first to generate task graph"
- Post/Calibrate: proceed without pre-estimate, compare against raw state data

### No state file (post mode)
- Error with "No execution data found. Run /zerg:rush first"

### No history files (calibrate mode)
- Warning: "No completed features with both pre and post estimates found"
- Suggest: "Run /zerg:estimate --pre before rush, then --post after, to build history"

### estimate_minutes missing from tasks
- Default to 15 minutes per task (same as risk_scoring.py default)

### < 3 features in calibration
- Warning: "Only {N} features in calibration — bias factor may be unreliable"
- Still compute and save, but flag confidence as "low"

### python -c import failure
- Fallback: Claude computes PERT manually using the formulas above
- Log warning: "Could not import zerg modules — using manual computation"

### Calibration factor > 2.0 or < 0.5
- Warning: "Extreme calibration factor ({factor}x) — estimates may be systematically wrong"
- Suggest reviewing task breakdown methodology

---

## Task Tracking (Details)

The TaskCreate subject uses mode-specific prefixes:

| Mode | Subject |
|------|---------|
| Pre | `[Estimate] Pre-execution estimate for {feature}` |
| Post | `[Estimate] Post-execution comparison for {feature}` |
| Calibrate | `[Estimate] Calibration report ({N} features)` |

TaskUpdate on completion should include a summary in the description:
- Pre: "Estimated {wall_p80}m wall-clock ({workers} workers). Risk grade: {grade}."
- Post: "Accuracy: {pct}%. {outliers} outliers detected."
- Calibrate: "Bias: {factor}x. MAE: {mae}%. {N} features analyzed."
