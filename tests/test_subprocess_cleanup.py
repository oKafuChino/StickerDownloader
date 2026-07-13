import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

from app.processes import ProcessExecutionError, run_checked_subprocess


ERROR_LIMIT = 64 * 1024


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
        self.started.set()
        if not self.terminated and not self.killed:
            await asyncio.Future()
        self.returncode = -15
        return self.returncode


class FailingProcess(FakeProcess):
    async def communicate(self):
        raise RuntimeError("pipe read failed")

    async def wait(self) -> int:
        if not self.terminated:
            raise RuntimeError("process wait failed")
        return await super().wait()


class CompletedProcess:
    def __init__(self, returncode: int, error_output: bytes) -> None:
        self.returncode = returncode
        self.error_output = error_output

    async def communicate(self):
        return b"", self.error_output

    async def wait(self) -> int:
        return self.returncode


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

    async def test_wait_failure_terminates_child_process(self) -> None:
        process = FailingProcess()
        with patch(
            "app.processes.asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=process),
        ):
            with self.assertRaisesRegex(RuntimeError, "process wait failed"):
                await run_checked_subprocess("converter")

        self.assertTrue(process.terminated)
        self.assertFalse(process.killed)

    async def test_failure_diagnostics_are_disk_backed_and_bounded(self) -> None:
        prefix = b"truncated-prefix\n"
        tail = b"actionable-tail\n"
        error_output = prefix + (b"x" * ERROR_LIMIT) + tail
        captured: dict[str, object] = {}

        async def start_process(*command, stdout, stderr, **kwargs):
            captured["stdout"] = stdout
            captured["stderr"] = stderr
            if hasattr(stderr, "write"):
                stderr.write(error_output)
                stderr.flush()
            return CompletedProcess(7, error_output)

        with patch(
            "app.processes.asyncio.create_subprocess_exec",
            new=start_process,
        ):
            with self.assertRaises(ProcessExecutionError) as raised:
                await run_checked_subprocess("converter")

        details = str(raised.exception)
        self.assertIs(captured["stdout"], asyncio.subprocess.DEVNULL)
        self.assertIsNot(captured["stderr"], asyncio.subprocess.PIPE)
        self.assertIn("actionable-tail", details)
        self.assertNotIn("truncated-prefix", details)

    async def test_converter_environment_excludes_bot_secrets(self) -> None:
        captured: dict[str, object] = {}

        async def start_process(*command, stdout, stderr, env=None):
            captured["env"] = env
            return CompletedProcess(0, b"")

        parent_environment = {
            "PATH": "/usr/local/bin:/usr/bin",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TZ": "UTC",
            "BOT_TOKEN": "123456:secret",
            "OWNER_TELEGRAM_ID": "42",
            "DATABASE_PATH": "/data/bot.sqlite3",
            "HTTPS_PROXY": "http://proxy.invalid",
            "PYTHONPATH": "/untrusted",
        }
        with patch.dict(os.environ, parent_environment, clear=True), patch(
            "app.processes.asyncio.create_subprocess_exec",
            new=start_process,
        ):
            await run_checked_subprocess("converter")

        self.assertEqual(
            captured["env"],
            {
                "PATH": "/usr/local/bin:/usr/bin",
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "TZ": "UTC",
                "HOME": "/tmp",
                "TMPDIR": "/tmp",
            },
        )


if __name__ == "__main__":
    unittest.main()
