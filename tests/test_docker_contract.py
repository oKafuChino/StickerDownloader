import unittest
from pathlib import Path


class DockerRuntimeContractTest(unittest.TestCase):
    def test_build_verifies_media_runtime_capabilities(self) -> None:
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

        self.assertIn("command -v lottie_convert.py", dockerfile)
        self.assertIn("ffmpeg -hide_banner -decoders", dockerfile)
        self.assertIn("libvpx-vp9", dockerfile)

    def test_compose_does_not_publish_ports(self) -> None:
        compose = Path("compose.yaml").read_text(encoding="utf-8")

        self.assertNotIn("ports:", compose)
        self.assertIn("restart: unless-stopped", compose)

    def test_installer_waits_for_container_health(self) -> None:
        compose = Path("compose.yaml").read_text(encoding="utf-8")
        installer = Path("install.sh").read_text(encoding="utf-8")

        self.assertIn("healthcheck:", compose)
        self.assertIn("--wait --wait-timeout 60", installer)
        self.assertEqual(installer.count("--wait --wait-timeout 60"), 2)


if __name__ == "__main__":
    unittest.main()
