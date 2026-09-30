"""Render TGS frames in an isolated, cancellable worker process."""

import json
import math
import sys
from fractions import Fraction
from pathlib import Path

from lottie.exporters.cairo import PngRenderer
from lottie.parsers.tgs import parse_tgs


def render(source: Path, destination: Path) -> None:
    animation = parse_tgs(str(source))
    rate = animation.frame_rate
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError("Invalid animation frame rate")
    start = math.ceil(animation.in_point)
    end = math.ceil(animation.out_point)
    if end <= start:
        raise ValueError("Animation contains no frames")
    destination.mkdir()
    # Lottie's out_point is exclusive. Keep every source frame and its geometry.
    with PngRenderer(animation, 96) as renderer:
        for index, frame in enumerate(range(start, end)):
            with (destination / f"{index:06d}.png").open("wb") as stream:
                renderer.serialize(frame, stream)
    (destination / "timing.json").write_text(
        json.dumps({"frame_rate": str(Fraction(str(rate)))}), encoding="utf-8",
    )


if __name__ == "__main__":
    render(Path(sys.argv[1]), Path(sys.argv[2]))
