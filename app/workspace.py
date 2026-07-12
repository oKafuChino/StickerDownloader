import logging
import shutil
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path


logger = logging.getLogger(__name__)


@asynccontextmanager
async def task_workspace(root: Path) -> AsyncIterator[Path]:
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="conversion-", dir=root))
    try:
        yield path
    finally:
        try:
            shutil.rmtree(path)
        except OSError:
            logger.warning("Failed to remove task workspace: %s", path, exc_info=True)
