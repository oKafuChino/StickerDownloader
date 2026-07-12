import ast
import sqlite3
import unittest
from pathlib import Path


def string_constant(path: str, name: str) -> str:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value
    raise AssertionError(f"missing string constant {name}")


class DatabaseSchemaContractTest(unittest.TestCase):
    def test_schema_allows_reauthorization_after_revocation(self) -> None:
        schema = string_constant("app/database.py", "SCHEMA")
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.executescript(schema)

        connection.execute(
            """
            INSERT INTO invitations(code, created_at, status, redeemed_by, redeemed_at)
            VALUES ('old-code', '2026-07-12', 'revoked', 100, '2026-07-12')
            """
        )
        connection.execute(
            """
            INSERT INTO invitations(code, created_at, status, redeemed_by, redeemed_at)
            VALUES ('new-code', '2026-07-12', 'claimed', 100, '2026-07-12')
            """
        )

        count = connection.execute(
            "SELECT COUNT(*) FROM invitations WHERE redeemed_by = 100"
        ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_legacy_schema_migration_removes_redeemer_uniqueness(self) -> None:
        migration = string_constant(
            "app/database.py", "LEGACY_REDEEMER_MIGRATION"
        )
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE invitations (
              code TEXT PRIMARY KEY,
              created_at TEXT NOT NULL,
              status TEXT NOT NULL,
              redeemed_by INTEGER UNIQUE,
              redeemed_at TEXT
            );
            CREATE TABLE authorized_users (
              user_id INTEGER PRIMARY KEY,
              invite_code TEXT NOT NULL UNIQUE REFERENCES invitations(code),
              authorized_at TEXT NOT NULL
            );
            INSERT INTO invitations VALUES (
              'old-code', '2026-07-12', 'revoked', 100, '2026-07-12'
            );
            """
        )

        connection.executescript(migration)
        connection.execute(
            """
            INSERT INTO invitations(code, created_at, status, redeemed_by, redeemed_at)
            VALUES ('new-code', '2026-07-12', 'claimed', 100, '2026-07-12')
            """
        )
        connection.execute(
            """
            INSERT INTO authorized_users(user_id, invite_code, authorized_at)
            VALUES (100, 'new-code', '2026-07-12')
            """
        )

        self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])


class RepositoryHygieneContractTest(unittest.TestCase):
    def test_gitignore_does_not_hide_regression_tests(self) -> None:
        patterns = {
            line.strip()
            for line in Path(".gitignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

        hidden_tests = sorted(pattern for pattern in patterns if pattern.startswith("tests/"))
        self.assertEqual(hidden_tests, [])

    def test_processing_slot_is_acquired_before_workspace_and_download(self) -> None:
        source = Path("app/handlers.py").read_text(encoding="utf-8")

        slot = source.index("async with processing_slots:")
        workspace = source.index("async with task_workspace(temp_root)")
        download = source.index("await message.bot.get_file")
        self.assertLess(slot, workspace)
        self.assertLess(slot, download)

    def test_database_transactions_rollback_on_cancellation(self) -> None:
        source = Path("app/database.py").read_text(encoding="utf-8")

        self.assertGreaterEqual(source.count("except BaseException:"), 3)

    def test_runtime_resources_are_acquired_inside_cleanup_scope(self) -> None:
        source = Path("app/main.py").read_text(encoding="utf-8")

        self.assertLess(source.index("    try:"), source.index("await repository.initialize()"))
        self.assertIn("close_bot_session=False", source)


if __name__ == "__main__":
    unittest.main()
