"""ZERG orchestrator - thin coordination engine delegating to extracted components."""

import asyncio
import contextlib
import os
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from zerg.assign import WorkerAssignment
from zerg.backpressure import BackpressureController
from zerg.capability_resolver import ResolvedCapabilities
from zerg.circuit_breaker import CircuitBreaker
from zerg.config import ZergConfig
from zerg.constants import (
    LOGS_TASKS_DIR,
    LOGS_WORKERS_DIR,
    GateResult,
    PluginHookEvent,
    TaskStatus,
    WorkerStatus,
)
from zerg.containers import ContainerManager
from zerg.context_plugin import ContextEngineeringPlugin
from zerg.event_emitter import EventEmitter
from zerg.gates import GateRunner
from zerg.launcher_configurator import LauncherConfigurator
from zerg.launcher_types import LauncherConfig, LauncherType
from zerg.launchers import (
    ContainerLauncher,
    SubprocessLauncher,
    WorkerLauncher,
    get_plugin_launcher,
)
from zerg.level_coordinator import GatePipeline, LevelCoordinator
from zerg.levels import LevelController
from zerg.log_writer import StructuredLogWriter
from zerg.logging import get_logger, setup_structured_logging
from zerg.loops import LoopController
from zerg.merge import MergeCoordinator, MergeFlowResult
from zerg.metrics import MetricsCollector
from zerg.modes import BehavioralMode, ModeContext, ModeDetector
from zerg.parser import TaskParser
from zerg.plugin_config import ContextEngineeringConfig
from zerg.plugins import LifecycleEvent, PluginRegistry
from zerg.ports import PortAllocator
from zerg.state import StateManager
from zerg.state_sync_service import StateSyncService
from zerg.task_retry_manager import TaskRetryManager
from zerg.task_sync import TaskSyncBridge
from zerg.types import WorkerState
from zerg.worker_manager import WorkerManager
from zerg.worktree import WorktreeManager

logger = get_logger("orchestrator")


def _now() -> datetime:
    return datetime.now()


class Orchestrator:
    # fmt: off
    """Thin coordinator delegating to WorkerManager, LevelCoordinator, etc."""

    def __init__(
        self, feature: str, config: ZergConfig | None = None, repo_path: str | Path = ".",
        launcher_mode: str | None = None, capabilities: ResolvedCapabilities | None = None,
        skip_tests: bool = False,
    ) -> None:
        self.feature = feature
        self.config = config or ZergConfig.load()
        self.repo_path = Path(repo_path).resolve()
        self._launcher_mode = launcher_mode
        self._capabilities = capabilities
        self._skip_tests = skip_tests

        self._plugin_registry = PluginRegistry()
        if hasattr(self.config, "plugins") and self.config.plugins.enabled:
            with contextlib.suppress(Exception):
                self._plugin_registry.load_yaml_hooks([h.model_dump() for h in self.config.plugins.hooks])
                self._plugin_registry.load_entry_points()
        with contextlib.suppress(Exception):
            ctx_cfg = ContextEngineeringConfig()
            if hasattr(self.config, "plugins") and hasattr(self.config.plugins, "context_engineering"):
                ctx_cfg = self.config.plugins.context_engineering
            if ctx_cfg.enabled:
                self._plugin_registry.register_context_plugin(ContextEngineeringPlugin(ctx_cfg))

        self.state = StateManager(feature)
        self.event_emitter = EventEmitter(feature, state_dir=self.repo_path / ".zerg" / "state")
        self.levels = LevelController()
        self.parser = TaskParser()
        self.gates = GateRunner(self.config, plugin_registry=self._plugin_registry)
        self.worktrees = WorktreeManager(self.repo_path)
        self.containers = ContainerManager(self.config)
        self.ports = PortAllocator(range_start=self.config.ports.range_start, range_end=self.config.ports.range_end)
        self.assigner: WorkerAssignment | None = None
        self.merger = MergeCoordinator(feature, self.config, self.repo_path)
        tl_id = os.environ.get("CLAUDE_CODE_TASK_LIST_ID", feature)
        self.task_sync = TaskSyncBridge(feature, self.state, task_list_id=tl_id)
        self._launcher_config = LauncherConfigurator(self.config, self.repo_path, self._plugin_registry)
        self.launcher: WorkerLauncher = self._create_launcher(mode=launcher_mode)
        try:
            is_container = isinstance(self.launcher, ContainerLauncher)
        except TypeError:
            is_container = False
        if is_container:
            with contextlib.suppress(Exception):
                self._launcher_config._cleanup_orphan_containers()

        self._structured_writer: StructuredLogWriter | None = None
        try:
            (self.repo_path / LOGS_WORKERS_DIR).mkdir(parents=True, exist_ok=True)
            (self.repo_path / LOGS_TASKS_DIR).mkdir(parents=True, exist_ok=True)
            lc = self.config.logging
            self._structured_writer = setup_structured_logging(
                log_dir=self.repo_path / Path(lc.directory), worker_id="orchestrator",
                feature=feature, level=lc.level, max_size_mb=lc.max_log_size_mb,
            )
        except Exception:
            pass

        self._running = False
        self._paused = False
        self._workers: dict[int, WorkerState] = {}
        self._on_task_complete: list[Callable[[str], None]] = [
            lambda tid: self.event_emitter.emit("task_complete", {"task_id": tid})]
        self._on_level_complete: list[Callable[[int], None]] = [
            lambda lvl: self.event_emitter.emit("level_complete", {"level": lvl})]
        self._poll_interval = 15
        self._max_retry_attempts = self.config.workers.retry_attempts
        self._restart_counts: dict[int, int] = {}
        self._respawn_counts: dict[int, int] = {}
        self._target_worker_count: int = 0
        self._retry_manager = TaskRetryManager(
            config=self.config, state=self.state, levels=self.levels,
            repo_path=self.repo_path, structured_writer=self._structured_writer,
        )
        self._state_sync = StateSyncService(state=self.state, levels=self.levels)
        er = self.config.error_recovery
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=er.circuit_breaker.failure_threshold,
            cooldown_seconds=er.circuit_breaker.cooldown_seconds, enabled=er.circuit_breaker.enabled,
        )
        self._backpressure = BackpressureController(
            failure_rate_threshold=er.backpressure.failure_rate_threshold,
            window_size=er.backpressure.window_size, enabled=er.backpressure.enabled,
        )
        self._worker_manager = WorkerManager(
            feature=self.feature, config=self.config, state=self.state, levels=self.levels,
            parser=self.parser, launcher=self.launcher, worktrees=self.worktrees, ports=self.ports,
            assigner=self.assigner, plugin_registry=self._plugin_registry, workers=self._workers,
            on_task_complete=self._on_task_complete, on_task_failure=self._retry_manager.handle_task_failure,
            structured_writer=self._structured_writer, circuit_breaker=self._circuit_breaker,
            capabilities=self._capabilities,
        )
        self._level_coord = LevelCoordinator(
            feature=self.feature, config=self.config, state=self.state, levels=self.levels,
            parser=self.parser, merger=self.merger, task_sync=self.task_sync,
            plugin_registry=self._plugin_registry, workers=self._workers,
            on_level_complete_callbacks=self._on_level_complete, assigner=self.assigner,
            structured_writer=self._structured_writer, backpressure=self._backpressure,
        )

        self._loop_controller: LoopController | None = None
        if self._capabilities and self._capabilities.loop_enabled:
            lc = self.config.improvement_loops
            self._loop_controller = LoopController(
                max_iterations=self._capabilities.loop_iterations,
                convergence_threshold=lc.convergence_threshold, plateau_threshold=lc.plateau_threshold,
            )
        self._gate_pipeline: GatePipeline | None = None
        if self._capabilities and self._capabilities.gates_enabled:
            self._gate_pipeline = GatePipeline(
                gate_runner=self.gates, artifacts_dir=Path(self.config.verification.artifact_dir),
                staleness_threshold_seconds=self._capabilities.staleness_threshold,
            )
            self.merger._gate_pipeline = self._gate_pipeline
        self._mode_context: ModeContext | None = None
        if self._capabilities:
            try:
                me = BehavioralMode(self._capabilities.mode)
            except ValueError:
                me = BehavioralMode.PRECISION
            bm = self.config.behavioral_modes
            det = ModeDetector(auto_detect=bm.auto_detect, default_mode=me, log_transitions=bm.log_transitions)
            self._mode_context = det.detect(explicit_mode=me, depth_tier=self._capabilities.depth_tier)

    def _create_launcher(self, mode: str | None = None) -> WorkerLauncher:
        if mode and mode not in ("subprocess", "container", "auto"):
            pl = get_plugin_launcher(mode, self._plugin_registry)
            if pl is not None:
                return pl
            raise ValueError(f"Unsupported launcher mode: '{mode}'")
        if mode == "subprocess":
            lt = LauncherType.SUBPROCESS
        elif mode == "container":
            lt = LauncherType.CONTAINER
        else:
            lt = self._launcher_config._auto_detect_launcher_type()
        cfg = LauncherConfig(launcher_type=lt, timeout_seconds=self.config.workers.timeout_minutes * 60,
                             log_dir=Path(self.config.logging.directory))
        if lt == LauncherType.CONTAINER:
            launcher = ContainerLauncher(
                config=cfg, image_name=self._launcher_config._get_worker_image_name(),
                memory_limit=self.config.resources.container_memory_limit,
                cpu_limit=self.config.resources.container_cpu_limit,
            )
            if not launcher.ensure_network():
                if mode == "container":
                    raise RuntimeError("Container mode requested but Docker network creation failed.")
                return SubprocessLauncher(cfg)
            return launcher
        return SubprocessLauncher(cfg)

    def _check_container_health(self) -> None:
        pre = {wid: w.status for wid, w in self._workers.items()}
        self._launcher_config._check_container_health(self._workers, self.launcher)
        for wid, w in self._workers.items():
            if w.status == WorkerStatus.CRASHED and pre.get(wid) != WorkerStatus.CRASHED:
                self.state.set_worker_state(w)

    def _handle_task_failure(self, task_id: str, worker_id: int, error: str) -> bool:
        self.event_emitter.emit("task_fail", {"task_id": task_id, "worker_id": worker_id, "error": error})
        return self._retry_manager.handle_task_failure(task_id, worker_id, error)

    def _check_stale_tasks(self) -> None:
        timeout = getattr(self.config.workers, "task_stale_timeout_seconds", 600)
        with contextlib.suppress(AttributeError):
            stale = self._retry_manager.check_stale_tasks(timeout)
            if stale:
                self.state.append_event("stale_tasks_detected", {"task_ids": stale})

    def _handle_worker_crash(self, task_id: str, wid: int) -> None:
        self.state.set_task_status(task_id, TaskStatus.FAILED, worker_id=wid, error="Worker crashed")
        self.state.append_event(
            "task_crash_reassign",
            {"task_id": task_id, "worker_id": wid, "retry_count_incremented": False},
        )
        self.levels.reset_task(task_id)
        self.state.set_task_status(task_id, TaskStatus.PENDING)

    def _auto_respawn_workers(self, level: int, remaining: int) -> None:
        max_r = getattr(self.config.workers, "max_respawn_attempts", 5)
        if not getattr(self.config.workers, "auto_respawn", True):
            return
        spawned = 0
        for wid in range(min(remaining, self._target_worker_count or 1)):
            rc = self._respawn_counts.get(wid, 0)
            if rc >= max_r:
                continue
            with contextlib.suppress(Exception):
                self._respawn_counts[wid] = rc + 1
                self._worker_manager.spawn_worker(wid)
                spawned += 1
                self.state.append_event("worker_auto_respawn", {"worker_id": wid, "level": level})
        if spawned == 0 and remaining > 0:
            self.state.append_event("auto_respawn_exhausted", {"level": level})

    def _reassign_stranded_tasks(self) -> None:
        active = {int(k) for k, v in self.state._state.get("workers", {}).items()
                  if v.get("status") not in ("stopped", "crashed")}
        active |= {wid for wid, w in self._workers.items()
                    if w.status not in (WorkerStatus.STOPPED, WorkerStatus.CRASHED)}
        self._state_sync.reassign_stranded_tasks(active)

    def _start_level(self, level: int) -> None:
        self._level_coord.assigner = self.assigner
        self._level_coord.start_level(level)
        self.event_emitter.emit("level_start", {"level": level})

    def _on_level_complete_handler(self, level: int) -> bool:
        result = self._level_coord.handle_level_complete(level)
        self._paused = self._paused or self._level_coord.paused
        if result and self._loop_controller is not None:
            self._run_level_loop(level, merge_result=self._level_coord.last_merge_result)
        return result

    def _run_level_loop(self, level: int, merge_result: MergeFlowResult | None = None) -> None:
        vl = self._mode_context.mode.verification_level if self._mode_context else "full"
        if vl == "none":
            return
        req_only = vl == "minimal"
        def score(_it: int) -> float:
            try:
                if self._gate_pipeline:
                    gs = [g for g in self.config.quality_gates if not req_only or g.required]
                    res = self._gate_pipeline.run_gates_for_level(level=level, gates=gs)
                else:
                    _, res = self.gates.run_all_gates(feature=self.feature, level=level, required_only=req_only)
                return sum(1 for r in res if r.result == GateResult.PASS) / len(res) if res else 1.0
            except Exception:
                return 0.0

        gr = merge_result.gate_results if merge_result and merge_result.gate_results else None
        init = (sum(1 for r in gr if r.result == GateResult.PASS) / len(gr)) if gr else score(0)
        if init >= 1.0:
            return
        s = self._loop_controller.run(score, initial_score=init)
        self.state.append_event("loop_completed", {
            "level": level, "status": s.status.value,
            "best_score": s.best_score, "iterations": len(s.iterations),
        })

    def _pause_for_intervention(self, reason: str) -> None:
        self._level_coord.pause_for_intervention(reason)
        self._paused = True

    def _set_recoverable_error(self, error: str) -> None:
        self._level_coord.set_recoverable_error(error)
        self._paused = True

    def _prepare_start(self, task_graph_path: str | Path, worker_count: int) -> WorkerAssignment:
        self.parser.parse(task_graph_path)
        tasks = self.parser.get_all_tasks()
        self.levels.initialize(tasks)
        self.assigner = WorkerAssignment(worker_count)
        result = self.assigner.assign(tasks, self.feature)
        self.assigner.save_to_file(f".gsd/specs/{self.feature}/worker-assignments.json", self.feature)
        self._worker_manager.assigner = self._level_coord.assigner = self.assigner
        return result

    def _spawn_and_begin(self, worker_count: int, start_level: int | None) -> None:
        self._running = self._worker_manager.running = True
        self._target_worker_count = worker_count
        spawned = self._worker_manager.spawn_workers(worker_count)
        if spawned == 0:
            self.state.append_event("rush_failed", {
                "reason": "No workers spawned",
                "requested": worker_count, "mode": self._launcher_mode,
            })
            self.state.save()
            msg = f"All {worker_count} workers failed to spawn (mode={self._launcher_mode})."
            raise RuntimeError(msg)
        self._worker_manager.wait_for_initialization(timeout=600)
        eff = start_level or 1
        for prev in range(1, eff):
            if prev in self.levels._levels:
                lvl = self.levels._levels[prev]
                lvl.completed_tasks, lvl.failed_tasks, lvl.status = lvl.total_tasks, 0, "complete"
                for t in self.levels._tasks.values():
                    if t.get("level") == prev:
                        t["status"] = TaskStatus.COMPLETE.value
        self._start_level(eff)

    def start(
        self, task_graph_path: str | Path, worker_count: int = 5,
        start_level: int | None = None, dry_run: bool = False,
    ) -> None:
        assignments = self._prepare_start(task_graph_path, worker_count)
        self.state.load()
        self.state.save()
        self.state.append_event("rush_started", {"workers": worker_count, "total_tasks": self.parser.total_tasks})
        if dry_run:
            self._print_plan(assignments)
            return
        self._spawn_and_begin(worker_count, start_level)
        self._main_loop()

    def _do_stop(self, force: bool = False) -> None:
        self._running = False
        self._worker_manager.running = False
        for wid in list(self._workers.keys()):
            self._worker_manager.terminate_worker(wid, force=force)
        self.ports.release_all()
        self.state.append_event("rush_stopped", {"force": force})

    def stop(self, force: bool = False) -> None:
        self._do_stop(force)
        self.state.save()
        with contextlib.suppress(Exception):
            self.state.generate_state_md()

    def status(self) -> dict[str, Any]:
        ls = self.levels.get_status()
        try:
            md = MetricsCollector(self.state).compute_feature_metrics().to_dict()
        except Exception:
            md = None
        progress = {
            "total": ls["total_tasks"], "completed": ls["completed_tasks"],
            "failed": ls["failed_tasks"], "in_progress": ls["in_progress_tasks"],
            "percent": ls["progress_percent"],
        }
        workers = {
            wid: {
                "status": w.status.value,
                "current_task": w.current_task,
                "tasks_completed": w.tasks_completed,
            }
            for wid, w in self._workers.items()
        }
        return {
            "feature": self.feature, "running": self._running,
            "current_level": ls["current_level"], "progress": progress,
            "workers": workers, "levels": ls["levels"],
            "is_complete": ls["is_complete"], "metrics": md,
            "circuit_breaker": self._circuit_breaker.get_status(),
            "backpressure": self._backpressure.get_status(),
        }

    def _main_loop(self, sleep_fn: Callable[..., Any] | None = None) -> None:
        sleep_fn = sleep_fn or time.sleep
        handled: set[int] = set()
        while self._running:
            try:
                self._poll_workers()
                self._retry_manager.check_retry_ready_tasks()
                cur = self.levels.current_level
                if cur > 0 and cur not in handled and self.levels.is_level_resolved(cur):
                    handled.add(cur)
                    if not self._on_level_complete_handler(cur):
                        continue
                    if self.levels.can_advance():
                        nxt = self.levels.advance_level()
                        if nxt:
                            self._start_level(nxt)
                            self._worker_manager.respawn_workers_for_level(nxt)
                    elif self.levels.get_status()["is_complete"]:
                        self._running = False
                        break
                ended = (WorkerStatus.STOPPED, WorkerStatus.CRASHED)
                active = [w for w in self._workers.values()
                          if w.status not in ended]
                if not active and self._running:
                    rem = self.levels.get_pending_tasks_for_level(cur)
                    if rem:
                        self._auto_respawn_workers(cur, len(rem))
                sleep_fn(self._poll_interval)
            except KeyboardInterrupt:
                self.stop()
                break
            except Exception as e:
                self.state.set_error(str(e))
                self.stop(force=True)
                raise
        with contextlib.suppress(Exception):
            self._plugin_registry.emit_event(
                LifecycleEvent(event_type=PluginHookEvent.RUSH_FINISHED.value, data={"feature": self.feature}))

    def _poll_workers(self) -> None:
        self.state.load()
        self._state_sync.sync_from_disk()
        self._reassign_stranded_tasks()
        self._check_container_health()
        self.task_sync.sync_state()
        self.launcher.sync_state()
        with contextlib.suppress(Exception):
            if self.config.escalation.auto_interrupt:
                from zerg.escalation import EscalationMonitor
                mon = EscalationMonitor()
                for esc in mon.get_unresolved():
                    mon.alert_terminal(esc)
        with contextlib.suppress(Exception):
            from zerg.progress_reporter import ProgressReporter
            ps = {str(wid): {"tasks_completed": wp.tasks_completed,
                             "tasks_total": wp.tasks_total,
                             "current_task": wp.current_task,
                             "current_step": wp.current_step}
                  for wid, wp in ProgressReporter.read_all().items()}
            self.state._state.setdefault("worker_progress", {}).update(ps)
        self._check_stale_tasks()
        done = (WorkerStatus.STOPPED, WorkerStatus.CRASHED)
        for wid, worker in list(self._workers.items()):
            if worker.status in done:
                continue
            st = self.launcher.monitor(wid)
            need_exit = st in (WorkerStatus.STALLED, WorkerStatus.CRASHED,
                               WorkerStatus.CHECKPOINTING, WorkerStatus.STOPPED)
            if need_exit:
                worker.status = st
                self.state.set_worker_state(worker)
            if st == WorkerStatus.STALLED:
                rc = self._restart_counts.get(wid, 0)
                if rc < self.config.heartbeat.max_restarts:
                    self._restart_counts[wid] = rc + 1
                elif worker.current_task:
                    self._handle_task_failure(worker.current_task, wid, "Worker stalled repeatedly")
            elif st == WorkerStatus.CRASHED and worker.current_task:
                self._handle_worker_crash(worker.current_task, wid)
            if need_exit:
                self._worker_manager.handle_worker_exit(wid)
            worker.health_check_at = _now()

    _poll_workers_sync = _poll_workers

    async def start_async(
        self, task_graph_path: str | Path, worker_count: int = 5,
        start_level: int | None = None, dry_run: bool = False,
    ) -> None:
        assignments = self._prepare_start(task_graph_path, worker_count)
        await self.state.load_async()
        self.state.append_event("rush_started", {"workers": worker_count, "total_tasks": self.parser.total_tasks})
        if dry_run:
            self._print_plan(assignments)
            return
        self._spawn_and_begin(worker_count, start_level)
        await asyncio.to_thread(self._main_loop)

    def start_sync(
        self, task_graph_path: str | Path, worker_count: int = 5,
        start_level: int | None = None, dry_run: bool = False,
    ) -> None:
        asyncio.run(self.start_async(
            task_graph_path, worker_count=worker_count,
            start_level=start_level, dry_run=dry_run,
        ))

    async def stop_async(self, force: bool = False) -> None:
        self._do_stop(force)
        await self.state.save_async()
        with contextlib.suppress(Exception):
            self.state.generate_state_md()

    async def _main_loop_as_async(self) -> None:
        await asyncio.to_thread(self._main_loop)

    def on_task_complete(self, cb: Callable[[str], None]) -> None:
        self._on_task_complete.append(cb)

    def on_level_complete(self, cb: Callable[[int], None]) -> None:
        self._on_level_complete.append(cb)

    def retry_task(self, task_id: str) -> bool:
        return self._retry_manager.retry_task(task_id)
    def retry_all_failed(self) -> list[str]:
        return self._retry_manager.retry_all_failed()

    def resume(self) -> None:
        if self._paused:
            self._paused = False
            self.state.set_paused(False)
            self.state.append_event("resumed", {})

    def verify_with_retry(self, task_id: str, command: str, timeout: int = 60, max_retries: int | None = None) -> bool:
        return self._retry_manager.verify_with_retry(task_id, command, timeout, max_retries)

    def generate_task_contexts(self, task_graph: dict) -> dict:
        contexts: dict[str, str] = {}
        feat = task_graph.get("feature", "")
        for task in task_graph.get("tasks", []):
            if task.get("context"):
                continue
            with contextlib.suppress(Exception):
                ctx = self._plugin_registry.build_task_context(task, task_graph, feat)
                if ctx:
                    task["context"] = ctx
                    contexts[task["id"]] = ctx
        return contexts

    def _print_plan(self, assignments: Any) -> None:
        p = self.parser
        print(f"\n=== ZERG Execution Plan ===\n\nFeature: {self.feature}")
        print(f"Tasks: {p.total_tasks} | Levels: {p.levels} | Workers: {assignments.worker_count}\n")
        for level in p.levels:
            print(f"Level {level}:")
            for t in p.get_tasks_for_level(level):
                w = self.assigner.get_task_worker(t["id"]) if self.assigner else "?"
                print(f"  [{t['id']}] {t['title']} -> Worker {w}")

    def _cleanup_orphan_containers(self) -> None:
        self._launcher_config._cleanup_orphan_containers()

    def _auto_detect_launcher_type(self) -> LauncherType:
        return self._launcher_config._auto_detect_launcher_type()

    def _get_worker_image_name(self) -> str:
        return self._launcher_config._get_worker_image_name()

    def _spawn_worker(self, wid: int) -> WorkerState:
        return self._worker_manager.spawn_worker(wid)

    def _spawn_workers(self, count: int) -> int:
        self._target_worker_count = count
        return self._worker_manager.spawn_workers(count)

    def _wait_for_initialization(self, timeout: int = 600) -> bool:
        return self._worker_manager.wait_for_initialization(timeout)

    def _terminate_worker(self, wid: int, force: bool = False) -> None:
        self._worker_manager.terminate_worker(wid, force=force)

    def _handle_worker_exit(self, wid: int) -> None:
        self._worker_manager.handle_worker_exit(wid)

    def _respawn_workers_for_level(self, level: int) -> int:
        return self._worker_manager.respawn_workers_for_level(level)

    def _merge_level(self, level: int) -> MergeFlowResult:
        return self._level_coord.merge_level(level)

    def _rebase_all_workers(self, level: int) -> None:
        self._level_coord.rebase_all_workers(level)

    def _sync_levels_from_state(self) -> None:
        self._state_sync.sync_from_disk()

    def _check_retry_ready_tasks(self) -> None:
        self._retry_manager.check_retry_ready_tasks()

    def _get_remaining_tasks_for_level(self, level: int) -> list[str]:
        return self.levels.get_pending_tasks_for_level(level)
