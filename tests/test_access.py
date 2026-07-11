import pytest

from app.access import AccessService, RedeemResult
from app.database import AccessRepository


@pytest.mark.asyncio
async def test_invitation_can_be_redeemed_once(repository: AccessRepository) -> None:
    service = AccessService(repository, code_factory=lambda: "friend-code")
    await service.issue_invite()

    assert (
        await service.redeem(code="friend-code", user_id=100)
        is RedeemResult.REDEEMED
    )
    assert (
        await service.redeem(code="friend-code", user_id=200)
        is RedeemResult.CLAIMED
    )
    assert await service.is_authorized(100)
    assert not await service.is_authorized(200)


@pytest.mark.asyncio
async def test_revoking_claimed_invite_removes_authorization(
    repository: AccessRepository,
) -> None:
    service = AccessService(repository, code_factory=lambda: "revoke-code")
    await service.issue_invite()
    await service.redeem(code="revoke-code", user_id=100)

    assert await service.revoke("revoke-code")
    assert not await service.is_authorized(100)
    assert (
        await service.redeem(code="revoke-code", user_id=100)
        is RedeemResult.REVOKED
    )


@pytest.mark.asyncio
async def test_unknown_invitation_is_invalid(repository: AccessRepository) -> None:
    service = AccessService(repository, code_factory=lambda: "unused")

    assert (
        await service.redeem(code="missing", user_id=100)
        is RedeemResult.INVALID
    )

