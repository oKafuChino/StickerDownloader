from pathlib import Path

import pytest

from app.models import StickerKind, sticker_kind
from app.settings import Settings


def test_settings_reads_required_environment() -> None:
    settings = Settings.from_env(
        {
            "BOT_TOKEN": "123:token",
            "OWNER_TELEGRAM_ID": "42",
            "DATABASE_PATH": "/data/bot.sqlite3",
            "TEMP_ROOT": "/tmp/bot",
            "CONVERSION_CONCURRENCY": "2",
        }
    )

    assert settings.owner_telegram_id == 42
    assert settings.database_path == Path("/data/bot.sqlite3")
    assert settings.conversion_concurrency == 2


def test_settings_rejects_zero_concurrency() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        Settings.from_env(
            {
                "BOT_TOKEN": "123:token",
                "OWNER_TELEGRAM_ID": "42",
                "DATABASE_PATH": "/data/bot.sqlite3",
                "TEMP_ROOT": "/tmp/bot",
                "CONVERSION_CONCURRENCY": "0",
            }
        )


@pytest.mark.parametrize(
    ("is_animated", "is_video", "expected"),
    [
        (False, False, StickerKind.STATIC),
        (True, False, StickerKind.ANIMATED),
        (False, True, StickerKind.VIDEO),
    ],
)
def test_sticker_kind_uses_telegram_flags(
    is_animated: bool, is_video: bool, expected: StickerKind
) -> None:
    assert sticker_kind(is_animated=is_animated, is_video=is_video) is expected

