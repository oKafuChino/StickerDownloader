import unittest
from pathlib import Path

from app.commands import video_to_gif_command


class VideoTransparencyContractTest(unittest.TestCase):
    def test_webm_conversion_preserves_vp9_alpha(self) -> None:
        command = video_to_gif_command(Path("source.webm"), Path("result.gif"))
        filter_graph = command[command.index("-filter_complex") + 1]

        self.assertEqual(command[command.index("-c:v") + 1], "libvpx-vp9")
        self.assertLess(command.index("-c:v"), command.index("-i"))
        self.assertIn("[0:v]format=rgba,split[a][b]", filter_graph)
        self.assertIn("palettegen=reserve_transparent=1", filter_graph)
        self.assertIn("paletteuse=alpha_threshold=128", filter_graph)


if __name__ == "__main__":
    unittest.main()
