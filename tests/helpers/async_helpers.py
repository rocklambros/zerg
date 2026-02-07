"""Async testing utilities for ZERG.

This module provides utilities for testing async code in ZERG, including:
- AsyncMockContextManager: Mock async context managers
- async_subprocess_mock: Simulate async subprocess execution
- timeout_helper: Configurable timeout wrapper for async operations
- event_loop_fixture: pytest fixture for event loop management
- async_file_mock: Simulate async file operations

Async Testing Best Practices for ZERG:
--------------------------------------
1. Use `pytest.mark.asyncio` for async tests (auto mode enabled in pyproject.toml)
2. Prefer real async operations over threading when possible
3. Use `asyncio.wait_for()` with explicit timeouts to prevent hanging tests
4. Clean up resources in finally blocks or use async context managers
5. For concurrent tests, use `asyncio.gather()` with `return_exceptions=True`
6. Mock external I/O at the boundary, not internal async code
7. Use `asyncio.TaskGroup` (Python 3.11+) for structured concurrency
8. Avoid `asyncio.sleep(0)` tricks; use proper synchronization primitives

Example Usage:
--------------
```python
import pytest
from tests.helpers.async_helpers import (
    AsyncMockContextManager,
    async_subprocess_mock,
    timeout_helper,
    ConcurrentTestRunner,
)

@pytest.mark.asyncio
async def test_with_context_manager():
    async with AsyncMockContextManager(enter_value="connected") as conn:
        assert conn == "connected"

@pytest.mark.asyncio
async def test_with_timeout():
    result = await timeout_helper(some_async_func(), timeout=5.0)
    assert result is not None

@pytest.mark.asyncio
async def test_subprocess():
    mock = async_subprocess_mock(stdout="output", returncode=0)
    result = await mock.communicate()
    assert result[0] == "output"
```
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine, Generator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# =============================================================================
# AsyncMockContextManager - Mock async context managers
# =============================================================================


class AsyncMockContextManager:
    """Mock for async context managers (async with).

    Provides configurable enter/exit behavior for testing code that uses
    async context managers like database connections, file handles, etc.

    Attributes:
        enter_value: Value returned by __aenter__
        exit_exception: Exception to raise on __aexit__ (if any)
        enter_side_effect: Callable/exception to trigger on enter
        exit_side_effect: Callable/exception to trigger on exit
        entered: Whether __aenter__ was called
        exited: Whether __aexit__ was called
        exit_args: Arguments passed to __aexit__

    Example:
        ```python
        # Basic usage
        async with AsyncMockContextManager(enter_value="conn") as conn:
            assert conn == "conn"

        # With exception on enter
        cm = AsyncMockContextManager(enter_side_effect=ConnectionError())
        with pytest.raises(ConnectionError):
            async with cm:
                pass

        # Verify exit was called
        cm = AsyncMockContextManager(enter_value="resource")
        async with cm as resource:
            pass
        assert cm.exited
        ```
    """

    def __init__(
        self,
        enter_value: Any = None,
        exit_exception: BaseException | None = None,
        enter_side_effect: BaseException | Callable[[], Any] | None = None,
        exit_side_effect: BaseException | Callable[..., Any] | None = None,
    ) -> None:
        """Initialize the async context manager mock.

        Args:
            enter_value: Value to return from __aenter__
            exit_exception: Exception to raise from __aexit__
            enter_side_effect: Side effect on enter (exception or callable)
            exit_side_effect: Side effect on exit (exception or callable)
        """
        self.enter_value = enter_value
        self.exit_exception = exit_exception
        self.enter_side_effect = enter_side_effect
        self.exit_side_effect = exit_side_effect
        self.entered = False
        self.exited = False
        self.exit_args: tuple[Any, ...] | None = None

    async def __aenter__(self) -> Any:
        """Enter the async context.

        Returns:
            The configured enter_value

        Raises:
            Any exception configured in enter_side_effect
        """
        self.entered = True

        if self.enter_side_effect is not None:
            if isinstance(self.enter_side_effect, BaseException):
                raise self.enter_side_effect
            result = self.enter_side_effect()
            if asyncio.iscoroutine(result):
                await result
            return result if result is not None else self.enter_value

        return self.enter_value

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Exit the async context.

        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Traceback if an exception was raised

        Returns:
            False to propagate exceptions, True to suppress

        Raises:
            Any exception configured in exit_exception or exit_side_effect
        """
        self.exited = True
        self.exit_args = (exc_type, exc_val, exc_tb)

        if self.exit_side_effect is not None:
            if isinstance(self.exit_side_effect, BaseException):
                raise self.exit_side_effect
            result = self.exit_side_effect(exc_type, exc_val, exc_tb)
            if asyncio.iscoroutine(result):
                await result

        if self.exit_exception is not None:
            raise self.exit_exception

        return False


class AsyncMockContextManagerFactory:
    """Factory for creating multiple async context manager mocks.

    Useful for testing code that creates multiple connections or resources.

    Example:
        ```python
        factory = AsyncMockContextManagerFactory(default_value="conn")
        cm1 = factory.create()
        cm2 = factory.create(enter_value="special")

        assert factory.created_count == 2
        ```
    """

    def __init__(self, default_value: Any = None) -> None:
        """Initialize the factory.

        Args:
            default_value: Default enter_value for created managers
        """
        self.default_value = default_value
        self.created: list[AsyncMockContextManager] = []

    def create(
        self,
        enter_value: Any | None = None,
        **kwargs: Any,
    ) -> AsyncMockContextManager:
        """Create a new async context manager mock.

        Args:
            enter_value: Override default enter value
            **kwargs: Additional arguments for AsyncMockContextManager

        Returns:
            New AsyncMockContextManager instance
        """
        value = enter_value if enter_value is not None else self.default_value
        cm = AsyncMockContextManager(enter_value=value, **kwargs)
        self.created.append(cm)
        return cm

    @property
    def created_count(self) -> int:
        """Return number of context managers created."""
        return len(self.created)

    def reset(self) -> None:
        """Clear the list of created context managers."""
        self.created.clear()


# =============================================================================
# async_subprocess_mock - Simulate async subprocess execution
# =============================================================================


@dataclass
class AsyncSubprocessMock:
    """Mock for async subprocess operations.

    Simulates asyncio.subprocess.Process for testing subprocess spawning
    and management in ZERG launcher and orchestrator.

    Attributes:
        stdout: Simulated stdout content
        stderr: Simulated stderr content
        returncode: Exit code to return
        pid: Simulated process ID
        communicate_delay: Delay in seconds for communicate()
        kill_side_effect: Exception to raise on kill()
        terminate_side_effect: Exception to raise on terminate()
        _killed: Whether kill() was called
        _terminated: Whether terminate() was called
        _waited: Whether wait() was called

    Example:
        ```python
        mock = async_subprocess_mock(
            stdout="task output",
            stderr="",
            returncode=0,
            pid=12345,
        )

        stdout, stderr = await mock.communicate()
        assert stdout == "task output"
        assert mock.returncode == 0
        ```
    """

    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    pid: int = 12345
    communicate_delay: float = 0.0
    kill_side_effect: BaseException | None = None
    terminate_side_effect: BaseException | None = None
    _killed: bool = field(default=False, repr=False)
    _terminated: bool = field(default=False, repr=False)
    _waited: bool = field(default=False, repr=False)

    async def communicate(
        self,
        input: bytes | None = None,  # noqa: A002
    ) -> tuple[str, str]:
        """Simulate process.communicate().

        Args:
            input: Input to send to stdin (ignored in mock)

        Returns:
            Tuple of (stdout, stderr)
        """
        if self.communicate_delay > 0:
            await asyncio.sleep(self.communicate_delay)
        return (self.stdout, self.stderr)

    async def wait(self) -> int:
        """Simulate process.wait().

        Returns:
            The configured returncode
        """
        self._waited = True
        return self.returncode

    def kill(self) -> None:
        """Simulate process.kill().

        Raises:
            Any exception configured in kill_side_effect
        """
        if self.kill_side_effect is not None:
            raise self.kill_side_effect
        self._killed = True
        self.returncode = -9  # SIGKILL

    def terminate(self) -> None:
        """Simulate process.terminate().

        Raises:
            Any exception configured in terminate_side_effect
        """
        if self.terminate_side_effect is not None:
            raise self.terminate_side_effect
        self._terminated = True
        self.returncode = -15  # SIGTERM

    def poll(self) -> int | None:
        """Simulate process.poll().

        Returns:
            returncode if process has exited, None if still running
        """
        if self._killed or self._terminated:
            return self.returncode
        return None

    @property
    def killed(self) -> bool:
        """Return whether kill() was called."""
        return self._killed

    @property
    def terminated(self) -> bool:
        """Return whether terminate() was called."""
        return self._terminated


def async_subprocess_mock(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
    pid: int = 12345,
    communicate_delay: float = 0.0,
) -> AsyncSubprocessMock:
    """Create an async subprocess mock.

    Convenience factory function for AsyncSubprocessMock.

    Args:
        stdout: Simulated stdout content
        stderr: Simulated stderr content
        returncode: Exit code to return
        pid: Simulated process ID
        communicate_delay: Delay in seconds for communicate()

    Returns:
        Configured AsyncSubprocessMock instance

    Example:
        ```python
        # Success case
        mock = async_subprocess_mock(stdout="OK", returncode=0)

        # Failure case
        mock = async_subprocess_mock(stderr="Error", returncode=1)

        # Slow process
        mock = async_subprocess_mock(communicate_delay=5.0)
        ```
    """
    return AsyncSubprocessMock(
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
        pid=pid,
        communicate_delay=communicate_delay,
    )


async def create_subprocess_exec_mock(
    *args: Any,
    mock_process: AsyncSubprocessMock | None = None,
    **kwargs: Any,
) -> AsyncSubprocessMock:
    """Mock replacement for asyncio.create_subprocess_exec.

    Use with unittest.mock.patch to replace asyncio.create_subprocess_exec.

    Args:
        *args: Command arguments (ignored)
        mock_process: Pre-configured mock process to return
        **kwargs: Additional subprocess kwargs (ignored)

    Returns:
        AsyncSubprocessMock instance

    Example:
        ```python
        from unittest.mock import patch

        mock = async_subprocess_mock(stdout="output", returncode=0)

        @pytest.mark.asyncio
        async def test_spawn():
            with patch(
                "asyncio.create_subprocess_exec",
                side_effect=lambda *a, **k: create_subprocess_exec_mock(
                    *a, mock_process=mock, **k
                ),
            ):
                process = await asyncio.create_subprocess_exec("cmd")
                stdout, _ = await process.communicate()
                assert stdout == "output"
        ```
    """
    return mock_process or AsyncSubprocessMock()


# =============================================================================
# timeout_helper - Wrapper for async operations with configurable timeout
# =============================================================================


class AsyncTimeoutError(Exception):
    """Raised when an async operation times out.

    Provides more context than the standard asyncio.TimeoutError.
    """

    def __init__(
        self,
        message: str = "Operation timed out",
        timeout: float | None = None,
        operation: str | None = None,
    ) -> None:
        """Initialize timeout error.

        Args:
            message: Error message
            timeout: Timeout value that was exceeded
            operation: Description of the operation that timed out
        """
        self.timeout = timeout
        self.operation = operation
        full_message = message
        if timeout is not None:
            full_message += f" (timeout={timeout}s)"
        if operation is not None:
            full_message += f" [{operation}]"
        super().__init__(full_message)


async def timeout_helper[T](
    coro: Coroutine[Any, Any, T],
    timeout: float = 30.0,
    operation: str | None = None,
    on_timeout: Callable[[], Any] | None = None,
) -> T:
    """Execute an async operation with configurable timeout.

    Wraps asyncio.wait_for with better error handling and optional
    cleanup callback.

    Args:
        coro: Coroutine to execute
        timeout: Timeout in seconds (default: 30.0)
        operation: Description for error messages
        on_timeout: Optional callback to run on timeout

    Returns:
        Result of the coroutine

    Raises:
        AsyncTimeoutError: If operation times out

    Example:
        ```python
        # Basic usage
        result = await timeout_helper(fetch_data(), timeout=5.0)

        # With operation description
        result = await timeout_helper(
            long_operation(),
            timeout=60.0,
            operation="database migration",
        )

        # With cleanup callback
        async def cleanup():
            await connection.close()

        result = await timeout_helper(
            operation(),
            timeout=10.0,
            on_timeout=cleanup,
        )
        ```
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except TimeoutError:
        if on_timeout is not None:
            callback_result = on_timeout()
            if asyncio.iscoroutine(callback_result):
                await callback_result
        raise AsyncTimeoutError(
            timeout=timeout,
            operation=operation,
        ) from None


@asynccontextmanager
async def timeout_context(
    timeout: float = 30.0,
    operation: str | None = None,
) -> AsyncGenerator[None, None]:
    """Context manager for timeout-bounded operations.

    Args:
        timeout: Timeout in seconds
        operation: Description for error messages

    Yields:
        None

    Raises:
        AsyncTimeoutError: If context times out

    Example:
        ```python
        async with timeout_context(timeout=5.0, operation="batch"):
            await task1()
            await task2()
        ```
    """
    try:
        async with asyncio.timeout(timeout):
            yield
    except TimeoutError:
        raise AsyncTimeoutError(timeout=timeout, operation=operation) from None


# =============================================================================
# event_loop_fixture - pytest fixture for event loop management
# =============================================================================


@pytest.fixture
def event_loop_fixture() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Pytest fixture for event loop management.

    Creates a new event loop for each test and properly closes it after.
    Use when you need explicit control over the event loop.

    Note: With pytest-asyncio's auto mode, you typically don't need this
    fixture unless you have specific event loop requirements.

    Yields:
        Event loop instance

    Example:
        ```python
        def test_with_loop(event_loop_fixture):
            loop = event_loop_fixture

            async def task():
                return 42

            result = loop.run_until_complete(task())
            assert result == 42
        ```
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    # Clean up pending tasks
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    # Allow cancelled tasks to complete
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    loop.close()


@pytest.fixture
def new_event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Alternative fixture name for event loop.

    Alias for event_loop_fixture for compatibility with different
    naming conventions.

    Yields:
        Event loop instance
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    loop.close()


# =============================================================================
# async_file_mock - Simulate async file operations
# =============================================================================


@dataclass
class AsyncFileMock:
    """Mock for async file operations.

    Simulates aiofiles-style async file I/O for testing file operations
    without actual filesystem access.

    Attributes:
        content: File content for read operations
        written: List of content written
        path: Simulated file path
        mode: File mode (r, w, a, etc.)
        read_side_effect: Exception to raise on read
        write_side_effect: Exception to raise on write
        _closed: Whether close() was called
        _position: Current read position

    Example:
        ```python
        # Reading
        mock = AsyncFileMock(content="file contents", path="/tmp/test.txt")
        async with mock:
            data = await mock.read()
            assert data == "file contents"

        # Writing
        mock = AsyncFileMock(path="/tmp/output.txt", mode="w")
        async with mock:
            await mock.write("new content")
        assert mock.written == ["new content"]
        ```
    """

    content: str = ""
    written: list[str] = field(default_factory=list)
    path: str | Path = ""
    mode: str = "r"
    read_side_effect: BaseException | None = None
    write_side_effect: BaseException | None = None
    _closed: bool = field(default=False, repr=False)
    _position: int = field(default=0, repr=False)

    async def read(self, size: int = -1) -> str:
        """Simulate async file read.

        Args:
            size: Number of characters to read (-1 for all)

        Returns:
            File content

        Raises:
            Any exception configured in read_side_effect
        """
        if self.read_side_effect is not None:
            raise self.read_side_effect
        if size == -1:
            result = self.content[self._position :]
            self._position = len(self.content)
            return result
        result = self.content[self._position : self._position + size]
        self._position += size
        return result

    async def readline(self) -> str:
        """Simulate async readline.

        Returns:
            Next line from content
        """
        if self._position >= len(self.content):
            return ""
        end = self.content.find("\n", self._position)
        if end == -1:
            end = len(self.content)
        else:
            end += 1  # Include newline
        line = self.content[self._position : end]
        self._position = end
        return line

    async def readlines(self) -> list[str]:
        """Simulate async readlines.

        Returns:
            List of all lines
        """
        lines = []
        while True:
            line = await self.readline()
            if not line:
                break
            lines.append(line)
        return lines

    async def write(self, data: str) -> int:
        """Simulate async file write.

        Args:
            data: Content to write

        Returns:
            Number of characters written

        Raises:
            Any exception configured in write_side_effect
        """
        if self.write_side_effect is not None:
            raise self.write_side_effect
        self.written.append(data)
        return len(data)

    async def writelines(self, lines: list[str]) -> None:
        """Simulate async writelines.

        Args:
            lines: Lines to write
        """
        for line in lines:
            await self.write(line)

    async def seek(self, offset: int, whence: int = 0) -> int:
        """Simulate async seek.

        Args:
            offset: Seek offset
            whence: Seek origin (0=start, 1=current, 2=end)

        Returns:
            New position
        """
        if whence == 0:
            self._position = offset
        elif whence == 1:
            self._position += offset
        elif whence == 2:
            self._position = len(self.content) + offset
        return self._position

    async def tell(self) -> int:
        """Simulate async tell.

        Returns:
            Current position
        """
        return self._position

    async def close(self) -> None:
        """Simulate async close."""
        self._closed = True

    async def __aenter__(self) -> AsyncFileMock:
        """Enter async context."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Exit async context."""
        await self.close()
        return False

    @property
    def closed(self) -> bool:
        """Return whether file is closed."""
        return self._closed

    def get_written_content(self) -> str:
        """Get all written content as single string.

        Returns:
            Concatenated written content
        """
        return "".join(self.written)


def async_file_mock(
    content: str = "",
    path: str | Path = "",
    mode: str = "r",
) -> AsyncFileMock:
    """Create an async file mock.

    Convenience factory function for AsyncFileMock.

    Args:
        content: Initial file content (for read operations)
        path: Simulated file path
        mode: File mode

    Returns:
        Configured AsyncFileMock instance

    Example:
        ```python
        # For reading
        mock = async_file_mock(content="data", path="/tmp/input.txt")

        # For writing
        mock = async_file_mock(path="/tmp/output.txt", mode="w")
        ```
    """
    return AsyncFileMock(content=content, path=path, mode=mode)


@asynccontextmanager
async def mock_async_open(
    mocks: dict[str | Path, AsyncFileMock] | None = None,
    default_content: str = "",
) -> AsyncGenerator[Callable[..., AsyncFileMock], None]:
    """Context manager that provides a mock async open function.

    Args:
        mocks: Dictionary mapping paths to pre-configured mocks
        default_content: Default content for unmocked paths

    Yields:
        Mock open function

    Example:
        ```python
        async with mock_async_open({"/tmp/test.txt": async_file_mock("data")}) as aopen:
            async with aopen("/tmp/test.txt") as f:
                content = await f.read()
                assert content == "data"
        ```
    """
    mocks = mocks or {}

    def mock_open(path: str | Path, mode: str = "r") -> AsyncFileMock:
        path_key = str(path)
        if path_key in mocks:
            return mocks[path_key]
        return AsyncFileMock(content=default_content, path=path, mode=mode)

    yield mock_open


# =============================================================================
# Concurrent Test Utilities
# =============================================================================


@dataclass
class ConcurrentTestResult:
    """Result from concurrent test operations.

    Attributes:
        results: List of successful results
        exceptions: List of exceptions from failed tasks
        total: Total number of operations
        succeeded: Number of successful operations
        failed: Number of failed operations
        duration: Total duration in seconds
    """

    results: list[Any] = field(default_factory=list)
    exceptions: list[BaseException] = field(default_factory=list)
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    duration: float = 0.0

    @property
    def success_rate(self) -> float:
        """Return success rate as percentage."""
        if self.total == 0:
            return 0.0
        return (self.succeeded / self.total) * 100


class ConcurrentTestRunner:
    """Runner for concurrent async test operations.

    Provides utilities for testing concurrent behavior in ZERG orchestrator
    and launcher components.

    Example:
        ```python
        async def worker_task(worker_id: int) -> str:
            await asyncio.sleep(0.1)
            return f"Worker {worker_id} done"

        runner = ConcurrentTestRunner()
        result = await runner.run_concurrent(
            [worker_task(i) for i in range(5)],
            timeout=10.0,
        )

        assert result.succeeded == 5
        assert result.failed == 0
        ```
    """

    def __init__(
        self,
        max_concurrent: int | None = None,
    ) -> None:
        """Initialize the concurrent test runner.

        Args:
            max_concurrent: Maximum concurrent tasks (None for unlimited)
        """
        self.max_concurrent = max_concurrent
        self._semaphore: asyncio.Semaphore | None = None

    async def run_concurrent(
        self,
        coros: list[Coroutine[Any, Any, Any]],
        timeout: float = 60.0,
        return_exceptions: bool = True,
    ) -> ConcurrentTestResult:
        """Run multiple coroutines concurrently.

        Args:
            coros: List of coroutines to run
            timeout: Overall timeout for all operations
            return_exceptions: Whether to catch exceptions

        Returns:
            ConcurrentTestResult with outcomes

        Example:
            ```python
            result = await runner.run_concurrent([
                async_task_1(),
                async_task_2(),
                async_task_3(),
            ])
            assert result.succeeded >= 2
            ```
        """
        import time

        start_time = time.monotonic()

        if self.max_concurrent:
            self._semaphore = asyncio.Semaphore(self.max_concurrent)

        async def wrapped_coro(coro: Coroutine[Any, Any, Any]) -> Any:
            if self._semaphore:
                async with self._semaphore:
                    return await coro
            return await coro

        wrapped = [wrapped_coro(c) for c in coros]

        try:
            outcomes = await asyncio.wait_for(
                asyncio.gather(*wrapped, return_exceptions=return_exceptions),
                timeout=timeout,
            )
        except TimeoutError:
            outcomes = []

        result = ConcurrentTestResult(total=len(coros))

        for outcome in outcomes:
            if isinstance(outcome, BaseException):
                result.exceptions.append(outcome)
                result.failed += 1
            else:
                result.results.append(outcome)
                result.succeeded += 1

        result.duration = time.monotonic() - start_time
        return result

    async def run_sequential(
        self,
        coros: list[Coroutine[Any, Any, Any]],
        stop_on_error: bool = False,
    ) -> ConcurrentTestResult:
        """Run coroutines sequentially (for comparison with concurrent).

        Args:
            coros: List of coroutines to run
            stop_on_error: Whether to stop on first error

        Returns:
            ConcurrentTestResult with outcomes
        """
        import time

        start_time = time.monotonic()
        result = ConcurrentTestResult(total=len(coros))

        for coro in coros:
            try:
                outcome = await coro
                result.results.append(outcome)
                result.succeeded += 1
            except BaseException as e:  # noqa: BLE001 — intentional: test helper; collecting all errors for sequential runner
                result.exceptions.append(e)
                result.failed += 1
                if stop_on_error:
                    break

        result.duration = time.monotonic() - start_time
        return result


async def run_with_delay[T](
    coro: Coroutine[Any, Any, T],
    delay: float,
) -> T:
    """Run a coroutine after a delay.

    Useful for testing timing-dependent behavior.

    Args:
        coro: Coroutine to run
        delay: Delay in seconds before running

    Returns:
        Result of the coroutine

    Example:
        ```python
        # Simulate delayed task completion
        result = await run_with_delay(complete_task(), delay=1.0)
        ```
    """
    await asyncio.sleep(delay)
    return await coro


async def wait_for_condition(
    condition: Callable[[], bool] | Callable[[], Coroutine[Any, Any, bool]],
    timeout: float = 10.0,
    poll_interval: float = 0.1,
    message: str = "Condition not met",
) -> None:
    """Wait for a condition to become true.

    Useful for testing eventually-consistent behavior.

    Args:
        condition: Callable returning bool or async bool
        timeout: Maximum wait time
        poll_interval: Time between condition checks
        message: Error message if timeout

    Raises:
        AsyncTimeoutError: If condition not met within timeout

    Example:
        ```python
        # Wait for worker to be ready
        await wait_for_condition(
            lambda: worker.status == WorkerStatus.READY,
            timeout=5.0,
        )
        ```
    """
    import time

    start = time.monotonic()

    while True:
        result = condition()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return
        if time.monotonic() - start > timeout:
            raise AsyncTimeoutError(message=message, timeout=timeout)
        await asyncio.sleep(poll_interval)


# =============================================================================
# Mock Factory for ZERG-specific patterns
# =============================================================================


class ZergAsyncMockFactory:
    """Factory for creating ZERG-specific async mocks.

    Provides pre-configured mocks for common ZERG patterns like
    worker spawning, task execution, and orchestration.

    Example:
        ```python
        factory = ZergAsyncMockFactory()

        # Create mock worker process
        worker_mock = factory.create_worker_process(
            worker_id=0,
            exit_code=0,
        )

        # Create mock orchestrator
        orch_mock = factory.create_mock_launcher()
        ```
    """

    def create_worker_process(
        self,
        worker_id: int = 0,
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> AsyncSubprocessMock:
        """Create a mock worker subprocess.

        Args:
            worker_id: Worker ID
            exit_code: Exit code to return
            stdout: Stdout content
            stderr: Stderr content

        Returns:
            Configured AsyncSubprocessMock
        """
        return AsyncSubprocessMock(
            stdout=stdout or f"Worker {worker_id} completed",
            stderr=stderr,
            returncode=exit_code,
            pid=10000 + worker_id,
        )

    def create_mock_launcher(self) -> MagicMock:
        """Create a mock launcher with async methods.

        Returns:
            MagicMock configured for launcher interface
        """
        mock = MagicMock()
        mock.spawn = AsyncMock(return_value=MagicMock(success=True, error=None))
        mock.monitor = MagicMock(return_value="running")
        mock.terminate = MagicMock(return_value=True)
        mock.get_output = MagicMock(return_value="")
        return mock

    def create_mock_state_manager(self) -> MagicMock:
        """Create a mock state manager.

        Returns:
            MagicMock configured for StateManager interface
        """
        mock = MagicMock()
        mock.load = MagicMock(return_value={})
        mock.save = MagicMock()
        mock.get_task_status = MagicMock(return_value=None)
        mock.set_task_status = MagicMock()
        mock.get_task_retry_count = MagicMock(return_value=0)
        mock.increment_task_retry = MagicMock(return_value=1)
        return mock

    def create_task_execution_context(
        self,
        task_id: str = "TASK-001",
        success: bool = True,
    ) -> AsyncMockContextManager:
        """Create a context manager for task execution.

        Args:
            task_id: Task identifier
            success: Whether task should succeed

        Returns:
            AsyncMockContextManager for task execution
        """
        return AsyncMockContextManager(
            enter_value={"task_id": task_id, "status": "running"},
            exit_exception=None if success else RuntimeError("Task failed"),
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Context managers
    "AsyncMockContextManager",
    "AsyncMockContextManagerFactory",
    # Subprocess mocks
    "AsyncSubprocessMock",
    "async_subprocess_mock",
    "create_subprocess_exec_mock",
    # Timeout utilities
    "AsyncTimeoutError",
    "timeout_helper",
    "timeout_context",
    # Event loop fixtures
    "event_loop_fixture",
    "new_event_loop",
    # File mocks
    "AsyncFileMock",
    "async_file_mock",
    "mock_async_open",
    # Concurrent testing
    "ConcurrentTestResult",
    "ConcurrentTestRunner",
    "run_with_delay",
    "wait_for_condition",
    # ZERG-specific
    "ZergAsyncMockFactory",
]
