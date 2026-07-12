import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.workspace import task_workspace


class WorkspaceCleanupTest(unittest.IsolatedAsyncioTestCase):
    async def test_cleanup_failure_is_logged_without_masking_result(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            with self.assertLogs("app.workspace", level=logging.WARNING) as captured:
                with patch(
                    "app.workspace.shutil.rmtree",
                    side_effect=OSError("permission denied"),
                ):
                    async with task_workspace(Path(root)):
                        pass

        self.assertIn("Failed to remove task workspace", captured.output[0])


if __name__ == "__main__":
    unittest.main()

