import asyncio


class ProcessExecutionError(RuntimeError):
    pass


async def run_checked_subprocess(*command: str) -> None:
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise ProcessExecutionError(f"Unable to start {command[0]}: {exc}") from exc

    try:
        _, stderr = await process.communicate()
    except BaseException:
        await _stop_process(process)
        raise

    if process.returncode != 0:
        details = stderr.decode("utf-8", errors="replace").strip()
        raise ProcessExecutionError(
            f"{command[0]} exited with {process.returncode}: {details}"
        )


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
