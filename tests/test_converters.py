import gzip
import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from app.converters import ConversionService
from app.models import StickerAsset, StickerKind
from app.workspace import task_workspace


@pytest.mark.asyncio
async def test_static_webp_becomes_png(tmp_path: Path) -> None:
    source = tmp_path / "sticker.webp"
    Image.new("RGBA", (16, 16), (255, 0, 0, 128)).save(source, "WEBP")
    output = await ConversionService(1).convert(
        asset=StickerAsset("file", "unique", StickerKind.STATIC),
        source=source,
        task_dir=tmp_path,
    )

    assert output.suffix == ".png"
    with Image.open(output) as image:
        assert image.mode == "RGBA"


@pytest.mark.asyncio
async def test_workspace_is_removed_after_exception(tmp_path: Path) -> None:
    created: Path
    with pytest.raises(RuntimeError):
        async with task_workspace(tmp_path) as created:
            raise RuntimeError("conversion failed")

    assert not created.exists()


def test_source_suffix_matches_sticker_kind() -> None:
    assert ConversionService.source_suffix(StickerKind.STATIC) == ".webp"
    assert ConversionService.source_suffix(StickerKind.ANIMATED) == ".tgs"
    assert ConversionService.source_suffix(StickerKind.VIDEO) == ".webm"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tgs_becomes_readable_gif(tmp_path: Path) -> None:
    source = tmp_path / "sticker.tgs"
    animation = {
        "v": "5.7.4",
        "fr": 30,
        "ip": 0,
        "op": 30,
        "w": 32,
        "h": 32,
        "nm": "dot",
        "ddd": 0,
        "assets": [],
        "layers": [
            {
                "ddd": 0,
                "ind": 1,
                "ty": 4,
                "nm": "dot",
                "sr": 1,
                "ks": {
                    "o": {"a": 0, "k": 100},
                    "r": {"a": 0, "k": 0},
                    "p": {"a": 0, "k": [0, 0, 0]},
                    "a": {"a": 0, "k": [0, 0, 0]},
                    "s": {"a": 0, "k": [100, 100, 100]},
                },
                "shapes": [
                    {
                        "ty": "el",
                        "p": {"a": 0, "k": [16, 16]},
                        "s": {"a": 0, "k": [16, 16]},
                        "nm": "circle",
                    },
                    {
                        "ty": "fl",
                        "c": {"a": 0, "k": [1, 0, 0, 1]},
                        "o": {"a": 0, "k": 100},
                        "r": 1,
                        "nm": "fill",
                    },
                ],
                "ip": 0,
                "op": 30,
                "st": 0,
                "bm": 0,
            }
        ],
    }
    with gzip.open(source, "wt", encoding="utf-8") as stream:
        json.dump(animation, stream)

    output = await ConversionService(1).convert(
        asset=StickerAsset("file", "unique", StickerKind.ANIMATED),
        source=source,
        task_dir=tmp_path,
    )

    assert output.suffix == ".gif"
    with Image.open(output) as image:
        assert image.format == "GIF"
        assert image.convert("RGBA").getpixel((0, 0))[3] == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_transparent_webm_becomes_transparent_gif(tmp_path: Path) -> None:
    frame = tmp_path / "transparent.png"
    source = tmp_path / "sticker.webm"
    image = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    for x in range(8, 24):
        for y in range(8, 24):
            image.putpixel((x, y), (255, 0, 0, 255))
    image.save(frame, "PNG")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-framerate",
            "10",
            "-i",
            str(frame),
            "-t",
            "1",
            "-c:v",
            "libvpx-vp9",
            "-pix_fmt",
            "yuva420p",
            "-auto-alt-ref",
            "0",
            "-an",
            str(source),
        ],
        check=True,
        capture_output=True,
    )

    output = await ConversionService(1).convert(
        asset=StickerAsset("file", "unique", StickerKind.VIDEO),
        source=source,
        task_dir=tmp_path,
    )

    assert output.suffix == ".gif"
    with Image.open(output) as image:
        assert image.format == "GIF"
        assert image.convert("RGBA").getpixel((0, 0))[3] == 0
