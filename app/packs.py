import asyncio
import re
import zipfile
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from urllib.parse import unquote, urlsplit

from app.converters import ConversionService
from app.models import StickerAsset


MAX_ARCHIVE_BYTES = 200 * 1024 * 1024
STICKER_SET_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


class StickerPackError(RuntimeError):
    pass


class StickerPackTooLargeError(StickerPackError):
    pass


def parse_sticker_set_name(value: str) -> str:
    parts = urlsplit(value.strip())
    if parts.scheme.lower() not in {"http", "https"}:
        raise ValueError("Sticker pack link must use HTTP or HTTPS")
    if (parts.hostname or "").lower() not in {"t.me", "www.t.me"}:
        raise ValueError("Sticker pack link must use t.me")

    path_parts = [unquote(part) for part in parts.path.split("/") if part]
    if len(path_parts) != 2 or path_parts[0].lower() != "addstickers":
        raise ValueError("Sticker pack link must use /addstickers/<name>")

    name = path_parts[1]
    if not STICKER_SET_NAME_PATTERN.fullmatch(name):
        raise ValueError("Sticker pack name contains unsupported characters")
    return name


async def create_sticker_pack_archive(
    *,
    assets: Sequence[StickerAsset],
    task_dir: Path,
    download: Callable[[StickerAsset, Path], Awaitable[None]],
    converter: ConversionService,
    max_archive_bytes: int = MAX_ARCHIVE_BYTES,
    progress: Callable[[int, int, str], Awaitable[None]] | None = None,
) -> Path:
    if not assets:
        raise StickerPackError("Sticker pack is empty")
    if max_archive_bytes < 1:
        raise ValueError("max_archive_bytes must be at least 1")

    content_dir = task_dir / "pack"
    content_dir.mkdir()
    files: list[Path] = []
    converted_bytes = 0
    width = max(3, len(str(len(assets))))

    for index, asset in enumerate(assets, start=1):
        suffix = ConversionService.source_suffix(asset.kind)
        sticker_dir = content_dir / f"{index:0{width}d}"
        sticker_dir.mkdir()
        destination = sticker_dir / f"source{suffix}"
        if progress is not None:
            await progress(index - 1, len(assets), "downloading")
        await download(asset, destination)
        if not destination.is_file() or destination.stat().st_size == 0:
            raise StickerPackError(f"Telegram did not provide sticker {index}")
        if progress is not None:
            await progress(index - 1, len(assets), "converting")
        output = await converter.convert(
            asset=asset, source=destination, task_dir=sticker_dir,
        )
        if not output.is_file() or output.stat().st_size == 0:
            raise StickerPackError(f"Converter did not provide sticker {index}")
        converted_bytes += output.stat().st_size
        if converted_bytes >= max_archive_bytes:
            raise StickerPackTooLargeError(
                "Sticker pack contents exceed the temporary archive size limit"
            )
        exported = content_dir / f"{index:0{width}d}{output.suffix}"
        output.replace(exported)
        destination.unlink()
        sticker_dir.rmdir()
        files.append(exported)
        if progress is not None:
            await progress(index, len(assets), "converted")

    if progress is not None:
        await progress(len(assets), len(assets), "packing")
    archive = task_dir / "sticker-pack.zip"
    worker = asyncio.create_task(asyncio.to_thread(_write_archive, archive, files))
    try:
        await asyncio.shield(worker)
    except asyncio.CancelledError:
        # Finish file I/O before the workspace is removed.
        try:
            await worker
        finally:
            raise
    if archive.stat().st_size > max_archive_bytes:
        raise StickerPackTooLargeError(
            "Sticker pack archive exceeds the temporary archive size limit"
        )
    return archive


def _write_archive(archive: Path, files: Sequence[Path]) -> None:
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
        for file in files:
            bundle.write(file, arcname=file.name)
