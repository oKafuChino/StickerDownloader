import asyncio
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from app.models import Invite


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS invitations (
  code TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'claimed', 'revoked')),
  redeemed_by INTEGER,
  redeemed_at TEXT
);
CREATE TABLE IF NOT EXISTS authorized_users (
  user_id INTEGER PRIMARY KEY,
  invite_code TEXT NOT NULL UNIQUE REFERENCES invitations(code),
  authorized_at TEXT NOT NULL
);
"""

LEGACY_REDEEMER_MIGRATION = """
PRAGMA foreign_keys = OFF;
BEGIN IMMEDIATE;
ALTER TABLE authorized_users RENAME TO authorized_users_legacy;
ALTER TABLE invitations RENAME TO invitations_legacy;
CREATE TABLE invitations (
  code TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'claimed', 'revoked')),
  redeemed_by INTEGER,
  redeemed_at TEXT
);
CREATE TABLE authorized_users (
  user_id INTEGER PRIMARY KEY,
  invite_code TEXT NOT NULL UNIQUE REFERENCES invitations(code),
  authorized_at TEXT NOT NULL
);
INSERT INTO invitations(code, created_at, status, redeemed_by, redeemed_at)
SELECT code, created_at, status, redeemed_by, redeemed_at
FROM invitations_legacy;
INSERT INTO authorized_users(user_id, invite_code, authorized_at)
SELECT user_id, invite_code, authorized_at
FROM authorized_users_legacy;
DROP TABLE authorized_users_legacy;
DROP TABLE invitations_legacy;
COMMIT;
PRAGMA foreign_keys = ON;
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AccessRepository:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._connection: aiosqlite.Connection | None = None
        self._operation_lock = asyncio.Lock()

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("Repository is not initialized")
        return self._connection

    async def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self._path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.executescript(SCHEMA)
        await self._connection.commit()
        if await self._has_legacy_redeemer_unique_constraint():
            await self._connection.executescript(LEGACY_REDEEMER_MIGRATION)

    async def _has_legacy_redeemer_unique_constraint(self) -> bool:
        async with self.connection.execute(
            "PRAGMA index_list(invitations)"
        ) as cursor:
            indexes = await cursor.fetchall()
        for index in indexes:
            if not index[2]:
                continue
            index_name = index[1]
            async with self.connection.execute(
                f'PRAGMA index_info("{index_name}")'
            ) as cursor:
                columns = await cursor.fetchall()
            if [column[2] for column in columns] == ["redeemed_by"]:
                return True
        return False

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def create_invite(self, code: str) -> Invite:
        created_at = _utc_now()
        async with self._operation_lock:
            try:
                await self.connection.execute(
                    "INSERT INTO invitations(code, created_at, status) VALUES (?, ?, 'active')",
                    (code, created_at),
                )
                await self.connection.commit()
            except aiosqlite.IntegrityError:
                await self.connection.rollback()
                raise
            except BaseException:
                await self.connection.rollback()
                raise
        return Invite(code=code, status="active", redeemed_by=None, redeemed_at=None)

    async def get_invite(self, code: str) -> Invite | None:
        async with self._operation_lock:
            async with self.connection.execute(
                "SELECT code, status, redeemed_by, redeemed_at FROM invitations WHERE code = ?",
                (code,),
            ) as cursor:
                row = await cursor.fetchone()
        return self._invite_from_row(row) if row is not None else None

    async def list_invites(self) -> list[Invite]:
        async with self._operation_lock:
            async with self.connection.execute(
                """
                SELECT code, status, redeemed_by, redeemed_at
                FROM invitations
                ORDER BY created_at DESC
                """
            ) as cursor:
                rows = await cursor.fetchall()
        return [self._invite_from_row(row) for row in rows]

    async def is_authorized(self, user_id: int) -> bool:
        async with self._operation_lock:
            async with self.connection.execute(
                "SELECT 1 FROM authorized_users WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                return await cursor.fetchone() is not None

    async def claim_invite(self, code: str, user_id: int) -> bool:
        now = _utc_now()
        async with self._operation_lock:
            try:
                await self.connection.execute("BEGIN IMMEDIATE")
                cursor = await self.connection.execute(
                    """
                    UPDATE invitations
                    SET status = 'claimed', redeemed_by = ?, redeemed_at = ?
                    WHERE code = ? AND status = 'active'
                    """,
                    (user_id, now, code),
                )
                if cursor.rowcount != 1:
                    await self.connection.rollback()
                    return False
                await self.connection.execute(
                    """
                    INSERT INTO authorized_users(user_id, invite_code, authorized_at)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, code, now),
                )
                await self.connection.commit()
                return True
            except aiosqlite.IntegrityError:
                await self.connection.rollback()
                return False
            except BaseException:
                await self.connection.rollback()
                raise

    async def revoke_invite(self, code: str) -> bool:
        async with self._operation_lock:
            try:
                await self.connection.execute("BEGIN IMMEDIATE")
                cursor = await self.connection.execute(
                    "UPDATE invitations SET status = 'revoked' WHERE code = ?",
                    (code,),
                )
                if cursor.rowcount != 1:
                    await self.connection.rollback()
                    return False
                await self.connection.execute(
                    "DELETE FROM authorized_users WHERE invite_code = ?",
                    (code,),
                )
                await self.connection.commit()
                return True
            except BaseException:
                await self.connection.rollback()
                raise

    @staticmethod
    def _invite_from_row(row: aiosqlite.Row) -> Invite:
        return Invite(
            code=row["code"],
            status=row["status"],
            redeemed_by=row["redeemed_by"],
            redeemed_at=row["redeemed_at"],
        )
