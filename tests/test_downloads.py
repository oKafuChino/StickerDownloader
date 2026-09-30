import time
from pathlib import Path

import pytest

from app.downloads import TemporaryDownloadService


@pytest.mark.asyncio
async def test_publish_moves_archive_and_expires_it(tmp_path: Path) -> None:
    archive = tmp_path / "source.zip"
    archive.write_bytes(b"zip-data")
    service = TemporaryDownloadService(
        root=tmp_path,
        public_base_url="https://downloads.example.test",
        ttl_seconds=1,
    )

    link = await service.publish(archive, filename="pack.zip")

    assert not archive.exists()
    assert link.url.startswith("https://downloads.example.test/downloads/")
    assert link.expires_at > time.time()
    assert len(list((tmp_path / "downloads").glob("*.zip"))) == 1

    await service._remove_expired(force=True)

    assert not list((tmp_path / "downloads").glob("*.zip"))


def test_download_service_requires_public_url(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        TemporaryDownloadService(root=tmp_path, public_base_url="")
