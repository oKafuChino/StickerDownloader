from pathlib import Path

import pytest

from app.database import AccessRepository


@pytest.fixture
async def repository(tmp_path: Path):
    repo = AccessRepository(tmp_path / "test.sqlite3")
    await repo.initialize()
    yield repo
    await repo.close()

