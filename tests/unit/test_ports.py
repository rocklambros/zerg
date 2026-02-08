"""Tests for ZERG port allocation module."""

import socket
from unittest.mock import MagicMock, patch

import pytest

from zerg.ports import PortAllocator


class TestPortAllocatorInit:
    """Tests for PortAllocator initialization and defaults."""

    def test_default_range(self) -> None:
        allocator = PortAllocator()
        assert allocator.range_start == 49152
        assert allocator.range_end == 65535

    def test_custom_range(self) -> None:
        allocator = PortAllocator(range_start=10000, range_end=10100)
        assert allocator.range_start == 10000
        assert allocator.range_end == 10100

    def test_allocated_starts_empty(self) -> None:
        allocator = PortAllocator()
        assert len(allocator._allocated) == 0


class TestIsAvailable:
    """Tests for port availability checking."""

    def test_allocated_port_not_available(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50010)
        allocator._allocated.add(50005)
        assert allocator.is_available(50005) is False

    def test_available_port_with_successful_bind(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50010)
        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)

        with patch("zerg.ports.socket.socket", return_value=mock_sock):
            result = allocator.is_available(50005)

        assert result is True
        mock_sock.setsockopt.assert_called_once_with(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        mock_sock.bind.assert_called_once_with(("127.0.0.1", 50005))

    def test_unavailable_port_oserror(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50010)
        mock_sock = MagicMock()
        mock_sock.__enter__ = MagicMock(return_value=mock_sock)
        mock_sock.__exit__ = MagicMock(return_value=False)
        mock_sock.bind.side_effect = OSError("Address already in use")

        with patch("zerg.ports.socket.socket", return_value=mock_sock):
            result = allocator.is_available(50005)

        assert result is False


class TestAllocate:
    """Tests for port allocation."""

    def test_allocate_single_port(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50010)
        with patch.object(allocator, "is_available", return_value=True):
            ports = allocator.allocate(1)

        assert len(ports) == 1
        assert ports[0] in range(50000, 50011)
        assert ports[0] in allocator._allocated

    def test_allocate_multiple_ports(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50100)
        with patch.object(allocator, "is_available", return_value=True):
            ports = allocator.allocate(3)

        assert len(ports) == 3
        # All ports should be unique
        assert len(set(ports)) == 3
        # All ports tracked in _allocated
        for p in ports:
            assert p in allocator._allocated

    def test_allocate_not_enough_ports_raises(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50002)
        with patch.object(allocator, "is_available", return_value=False):
            with pytest.raises(RuntimeError, match="Could not allocate"):
                allocator.allocate(3)

    def test_allocate_skips_unavailable_ports(self) -> None:
        """Allocator should skip unavailable ports and continue to next candidates."""
        allocator = PortAllocator(range_start=50000, range_end=50010)
        call_count = 0

        def alternating_available(port: int) -> bool:
            nonlocal call_count
            call_count += 1
            # Every other port is available
            return call_count % 2 == 0

        with patch.object(allocator, "is_available", side_effect=alternating_available):
            ports = allocator.allocate(2)

        assert len(ports) == 2

    def test_allocate_respects_max_attempts(self) -> None:
        """When count*10 attempts are exhausted without finding enough, raise RuntimeError."""
        allocator = PortAllocator(range_start=50000, range_end=60000)
        # is_available always False -> should hit max_attempts and raise
        with patch.object(allocator, "is_available", return_value=False):
            with pytest.raises(RuntimeError, match="Could not allocate"):
                allocator.allocate(1)


class TestAllocateOne:
    """Tests for single port allocation."""

    def test_allocate_one_returns_int(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50010)
        with patch.object(allocator, "is_available", return_value=True):
            port = allocator.allocate_one()

        assert isinstance(port, int)
        assert port in allocator._allocated


class TestRelease:
    """Tests for port release."""

    def test_release_allocated_port(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50010)
        allocator._allocated.add(50005)
        allocator.release(50005)
        assert 50005 not in allocator._allocated

    def test_release_unallocated_port_is_noop(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50010)
        # Should not raise
        allocator.release(50005)
        assert 50005 not in allocator._allocated

    def test_release_all(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50010)
        allocator._allocated = {50000, 50001, 50002}
        allocator.release_all()
        assert len(allocator._allocated) == 0


class TestGetAllocated:
    """Tests for get_allocated."""

    def test_returns_copy(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50010)
        allocator._allocated = {50001, 50002}
        result = allocator.get_allocated()
        assert result == {50001, 50002}
        # Modifying the returned set should not affect internal state
        result.add(99999)
        assert 99999 not in allocator._allocated


class TestAllocateForWorker:
    """Tests for worker-specific allocation."""

    def test_allocate_for_worker(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50100)
        with patch.object(allocator, "is_available", return_value=True):
            ports = allocator.allocate_for_worker(worker_id=1, ports_per_worker=2)

        assert len(ports) == 2
        for p in ports:
            assert p in allocator._allocated

    def test_release_for_worker(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50010)
        allocator._allocated = {50001, 50002, 50003}
        allocator.release_for_worker([50001, 50002], worker_id=1)
        assert 50001 not in allocator._allocated
        assert 50002 not in allocator._allocated
        assert 50003 in allocator._allocated


class TestAvailableCount:
    """Tests for the available_count property."""

    def test_available_count_no_allocations(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50009)
        # 10 ports in range (50000..50009 inclusive)
        assert allocator.available_count == 10

    def test_available_count_with_allocations(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50009)
        allocator._allocated = {50000, 50001, 50002}
        assert allocator.available_count == 7


class TestAsyncMethods:
    """Tests for async port allocation methods."""

    @pytest.mark.asyncio
    async def test_allocate_one_async(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50010)
        with patch.object(allocator, "is_available", return_value=True):
            port = await allocator.allocate_one_async()

        assert isinstance(port, int)
        assert port in allocator._allocated

    @pytest.mark.asyncio
    async def test_allocate_many_async(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50100)
        with patch.object(allocator, "is_available", return_value=True):
            ports = await allocator.allocate_many_async(3)

        assert len(ports) == 3

    @pytest.mark.asyncio
    async def test_allocate_for_worker_async_single(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50010)
        with patch.object(allocator, "is_available", return_value=True):
            ports = await allocator.allocate_for_worker_async(worker_id=1, ports_per_worker=1)

        assert len(ports) == 1

    @pytest.mark.asyncio
    async def test_allocate_for_worker_async_multiple(self) -> None:
        allocator = PortAllocator(range_start=50000, range_end=50100)
        with patch.object(allocator, "is_available", return_value=True):
            ports = await allocator.allocate_for_worker_async(worker_id=2, ports_per_worker=3)

        assert len(ports) == 3
