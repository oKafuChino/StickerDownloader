import asyncio
from pathlib import Path

from PIL import Image

from app.commands import video_to_gif_command
from app.models import StickerAsset, StickerKind
from app.processes import ProcessExecutionError, run_checked_subprocess


class ConversionError(RuntimeError):
    pass


class ConversionService:
    def __init__(self, concurrency: int) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        self._semaphore = asyncio.Semaphore(concurrency)

    async def convert(
        self,
        *,
        asset: StickerAsset,
        source: Path,
        task_dir: Path,
    ) -> Path:
        async with self._semaphore:
            if asset.kind is StickerKind.STATIC:
                output = task_dir / "result.png"
                await asyncio.to_thread(self._convert_static, source, output)
            elif asset.kind is StickerKind.ANIMATED:
                output = task_dir / "result.gif"
                await self._run_command("lottie_convert.py", str(source), str(output))
            else:
                output = task_dir / "result.gif"
                await self._run_command(*video_to_gif_command(source, output))

            if not output.is_file() or output.stat().st_size == 0:
                raise ConversionError("Converter did not create a valid output file")
            return output

    @staticmethod
    def source_suffix(kind: StickerKind) -> str:
        return {
            StickerKind.STATIC: ".webp",
            StickerKind.ANIMATED: ".tgs",
            StickerKind.VIDEO: ".webm",
        }[kind]

    @staticmethod
    def _convert_static(source: Path, output: Path) -> None:
        try:
            with Image.open(source) as image:
                image.convert("RGBA").save(output, "PNG")
        except Exception as exc:
            raise ConversionError(f"Pillow conversion failed: {exc}") from exc

    @staticmethod
    async def _run_command(*command: str) -> None:
        try:
            await run_checked_subprocess(*command)
        except ProcessExecutionError as exc:
            raise ConversionError(str(exc)) from exc
