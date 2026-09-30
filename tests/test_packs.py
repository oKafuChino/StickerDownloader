import asyncio
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.models import StickerAsset, StickerKind
from app.packs import (
    StickerPackError,
    StickerPackTooLargeError,
    create_sticker_pack_archive,
    parse_sticker_set_name,
)


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        ("https://t.me/addstickers/Cats_123", "Cats_123"),
        ("http://www.t.me/addstickers/example", "example"),
        ("https://t.me/addstickers/example?start=1", "example"),
    ],
)
def test_parse_sticker_set_name(link: str, expected: str) -> None:
    assert parse_sticker_set_name(link) == expected


@pytest.mark.parametrize(
    "link",
    [
        "example",
        "https://example.com/addstickers/test",
        "https://t.me/test",
        "https://t.me/addstickers/test/extra",
        "https://t.me/addstickers/bad-name",
    ],
)
def test_parse_sticker_set_name_rejects_invalid_links(link: str) -> None:
    with pytest.raises(ValueError):
        parse_sticker_set_name(link)


@pytest.mark.asyncio
async def test_create_archive_contains_converted_files_in_order(
    tmp_path: Path,
) -> None:
    assets = [
        StickerAsset("static", "one", StickerKind.STATIC),
        StickerAsset("animated", "two", StickerKind.ANIMATED),
        StickerAsset("video", "three", StickerKind.VIDEO),
    ]

    async def download(asset: StickerAsset, destination: Path) -> None:
        destination.write_bytes(asset.file_id.encode("ascii"))

    async def convert(*, asset, source, task_dir):
        assert source.parent == task_dir
        assert source.read_bytes() == asset.file_id.encode("ascii")
        suffix = ".png" if asset.kind is StickerKind.STATIC else ".gif"
        result = task_dir / f"result{suffix}"
        result.write_bytes(b"converted-" + asset.file_id.encode("ascii"))
        return result

    converter = AsyncMock()
    converter.convert.side_effect = convert
    archive = await create_sticker_pack_archive(
        assets=assets,
        task_dir=tmp_path,
        download=download,
        converter=converter,
    )

    with zipfile.ZipFile(archive) as bundle:
        assert bundle.namelist() == ["001.png", "002.gif", "003.gif"]
        assert bundle.read("001.png") == b"converted-static"
        assert bundle.read("002.gif") == b"converted-animated"
        assert bundle.read("003.gif") == b"converted-video"
    assert converter.convert.await_count == 3
    directories = [call.kwargs["task_dir"] for call in converter.convert.await_args_list]
    assert len(set(directories)) == 3
    assert all(not directory.exists() for directory in directories)


@pytest.mark.asyncio
async def test_create_archive_rejects_oversized_output(tmp_path: Path) -> None:
    async def download(asset: StickerAsset, destination: Path) -> None:
        destination.write_bytes(b"small-source")

    async def convert(*, asset, source, task_dir):
        result = task_dir / "result.gif"
        result.write_bytes(b"x" * 1024)
        return result

    converter = AsyncMock()
    converter.convert.side_effect = convert

    with pytest.raises(StickerPackTooLargeError):
        await create_sticker_pack_archive(
            assets=[StickerAsset("file", "one", StickerKind.STATIC)],
            task_dir=tmp_path,
            download=download,
            converter=converter,
            max_archive_bytes=512,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [RuntimeError("failed"), asyncio.CancelledError()])
async def test_failed_conversion_leaves_no_archive_or_workspace(tmp_path, failure):
    from app.workspace import task_workspace

    async def download(asset, destination):
        destination.write_bytes(b"source")

    converter = AsyncMock()
    converter.convert.side_effect = failure
    with pytest.raises(type(failure)):
        async with task_workspace(tmp_path) as task_dir:
            await create_sticker_pack_archive(
                assets=[StickerAsset("file", "one", StickerKind.STATIC)],
                task_dir=task_dir, download=download, converter=converter,
            )
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_empty_pack_is_rejected(tmp_path):
    download = AsyncMock()
    converter = AsyncMock()
    with pytest.raises(StickerPackError, match="empty"):
        await create_sticker_pack_archive(
            assets=[], task_dir=tmp_path, download=download, converter=converter,
        )
    download.assert_not_awaited()
    converter.convert.assert_not_awaited()
