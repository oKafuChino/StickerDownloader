from app.handlers import (
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

