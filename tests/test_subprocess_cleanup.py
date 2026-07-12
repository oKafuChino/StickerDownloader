import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.processes import run_checked_subprocess


class FakeProcess:
    def __init__(self) -> None:
        self.returncode = None
        self.started = asyncio.Event()
        self.terminated = False
        self.killed = False

    async def communicate(self):
        self.started.set()
        await asyncio.Future()

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        self.returncode = -15
        return self.returncode


class FailingProcess(FakeProcess):
    async def communicate(self):
        raise RuntimeError("pipe read failed")


class SubprocessCleanupTest(unittest.IsolatedAsyncioTestCase):
    async def test_cancellation_terminates_child_process(self) -> None:
        process = FakeProcess()
        with patch(
            "app.processes.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ):
            task = asyncio.create_task(run_checked_subprocess("converter"))
            await process.started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        self.assertTrue(process.terminated)
        self.assertFalse(process.killed)

    async def test_communication_failure_terminates_child_process(self) -> None:
        process = FailingProcess()
        with patch(
            "app.processes.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ):
            with self.assertRaisesRegex(RuntimeError, "pipe read failed"):
                await run_checked_subprocess("converter")

        self.assertTrue(process.terminated)
        self.assertFalse(process.killed)


if __name__ == "__main__":
    unittest.main()
