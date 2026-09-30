import gzip
import io
import json
import shutil
import subprocess
import zipfile

import pytest
from aiohttp.test_utils import TestClient, TestServer
from PIL import Image, ImageChops, ImageStat

from app.converters import ConversionService
from app.downloads import TemporaryDownloadService
from app.models import StickerAsset, StickerKind
from app.packs import create_sticker_pack_archive
from app.workspace import task_workspace


def write_tgs(path, fps):
    animation = {
        "v": "5.7.4", "fr": fps, "ip": 0, "op": fps,
        "w": 64, "h": 64, "ddd": 0, "assets": [],
        "layers": [{
            "ddd": 0, "ind": 1, "ty": 4, "nm": "moving square", "sr": 1,
            "ks": {
                "o": {"a": 0, "k": 100}, "r": {"a": 0, "k": 0},
                "p": {"a": 1, "k": [
                    {"t": 0, "s": [10, 32, 0], "e": [54, 32, 0],
                     "o": {"x": 0, "y": 0}, "i": {"x": 1, "y": 1}},
                    {"t": fps, "s": [54, 32, 0]},
                ]},
                "a": {"a": 0, "k": [0, 0, 0]},
                "s": {"a": 0, "k": [100, 100, 100]},
            },
            "shapes": [
                {"ty": "rc", "p": {"a": 0, "k": [0, 0]},
                 "s": {"a": 0, "k": [12, 12]}, "r": {"a": 0, "k": 0}},
                {"ty": "fl", "c": {"a": 0, "k": [1, 0, 0, 1]},
                 "o": {"a": 0, "k": 100}, "r": 1},
            ],
            "ip": 0, "op": fps, "st": 0, "bm": 0,
        }],
    }
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        json.dump(animation, stream)


def assert_animation(image, frames, duration=1000):
    assert image.size == (64, 64)
    assert image.n_frames == frames
    assert image.info["loop"] == 0
    elapsed = 0
    contents = []
    for index in range(image.n_frames):
        image.seek(index)
        elapsed += image.info["duration"]
        frame = image.convert("RGBA")
        assert frame.getpixel((0, 0))[3] == 0
        contents.append(frame.tobytes())
    assert abs(elapsed - duration) <= 10
    assert contents[0] != contents[-1]


@pytest.mark.integration
@pytest.mark.parametrize("fps", [30, 60])
async def test_tgs_retains_dimensions_frames_timing_and_alpha(tmp_path, fps):
    source = tmp_path / "source.tgs"
    write_tgs(source, fps)
    output = await ConversionService(1).convert(
        asset=StickerAsset("a", "a", StickerKind.ANIMATED),
        source=source, task_dir=tmp_path,
    )
    with Image.open(output) as image:
        assert_animation(image, fps)
        image.seek(0)
        assert image.convert("RGBA").getpixel((10, 32)) == (255, 0, 0, 255)
        image.seek(fps - 1)
        assert image.convert("RGBA").getpixel((10, 32))[3] == 0
    assert not (tmp_path / "frames").exists()


async def test_static_png_preserves_decoded_pixels_and_partial_alpha(tmp_path):
    source = tmp_path / "source.webp"
    original = Image.new("RGBA", (512, 256))
    original.putdata([(x % 256, y, (x + y) % 256, (x + 2 * y) % 256)
                      for y in range(256) for x in range(512)])
    original.save(source, "WEBP", lossless=True, exact=True)
    with Image.open(source) as image:
        expected = image.convert("RGBA").tobytes()
    output = await ConversionService(1).convert(
        asset=StickerAsset("a", "a", StickerKind.STATIC),
        source=source, task_dir=tmp_path,
    )
    with Image.open(output) as image:
        assert image.size == (512, 256)
        assert image.mode == "RGBA"
        assert image.tobytes() == expected


@pytest.mark.integration
async def test_mixed_pack_download_link_serves_converted_media(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    Image.new("RGBA", (64, 64), (20, 80, 160, 128)).save(inputs / "static.webp", "WEBP")
    write_tgs(inputs / "animated.tgs", 30)
    for index in range(10):
        frame = Image.new("RGBA", (64, 64))
        for y in range(8, 56):
            for x in range(8, 56):
                frame.putpixel((x, y), (x * 4, y * 4, index * 20, 255))
        frame.save(inputs / f"{index:03d}.png")
    subprocess.run([
        "ffmpeg", "-loglevel", "error", "-y", "-framerate", "10",
        "-i", str(inputs / "%03d.png"), "-c:v", "libvpx-vp9",
        "-lossless", "1", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0",
        str(inputs / "video.webm"),
    ], check=True, capture_output=True)
    assets = [StickerAsset(name, name, kind) for name, kind in [
        ("static.webp", StickerKind.STATIC), ("animated.tgs", StickerKind.ANIMATED),
        ("video.webm", StickerKind.VIDEO),
    ]]

    async def download(asset, destination):
        shutil.copyfile(inputs / asset.file_id, destination)

    service = TemporaryDownloadService(root=tmp_path, public_base_url="https://example.test")
    try:
        async with task_workspace(tmp_path / "tasks") as task_dir:
            archive = await create_sticker_pack_archive(
                assets=assets, task_dir=task_dir, download=download,
                converter=ConversionService(1),
            )
            link = await service.publish(archive, filename="converted.zip")
        assert not task_dir.exists()
        async with TestClient(TestServer(service.application())) as client:
            response = await client.get(f"/downloads/{link.token}")
            assert response.status == 200
            with zipfile.ZipFile(io.BytesIO(await response.read())) as bundle:
                assert bundle.namelist() == ["001.png", "002.gif", "003.gif"]
                assert bundle.testzip() is None
                with Image.open(io.BytesIO(bundle.read("001.png"))) as png:
                    with Image.open(inputs / "static.webp") as source:
                        assert png.tobytes() == source.convert("RGBA").tobytes()
                with Image.open(io.BytesIO(bundle.read("002.gif"))) as gif:
                    assert_animation(gif, 30)
                with Image.open(io.BytesIO(bundle.read("003.gif"))) as gif:
                    assert_animation(gif, 10)
                    gif.seek(0)
                    actual = gif.convert("RGB").crop((12, 12, 52, 52))
                    with Image.open(inputs / "000.png") as frame:
                        expected = frame.convert("RGB").crop((12, 12, 52, 52))
                    assert max(ImageStat.Stat(ImageChops.difference(actual, expected)).mean) < 12
    finally:
        await service.stop()
