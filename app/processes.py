import asyncio
import os
import tempfile
from collections.abc import Mapping
from typing import BinaryIO


MAX_ERROR_OUTPUT_BYTES = 64 * 1024
SUBPROCESS_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "TZ")


class ProcessExecutionError(RuntimeError):
    pass


async def run_checked_subprocess(*command: str) -> None:
    with tempfile.TemporaryFile(mode="w+b") as error_stream:
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=error_stream,
                env=_subprocess_environment(os.environ),
            )
        except OSError as exc:
            raise ProcessExecutionError(
                f"Unable to start {command[0]}: {exc}"
            ) from exc

        try:
            await process.wait()
        except BaseException:
            await _stop_process(process)
            raise

        if process.returncode != 0:
            details = _read_error_tail(error_stream)
            raise ProcessExecutionError(
                f"{command[0]} exited with {process.returncode}: {details}"
            )


def _subprocess_environment(environ: Mapping[str, str]) -> dict[str, str]:
    environment = {
        key: environ[key]
        for key in SUBPROCESS_ENV_KEYS
        if key in environ
    }
    environment.setdefault("PATH", os.defpath)
    environment["HOME"] = "/tmp"
    environment["TMPDIR"] = "/tmp"
    return environment


def _read_error_tail(stream: BinaryIO) -> str:
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(max(0, size - MAX_ERROR_OUTPUT_BYTES))
    return stream.read(MAX_ERROR_OUTPUT_BYTES).decode(
        "utf-8", errors="replace"
    ).strip()


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        process.terminate()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
