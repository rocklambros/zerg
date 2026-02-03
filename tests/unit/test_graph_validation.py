"""Unit tests for graph_validation module."""

from zerg.graph_validation import validate_graph_properties


def _make_graph(tasks):
    """Helper to create a task graph dict."""
    return {"tasks": tasks}


def _task(id, level=1, deps=None, consumers=None, integration_test=None, title=""):
    """Helper to create a task dict."""
    t = {
        "id": id,
        "title": title or f"Task {id}",
        "level": level,
        "dependencies": deps or [],
    }
    if consumers is not None:
        t["consumers"] = consumers
    if integration_test is not None:
        t["integration_test"] = integration_test
    return t


class TestDependencyReferences:
    def test_valid_deps(self):
        graph = _make_graph(
            [
                _task("T1", level=1),
                _task("T2", level=2, deps=["T1"]),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        assert not errors

    def test_invalid_dep_reference(self):
        graph = _make_graph(
            [
                _task("T1", level=1),
                _task("T2", level=2, deps=["T1", "T999"]),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        assert any("T999" in e for e in errors)

    def test_empty_graph(self):
        graph = _make_graph([])
        errors, warnings = validate_graph_properties(graph)
        assert not errors


class TestIntraLevelCycles:
    def test_no_cycle(self):
        graph = _make_graph(
            [
                _task("T1", level=1),
                _task("T2", level=1),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        cycle_errors = [e for e in errors if "cycle" in e.lower() or "circular" in e.lower()]
        assert not cycle_errors

    def test_self_reference(self):
        graph = _make_graph(
            [
                _task("T1", level=1, deps=["T1"]),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        # Should detect as intra-level cycle (T1 depends on itself at level 1)
        assert len(errors) > 0

    def test_mutual_cycle_same_level(self):
        graph = _make_graph(
            [
                _task("T1", level=1, deps=["T2"]),
                _task("T2", level=1, deps=["T1"]),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        cycle_errors = [e for e in errors if "cycle" in e.lower()]
        assert len(cycle_errors) >= 1


class TestOrphanTasks:
    def test_l1_not_orphan(self):
        graph = _make_graph(
            [
                _task("T1", level=1),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        orphan_warnings = [w for w in warnings if "orphan" in w.lower()]
        assert not orphan_warnings

    def test_l2_with_no_dependents_is_orphan(self):
        # T2 at L2 has no task depending on it and no consumers
        graph = _make_graph(
            [
                _task("T1", level=1),
                _task("T2", level=2, deps=["T1"]),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        orphan_warnings = [w for w in warnings if "orphan" in w.lower()]
        assert len(orphan_warnings) >= 1

    def test_l2_with_dependents_not_orphan(self):
        graph = _make_graph(
            [
                _task("T1", level=1),
                _task("T2", level=2, deps=["T1"]),
                _task("T3", level=3, deps=["T2"]),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        # T2 is depended on by T3, so not orphan
        orphan_t2 = [w for w in warnings if "T2" in w and "orphan" in w.lower()]
        assert not orphan_t2

    def test_l2_with_consumers_not_orphan(self):
        graph = _make_graph(
            [
                _task("T1", level=1),
                _task("T2", level=2, deps=["T1"], consumers=["T1"], integration_test="tests/t.py"),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        orphan_t2 = [w for w in warnings if "T2" in w and "orphan" in w.lower()]
        assert not orphan_t2


class TestUnreachableTasks:
    def test_all_reachable(self):
        graph = _make_graph(
            [
                _task("T1", level=1),
                _task("T2", level=2, deps=["T1"]),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        unreachable = [e for e in errors if "unreachable" in e.lower()]
        assert not unreachable

    def test_disconnected_l2_task(self):
        # T3 at L2 has no deps — not reachable from L1 roots
        graph = _make_graph(
            [
                _task("T1", level=1),
                _task("T2", level=2, deps=["T1"]),
                _task("T3", level=2, deps=[]),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        unreachable = [e for e in errors if "unreachable" in e.lower() and "T3" in e]
        assert len(unreachable) >= 1

    def test_l1_tasks_always_reachable(self):
        graph = _make_graph(
            [
                _task("T1", level=1),
                _task("T2", level=1),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        unreachable = [e for e in errors if "unreachable" in e.lower()]
        assert not unreachable


class TestConsumerReferences:
    def test_valid_consumers(self):
        graph = _make_graph(
            [
                _task("T1", level=1, consumers=["T2"], integration_test="tests/test_t1.py"),
                _task("T2", level=2, deps=["T1"]),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        consumer_errors = [e for e in errors if "consumer" in e.lower()]
        assert not consumer_errors

    def test_invalid_consumer_reference(self):
        graph = _make_graph(
            [
                _task("T1", level=1, consumers=["T999"], integration_test="tests/test.py"),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        assert any("T999" in e for e in errors)

    def test_empty_consumers_ok(self):
        graph = _make_graph(
            [
                _task("T1", level=1, consumers=[]),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        consumer_errors = [e for e in errors if "consumer" in e.lower()]
        assert not consumer_errors


class TestConsumerIntegrationTest:
    def test_consumers_with_integration_test(self):
        graph = _make_graph(
            [
                _task("T1", level=1, consumers=["T2"], integration_test="tests/test.py"),
                _task("T2", level=2, deps=["T1"]),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        test_errors = [e for e in errors if "integration_test" in e.lower()]
        assert not test_errors

    def test_consumers_without_integration_test(self):
        graph = _make_graph(
            [
                _task("T1", level=1, consumers=["T2"]),
                _task("T2", level=2, deps=["T1"]),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        test_errors = [e for e in errors if "integration_test" in e.lower()]
        assert len(test_errors) >= 1

    def test_no_consumers_no_test_needed(self):
        graph = _make_graph(
            [
                _task("T1", level=1, consumers=[]),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        test_errors = [e for e in errors if "integration_test" in e.lower()]
        assert not test_errors

    def test_none_consumers_no_test_needed(self):
        graph = _make_graph(
            [
                _task("T1", level=1),
            ]
        )
        errors, warnings = validate_graph_properties(graph)
        test_errors = [e for e in errors if "integration_test" in e.lower()]
        assert not test_errors
