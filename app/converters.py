import asyncio
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

from app.commands import frames_to_gif_command, video_to_gif_command
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
                worker = asyncio.create_task(
                    asyncio.to_thread(self._convert_static, source, output)
                )
                try:
                    await asyncio.shield(worker)
                except asyncio.CancelledError:
                    try:
                        await worker
                    finally:
                        raise
            elif asset.kind is StickerKind.ANIMATED:
                output = task_dir / "result.gif"
                frames_dir = task_dir / "frames"
                try:
                    await self._run_command(
                        sys.executable, str(Path(__file__).with_name("render_tgs.py")),
                        str(source), str(frames_dir),
                    )
                    timing = json.loads((frames_dir / "timing.json").read_text())
                    await self._run_command(
                        *frames_to_gif_command(frames_dir, output, timing["frame_rate"])
                    )
                finally:
                    if frames_dir.exists():
                        shutil.rmtree(frames_dir)
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
