import zipfile
from pathlib import Path

import pytest

from app.models import StickerAsset, StickerKind
from app.packs import (
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
async def test_create_archive_preserves_original_sticker_formats(
    tmp_path: Path,
) -> None:
    assets = [
        StickerAsset("static", "one", StickerKind.STATIC),
        StickerAsset("animated", "two", StickerKind.ANIMATED),
        StickerAsset("video", "three", StickerKind.VIDEO),
    ]

    async def download(asset: StickerAsset, destination: Path) -> None:
        destination.write_bytes(asset.file_id.encode("ascii"))

    archive = await create_sticker_pack_archive(
        assets=assets,
        task_dir=tmp_path,
        download=download,
    )

    with zipfile.ZipFile(archive) as bundle:
        assert bundle.namelist() == ["001.webp", "002.tgs", "003.webm"]
        assert bundle.read("001.webp") == b"static"
        assert bundle.read("002.tgs") == b"animated"
        assert bundle.read("003.webm") == b"video"


@pytest.mark.asyncio
async def test_create_archive_rejects_oversized_output(tmp_path: Path) -> None:
    async def download(asset: StickerAsset, destination: Path) -> None:
        destination.write_bytes(b"large-output")

    with pytest.raises(StickerPackTooLargeError):
        await create_sticker_pack_archive(
            assets=[StickerAsset("file", "one", StickerKind.STATIC)],
            task_dir=tmp_path,
            download=download,
            max_archive_bytes=1,
        )
