"""Extended unit tests for port allocation (TC-021).

Tests edge cases and error conditions for PortAllocator.
"""

from unittest.mock import MagicMock, patch

import pytest

from zerg.ports import PortAllocator


class TestPortAllocatorInit:
    """Tests for PortAllocator initialization."""

    def test_init_with_defaults(self) -> None:
        """Test initialization with default range."""
        allocator = PortAllocator()

        assert allocator.range_start == 49152
        assert allocator.range_end == 65535
        assert len(allocator._allocated) == 0

    def test_init_with_custom_range(self) -> None:
        """Test initialization with custom port range."""
        allocator = PortAllocator(range_start=50000, range_end=50100)

        assert allocator.range_start == 50000
        assert allocator.range_end == 50100

    def test_init_with_narrow_range(self) -> None:
        """Test initialization with very narrow range."""
        allocator = PortAllocator(range_start=50000, range_end=50001)

        assert allocator.range_end - allocator.range_start == 1


class TestPortAvailability:
    """Tests for port availability checking."""

    def test_is_available_unallocated(self) -> None:
        """Test checking availability of unallocated port."""
        allocator = PortAllocator()

        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_sock

            result = allocator.is_available(50000)

            assert result is True
            mock_sock.bind.assert_called_with(("127.0.0.1", 50000))

    def test_is_available_already_allocated(self) -> None:
        """Test checking availability of already allocated port."""
        allocator = PortAllocator()
        allocator._allocated.add(50000)

        result = allocator.is_available(50000)

        assert result is False

    def test_is_available_bind_fails(self) -> None:
        """Test checking availability when bind fails."""
        allocator = PortAllocator()

        with patch("socket.socket") as mock_socket:
            mock_sock = MagicMock()
            mock_sock.bind.side_effect = OSError("Address in use")
            mock_socket.return_value.__enter__.return_value = mock_sock

            result = allocator.is_available(50000)

            assert result is False


class TestPortAllocation:
    """Tests for port allocation."""

    def test_allocate_one(self) -> None:
        """Test allocating a single port."""
        allocator = PortAllocator(range_start=50000, range_end=50010)

        with patch.object(allocator, "is_available", return_value=True):
            port = allocator.allocate_one()

            assert port in range(50000, 50011)
            assert port in allocator._allocated

    def test_allocate_multiple(self) -> None:
        """Test allocating multiple ports."""
        allocator = PortAllocator(range_start=50000, range_end=50010)

        with patch.object(allocator, "is_available", return_value=True):
            ports = allocator.allocate(3)

            assert len(ports) == 3
            assert len(set(ports)) == 3  # All unique
            for port in ports:
                assert port in allocator._allocated

    def test_allocate_not_enough_ports(self) -> None:
        """Test allocation fails when not enough ports available."""
        allocator = PortAllocator(range_start=50000, range_end=50002)

        # Mark most ports as unavailable
        with patch.object(allocator, "is_available", return_value=False):
            with pytest.raises(RuntimeError, match="Could not allocate"):
                allocator.allocate(5)

    def test_allocate_zero_count(self) -> None:
        """Test allocating zero ports returns empty list."""
        allocator = PortAllocator()

        ports = allocator.allocate(0)

        assert ports == []

    def test_allocate_skips_unavailable(self) -> None:
        """Test allocation skips unavailable ports."""
        allocator = PortAllocator(range_start=50000, range_end=50010)

        # Make odd ports unavailable
        def availability(port):
            return port % 2 == 0

        with patch.object(allocator, "is_available", side_effect=availability):
            ports = allocator.allocate(3)

            assert len(ports) == 3
            assert all(p % 2 == 0 for p in ports)


class TestPortRelease:
    """Tests for port release."""

    def test_release_allocated_port(self) -> None:
        """Test releasing an allocated port."""
        allocator = PortAllocator()
        allocator._allocated.add(50000)

        allocator.release(50000)

        assert 50000 not in allocator._allocated

    def test_release_unallocated_port(self) -> None:
        """Test releasing an unallocated port (no-op)."""
        allocator = PortAllocator()

        # Should not raise
        allocator.release(50000)

        assert 50000 not in allocator._allocated

    def test_release_all(self) -> None:
        """Test releasing all allocated ports."""
        allocator = PortAllocator()
        allocator._allocated.update({50000, 50001, 50002})

        allocator.release_all()

        assert len(allocator._allocated) == 0


class TestGetAllocated:
    """Tests for getting allocated ports."""

    def test_get_allocated_empty(self) -> None:
        """Test getting allocated ports when none allocated."""
        allocator = PortAllocator()

        result = allocator.get_allocated()

        assert result == set()

    def test_get_allocated_returns_copy(self) -> None:
        """Test that get_allocated returns a copy."""
        allocator = PortAllocator()
        allocator._allocated.add(50000)

        result = allocator.get_allocated()
        result.add(60000)

        assert 60000 not in allocator._allocated

    def test_get_allocated_with_ports(self) -> None:
        """Test getting allocated ports."""
        allocator = PortAllocator()
        allocator._allocated.update({50000, 50001})

        result = allocator.get_allocated()

        assert result == {50000, 50001}


class TestWorkerPortAllocation:
    """Tests for worker-specific port allocation."""

    def test_allocate_for_worker(self) -> None:
        """Test allocating ports for a worker."""
        allocator = PortAllocator(range_start=50000, range_end=50010)

        with patch.object(allocator, "is_available", return_value=True):
            ports = allocator.allocate_for_worker(worker_id=1, ports_per_worker=2)

            assert len(ports) == 2

    def test_release_for_worker(self) -> None:
        """Test releasing ports for a worker."""
        allocator = PortAllocator()
        allocator._allocated.update({50000, 50001})

        allocator.release_for_worker([50000, 50001], worker_id=1)

        assert 50000 not in allocator._allocated
        assert 50001 not in allocator._allocated

    def test_release_for_worker_partial(self) -> None:
        """Test releasing some ports for a worker."""
        allocator = PortAllocator()
        allocator._allocated.update({50000, 50001, 50002})

        allocator.release_for_worker([50000, 50001], worker_id=1)

        assert 50000 not in allocator._allocated
        assert 50001 not in allocator._allocated
        assert 50002 in allocator._allocated


class TestAvailableCount:
    """Tests for available port count."""

    def test_available_count_all_free(self) -> None:
        """Test available count when all ports free."""
        allocator = PortAllocator(range_start=50000, range_end=50009)

        assert allocator.available_count == 10

    def test_available_count_some_allocated(self) -> None:
        """Test available count with some allocated."""
        allocator = PortAllocator(range_start=50000, range_end=50009)
        allocator._allocated.update({50000, 50001, 50002})

        assert allocator.available_count == 7

    def test_available_count_all_allocated(self) -> None:
        """Test available count when all allocated."""
        allocator = PortAllocator(range_start=50000, range_end=50002)
        allocator._allocated.update({50000, 50001, 50002})

        assert allocator.available_count == 0


class TestEdgeCases:
    """Tests for edge cases."""

    def test_concurrent_allocation_tracking(self) -> None:
        """Test that allocation properly tracks ports."""
        allocator = PortAllocator(range_start=50000, range_end=50010)

        # Mock is_available to return True only for ports not already allocated

        def tracking_is_available(port: int) -> bool:
            if port in allocator._allocated:
                return False
            return True

        with patch.object(allocator, "is_available", side_effect=tracking_is_available):
            port1 = allocator.allocate_one()
            port2 = allocator.allocate_one()

            assert port1 != port2
            assert port1 in allocator._allocated
            assert port2 in allocator._allocated

    def test_release_and_reallocate(self) -> None:
        """Test releasing then reallocating a port."""
        allocator = PortAllocator(range_start=50000, range_end=50000)

        with patch.object(allocator, "is_available", return_value=True):
            port1 = allocator.allocate_one()
            allocator.release(port1)

            # Should be able to allocate again
            port2 = allocator.allocate_one()
            assert port2 == 50000

    def test_large_allocation_request(self) -> None:
        """Test allocating many ports at once."""
        allocator = PortAllocator(range_start=50000, range_end=50099)

        with patch.object(allocator, "is_available", return_value=True):
            ports = allocator.allocate(50)

            assert len(ports) == 50
            assert len(set(ports)) == 50
