from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Settings:
    bot_token: str
    owner_telegram_id: int
    database_path: Path
    temp_root: Path
    conversion_concurrency: int

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "Settings":
        names = (
            "BOT_TOKEN",
            "OWNER_TELEGRAM_ID",
            "DATABASE_PATH",
            "TEMP_ROOT",
            "CONVERSION_CONCURRENCY",
        )
        missing = [name for name in names if not environ.get(name)]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        concurrency = int(environ["CONVERSION_CONCURRENCY"])
        if concurrency < 1:
            raise ValueError("CONVERSION_CONCURRENCY must be at least 1")

        return cls(
            bot_token=environ["BOT_TOKEN"],
            owner_telegram_id=int(environ["OWNER_TELEGRAM_ID"]),
            database_path=Path(environ["DATABASE_PATH"]),
            temp_root=Path(environ["TEMP_ROOT"]),
            conversion_concurrency=concurrency,
        )

