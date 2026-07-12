import unittest
from pathlib import Path


class UpdateScriptContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.script = Path("update.sh").read_text(encoding="utf-8")

    def test_update_entrypoint_is_safe_and_health_checked(self) -> None:
        self.assertIn("set -Eeuo pipefail", self.script)
        self.assertIn('[[ -d "$INSTALL_DIR/.git" ]]', self.script)
        self.assertIn('[[ -f "$INSTALL_DIR/.env" ]]', self.script)
        self.assertIn("oKafuChino/StickerDownloader", self.script)
        self.assertIn("pull --ff-only origin main", self.script)
        self.assertIn(
            "docker compose up -d --build --wait --wait-timeout 60",
            self.script,
        )
        self.assertIn("docker compose ps", self.script)

    def test_update_does_not_rewrite_configuration_or_local_changes(self) -> None:
        self.assertNotIn("BOT_TOKEN=", self.script)
        self.assertNotIn("git reset", self.script)
        self.assertNotIn("git stash", self.script)
        self.assertNotIn("docker compose down", self.script)


if __name__ == "__main__":
    unittest.main()
