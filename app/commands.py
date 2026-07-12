from pathlib import Path


def video_to_gif_command(source: Path, output: Path) -> tuple[str, ...]:
    return (
        "ffmpeg",
        "-y",
        "-c:v",
        "libvpx-vp9",
        "-i",
        str(source),
        "-filter_complex",
        "[0:v]format=rgba,split[a][b];"
        "[a]palettegen=reserve_transparent=1:transparency_color=ffffff[p];"
        "[b][p]paletteuse=alpha_threshold=128",
        str(output),
    )

