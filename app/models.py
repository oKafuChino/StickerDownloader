from dataclasses import dataclass
from enum import StrEnum


class StickerKind(StrEnum):
    STATIC = "static"
    ANIMATED = "animated"
    VIDEO = "video"


@dataclass(frozen=True)
class StickerAsset:
    file_id: str
    file_unique_id: str
    kind: StickerKind


@dataclass(frozen=True)
class Invite:
    code: str
    status: str
    redeemed_by: int | None
    redeemed_at: str | None


def sticker_kind(*, is_animated: bool, is_video: bool) -> StickerKind:
    if is_animated:
        return StickerKind.ANIMATED
    if is_video:
        return StickerKind.VIDEO
    return StickerKind.STATIC

