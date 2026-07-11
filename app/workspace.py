import shutil
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path


@asynccontextmanager
async def task_workspace(root: Path) -> AsyncIterator[Path]:
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="conversion-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)

