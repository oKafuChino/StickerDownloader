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


def async_function(path: str, name: str):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
            namespace = {"AccessService": object}
            exec(compile(module, path, "exec"), namespace)
            return namespace[name]
    raise AssertionError(f"missing async function {name}")


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

        acknowledgement = source.index(
            "await message.answer(STICKER_ACKNOWLEDGEMENT)"
        )
        slot = source.index("async with processing_slots:")
        typing = source.index("async with ChatActionSender.typing(")
        workspace = source.index("async with task_workspace(temp_root)")
        download = source.index("await message.bot.get_file")
        self.assertLess(acknowledgement, slot)
        self.assertLess(slot, typing)
        self.assertLess(slot, workspace)
        self.assertLess(slot, download)

    def test_database_transactions_rollback_on_cancellation(self) -> None:
        source = Path("app/database.py").read_text(encoding="utf-8")

        self.assertGreaterEqual(source.count("except BaseException:"), 3)

    def test_runtime_resources_are_acquired_inside_cleanup_scope(self) -> None:
        source = Path("app/main.py").read_text(encoding="utf-8")

        self.assertLess(source.index("    try:"), source.index("await repository.initialize()"))
        self.assertIn("close_bot_session=False", source)

    def test_owner_authorization_short_circuits_database_lookup(self) -> None:
        source = Path("app/handlers.py").read_text(encoding="utf-8")

        self.assertIn(
            "return is_owner or await access.is_authorized(user_id)",
            source,
        )

    def test_sticker_capacity_precedes_authorization_and_expensive_work(self) -> None:
        source = Path("app/handlers.py").read_text(encoding="utf-8")
        handler = source.index("async def convert_sticker")

        limiter = source.index("sticker_capacity = CapacityLimiter(")
        self.assertIn(
            "processing_concurrency + max_pending_conversions",
            source[limiter : limiter + 150],
        )
        admission = source.index(
            "if not sticker_capacity.try_acquire():", handler
        )
        authorization = source.index(
            "authorized = await is_feature_authorized(", handler
        )
        acknowledgement = source.index(
            "await message.answer(STICKER_ACKNOWLEDGEMENT)", handler
        )
        workspace = source.index("async with task_workspace(temp_root)", handler)
        download = source.index("await message.bot.get_file", handler)
        release = source.index("sticker_capacity.release()", handler)

        self.assertLess(limiter, handler)
        self.assertLess(admission, authorization)
        self.assertLess(admission, acknowledgement)
        self.assertLess(admission, workspace)
        self.assertLess(admission, download)
        self.assertLess(source.index("finally:", handler), release)

    def test_overload_reply_copy_is_stable(self) -> None:
        source = Path("app/handlers.py").read_text(encoding="utf-8")

        self.assertIn(
            'MAX_CAPACITY_REPLY = "当前任务较多，请稍后重试。"',
            source,
        )

    def test_main_passes_pending_capacity_to_router(self) -> None:
        source = Path("app/main.py").read_text(encoding="utf-8")

        self.assertIn(
            "max_pending_conversions=settings.max_pending_conversions",
            source,
        )


class HandlerAuthorizationBehaviorTest(unittest.IsolatedAsyncioTestCase):
    async def test_owner_bypasses_authorization_lookup(self) -> None:
        feature_authorized = async_function(
            "app/handlers.py", "is_feature_authorized"
        )

        class AccessProbe:
            calls = 0

            async def is_authorized(self, user_id: int) -> bool:
                self.calls += 1
                return False

        access = AccessProbe()
        self.assertTrue(
            await feature_authorized(is_owner=True, user_id=42, access=access)
        )
        self.assertEqual(access.calls, 0)

    async def test_non_owner_uses_authorization_lookup(self) -> None:
        feature_authorized = async_function(
            "app/handlers.py", "is_feature_authorized"
        )

        class AccessProbe:
            calls = 0

            async def is_authorized(self, user_id: int) -> bool:
                self.calls += 1
                return user_id == 42

        access = AccessProbe()
        self.assertTrue(
            await feature_authorized(is_owner=False, user_id=42, access=access)
        )
        self.assertEqual(access.calls, 1)


if __name__ == "__main__":
    unittest.main()
