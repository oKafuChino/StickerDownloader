from app.handlers import (
    STICKER_ACKNOWLEDGEMENT,
    help_text,
    is_feature_authorized,
    is_private_chat,
    should_download_sticker,
    sticker_asset_from_flags,
)
from app.models import StickerKind


def test_only_private_chat_is_eligible_for_processing() -> None:
    assert is_private_chat("private")
    assert not is_private_chat("group")
    assert not is_private_chat("supergroup")
    assert not is_private_chat("channel")


def test_group_and_unauthorized_messages_never_download_stickers() -> None:
    assert not should_download_sticker(chat_type="group", is_authorized=True)
    assert not should_download_sticker(
        chat_type="private", is_authorized=False
    )
    assert should_download_sticker(chat_type="private", is_authorized=True)


def test_video_sticker_routes_to_video_conversion() -> None:
    asset = sticker_asset_from_flags(
        file_id="file",
        file_unique_id="unique",
        is_animated=False,
        is_video=True,
    )

    assert asset.kind is StickerKind.VIDEO


def test_regular_help_does_not_reveal_admin_commands() -> None:
    text = help_text(is_owner=False)

    assert "/help" in text
    assert "发送贴纸" in text
    assert "/invite" not in text
    assert "/revoke" not in text


def test_owner_help_includes_admin_commands() -> None:
    text = help_text(is_owner=True)

    assert "/invite" in text
    assert "/invites" in text
    assert "/revoke <邀请码>" in text


def test_features_require_owner_or_active_authorization() -> None:
    assert is_feature_authorized(is_owner=True, is_authorized=False)
    assert is_feature_authorized(is_owner=False, is_authorized=True)
    assert not is_feature_authorized(is_owner=False, is_authorized=False)


def test_sticker_acknowledgement_copy_is_stable() -> None:
    assert STICKER_ACKNOWLEDGEMENT == "已收到贴纸，正在转换，请稍等。"

