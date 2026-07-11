import secrets
from collections.abc import Callable
from enum import StrEnum

import aiosqlite

from app.database import AccessRepository
from app.models import Invite


class RedeemResult(StrEnum):
    REDEEMED = "redeemed"
    INVALID = "invalid"
    CLAIMED = "claimed"
    REVOKED = "revoked"
    ALREADY_AUTHORIZED = "already_authorized"


class AccessService:
    def __init__(
        self,
        repository: AccessRepository,
        code_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repository = repository
        self._code_factory = code_factory or (lambda: secrets.token_urlsafe(8))

    async def issue_invite(self) -> Invite:
        for _ in range(5):
            code = self._code_factory()
            try:
                return await self._repository.create_invite(code)
            except aiosqlite.IntegrityError:
                continue
        raise RuntimeError("Unable to generate a unique invitation code")

    async def redeem(self, *, code: str, user_id: int) -> RedeemResult:
        if await self._repository.is_authorized(user_id):
            return RedeemResult.ALREADY_AUTHORIZED

        invite = await self._repository.get_invite(code)
        if invite is None:
            return RedeemResult.INVALID
        if invite.status == "claimed":
            return RedeemResult.CLAIMED
        if invite.status == "revoked":
            return RedeemResult.REVOKED

        if await self._repository.claim_invite(code, user_id):
            return RedeemResult.REDEEMED

        if await self._repository.is_authorized(user_id):
            return RedeemResult.ALREADY_AUTHORIZED
        current = await self._repository.get_invite(code)
        if current is None:
            return RedeemResult.INVALID
        return (
            RedeemResult.REVOKED
            if current.status == "revoked"
            else RedeemResult.CLAIMED
        )

    async def is_authorized(self, user_id: int) -> bool:
        return await self._repository.is_authorized(user_id)

    async def list_invites(self) -> list[Invite]:
        return await self._repository.list_invites()

    async def revoke(self, code: str) -> bool:
        return await self._repository.revoke_invite(code)

