"""Port allocation for ZERG workers."""

import asyncio
import random
import socket
from dataclasses import dataclass, field

from zerg.constants import DEFAULT_PORT_RANGE_END, DEFAULT_PORT_RANGE_START
from zerg.logging import get_logger

logger = get_logger("ports")


@dataclass
class PortAllocator:
    """Allocate and track ephemeral ports for workers."""

    range_start: int = DEFAULT_PORT_RANGE_START
    range_end: int = DEFAULT_PORT_RANGE_END
    _allocated: set[int] = field(default_factory=set)

    def is_available(self, port: int) -> bool:
        """Check if a port is available for binding.

        Args:
            port: Port number to check

        Returns:
            True if port is available
        """
        if port in self._allocated:
            return False

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("127.0.0.1", port))
                return True
        except OSError:
            return False

    def allocate(self, count: int = 1) -> list[int]:
        """Allocate available ports.

        Args:
            count: Number of ports to allocate

        Returns:
            List of allocated port numbers

        Raises:
            RuntimeError: If not enough ports available
        """
        allocated: list[int] = []
        max_attempts = count * 10  # Allow some retries

        # Generate candidates in random order to avoid collisions
        candidates = list(range(self.range_start, self.range_end + 1))
        random.shuffle(candidates)

        for attempts, port in enumerate(candidates):
            if len(allocated) >= count:
                break

            if self.is_available(port):
                self._allocated.add(port)
                allocated.append(port)
                logger.debug(f"Allocated port {port}")

            if attempts + 1 >= max_attempts:
                break

        if len(allocated) < count:
            raise RuntimeError(
                f"Could not allocate {count} ports. "
                f"Only {len(allocated)} available in range "
                f"{self.range_start}-{self.range_end}"
            )

        logger.info(f"Allocated {count} ports: {allocated}")
        return allocated

    def allocate_one(self) -> int:
        """Allocate a single port.

        Returns:
            Allocated port number
        """
        return self.allocate(1)[0]

    def release(self, port: int) -> None:
        """Release an allocated port.

        Args:
            port: Port number to release
        """
        if port in self._allocated:
            self._allocated.discard(port)
            logger.debug(f"Released port {port}")

    def release_all(self) -> None:
        """Release all allocated ports."""
        count = len(self._allocated)
        self._allocated.clear()
        logger.info(f"Released {count} ports")

    def get_allocated(self) -> set[int]:
        """Get set of currently allocated ports.

        Returns:
            Set of allocated port numbers
        """
        return self._allocated.copy()

    def allocate_for_worker(self, worker_id: int, ports_per_worker: int = 1) -> list[int]:
        """Allocate ports for a specific worker.

        Args:
            worker_id: Worker ID (for logging)
            ports_per_worker: Number of ports to allocate

        Returns:
            List of allocated ports
        """
        ports = self.allocate(ports_per_worker)
        logger.info(f"Worker {worker_id}: allocated ports {ports}")
        return ports

    def release_for_worker(self, ports: list[int], worker_id: int) -> None:
        """Release ports for a specific worker.

        Args:
            ports: List of ports to release
            worker_id: Worker ID (for logging)
        """
        for port in ports:
            self.release(port)
        logger.info(f"Worker {worker_id}: released ports {ports}")

    # --- Async methods ---

    async def allocate_one_async(self) -> int:
        """Allocate a single port asynchronously.

        Returns:
            Allocated port number
        """
        return await asyncio.to_thread(self.allocate_one)

    async def allocate_many_async(self, count: int) -> list[int]:
        """Allocate multiple ports asynchronously.

        Uses asyncio.gather for parallel allocation.

        Args:
            count: Number of ports to allocate

        Returns:
            List of allocated port numbers
        """
        tasks = [asyncio.to_thread(self.allocate_one) for _ in range(count)]
        return list(await asyncio.gather(*tasks))

    async def allocate_for_worker_async(self, worker_id: int, ports_per_worker: int = 1) -> list[int]:
        """Allocate ports for a specific worker asynchronously.

        Args:
            worker_id: Worker ID (for logging)
            ports_per_worker: Number of ports to allocate

        Returns:
            List of allocated ports
        """
        if ports_per_worker == 1:
            port = await self.allocate_one_async()
            ports = [port]
        else:
            ports = await self.allocate_many_async(ports_per_worker)
        logger.info(f"Worker {worker_id}: allocated ports {ports} (async)")
        return ports

    @property
    def available_count(self) -> int:
        """Estimate number of available ports.

        Returns:
            Estimated available port count
        """
        total_range = self.range_end - self.range_start + 1
        return total_range - len(self._allocated)
