from pathlib import Path


GIF_FILTER = (
    "[0:v]format=rgba,split[a][b];"
    "[a]palettegen=reserve_transparent=1:transparency_color=ffffff:"
    "max_colors=256:stats_mode=single[p];"
    "[b][p]paletteuse=alpha_threshold=128:dither=sierra2_4a:new=1"
)


def _gif_output(output: Path) -> tuple[str, ...]:
    return ("-filter_complex", GIF_FILTER, "-fps_mode", "passthrough",
            "-loop", "0", str(output))


def video_to_gif_command(source: Path, output: Path) -> tuple[str, ...]:
    return (
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostats",
        "-y",
        "-c:v",
        "libvpx-vp9",
        "-i",
        str(source),
        *_gif_output(output),
    )


def frames_to_gif_command(
    frames_dir: Path, output: Path, frame_rate: str,
) -> tuple[str, ...]:
    return (
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats", "-y",
        "-framerate", frame_rate, "-i", str(frames_dir / "%06d.png"),
        *_gif_output(output),
    )
