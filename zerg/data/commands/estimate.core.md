<!-- SPLIT: core, parent: estimate.md -->
# ZERG Estimate

Full-lifecycle effort estimation with PERT confidence intervals, post-execution comparison, historical calibration, and API cost projection.

## Flags

- `--pre`: Force pre-execution estimation mode
- `--post`: Force post-execution comparison mode
- `--calibrate`: Show historical accuracy and compute bias factors
- `--workers N`: Worker count for wall-clock projection (default: from config or 5)
- `--format text|json|md`: Output format (default: text)
- `--verbose`: Show per-task breakdown (not just level summaries)
- `--history`: Show past estimates for this feature
- `--no-calibration`: Skip auto-applying calibration bias

## Pre-Flight

```bash
FEATURE="$ARGUMENTS"

# Extract feature name (strip flags)
FEATURE=$(echo "$FEATURE" | sed 's/--[a-z-]*\s*[^ ]*//' | xargs)

# If no explicit feature, detect from state
if [ -z "$FEATURE" ]; then
  FEATURE=$(cat .gsd/.current-feature 2>/dev/null)
fi

if [ -z "$FEATURE" ]; then
  echo "ERROR: No feature specified or detected"
  exit 1
fi

SPEC_DIR=".gsd/specs/$FEATURE"
STATE_FILE=".zerg/state/$FEATURE.json"
ESTIMATE_DIR=".gsd/estimates"
ESTIMATE_FILE="$ESTIMATE_DIR/$FEATURE-estimate.json"
CALIBRATION_FILE="$ESTIMATE_DIR/calibration.json"
```

## Auto-Detection

If no explicit `--pre`, `--post`, or `--calibrate` flag:

1. If `$STATE_FILE` does not exist or has zero completed tasks → **pre** mode
2. If `$STATE_FILE` exists and has completed tasks → **post** mode
3. `--calibrate` flag always overrides to calibration mode
4. Explicit `--pre`/`--post` overrides auto-detection

## Workflow

Execute the detected mode. See `estimate.details.md` for full formulas, templates, and schemas.

### Mode 1: Pre-Execution Estimate

1. **Load task graph** from `$SPEC_DIR/task-graph.json`
2. **Compute risk scores** via `python -c` using `RiskScorer` from `zerg/risk_scoring.py`
3. **PERT per task**: derive optimistic/most-likely/pessimistic from `estimate_minutes` + risk score
4. **Confidence intervals**: P50, P80, P95 per task, level, and feature total
5. **Level wall-clock**: simulate worker assignment per level (max worker load)
6. **Cost projection**: via `python -c` using `.zerg/estimate.py` `ResourceEstimator`
7. **Apply calibration**: if `$CALIBRATION_FILE` exists and `--no-calibration` not set
8. **Save snapshot** to `$ESTIMATE_FILE`
9. **Output** summary with tables

### Mode 2: Post-Execution Comparison

1. **Load pre-estimate** from `$ESTIMATE_FILE` (if exists)
2. **Load actuals** from `$STATE_FILE` and metrics
3. **Compute accuracy** per task, level, and total: `actual / estimated`
4. **Flag outliers** with >50% deviation
5. **Append post snapshot** to `$ESTIMATE_FILE`
6. **Output** comparison tables

### Mode 3: Calibration

1. **Scan** all `$ESTIMATE_DIR/*-estimate.json` files with both pre and post snapshots
2. **Compute bias**: `mean(actual/estimated)` across features
3. **Per-grade breakdown**: group tasks by risk grade, average accuracy
4. **MAE**: mean absolute error as percentage
5. **Save** to `$CALIBRATION_FILE` for auto-apply
6. **Output** calibration report with recommendations

## Task Tracking

On invocation, create a Claude Code Task:

Call TaskCreate:
  - subject: "[Estimate] {mode} estimate for {feature}"
  - description: "Running {mode} estimation for {feature}. Workers: {N}. Format: {format}."
  - activeForm: "Estimating {feature}"

Immediately call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "in_progress"

On completion, call TaskUpdate:
  - taskId: (the Claude Task ID)
  - status: "completed"

## Completion Criteria

- Pre mode: estimate saved to `.gsd/estimates/{feature}-estimate.json`, tables output
- Post mode: comparison tables output, post snapshot appended to history
- Calibrate mode: `calibration.json` updated, bias report output

## Exit Codes

- 0: Estimation completed successfully
- 1: Missing task-graph or state data
- 2: Configuration error

## Help

When `--help` is passed in `$ARGUMENTS`, display usage and exit:

```
/zerg:estimate — Full-lifecycle effort estimation with PERT confidence intervals, post-execution comparison, historical calibration, and API cost projection.

Flags:
  --pre             Force pre-execution estimation mode
  --post            Force post-execution comparison mode
  --calibrate       Show historical accuracy and compute bias factors
  --workers N       Worker count for wall-clock projection (default: from config or 5)
  --format text|json|md
                    Output format (default: text)
  --verbose         Show per-task breakdown (not just level summaries)
  --history         Show past estimates for this feature
  --no-calibration  Skip auto-applying calibration bias
  --help            Show this help message
```

<!-- SPLIT: core=estimate.core.md details=estimate.details.md -->
