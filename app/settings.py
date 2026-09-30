from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit


def _read_positive_int(
    environ: Mapping[str, str],
    name: str,
    default: int,
    *,
    maximum: int | None = None,
) -> int:
    try:
        value = int(environ.get(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 1 or (maximum is not None and value > maximum):
        suffix = f" and at most {maximum}" if maximum is not None else ""
        raise ValueError(f"{name} must be at least 1{suffix}")
    return value




@dataclass(frozen=True)
class Settings:
    bot_token: str
    owner_telegram_id: int
    database_path: Path
    temp_root: Path
    conversion_concurrency: int
    max_pending_conversions: int
    public_base_url: str = ""
    download_port: int = 18080
    download_ttl_seconds: int = 3600

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

        try:
            max_pending = int(environ.get("MAX_PENDING_CONVERSIONS", "8"))
        except ValueError as exc:
            raise ValueError(
                "MAX_PENDING_CONVERSIONS must be an integer"
            ) from exc
        if max_pending < 0:
            raise ValueError("MAX_PENDING_CONVERSIONS must be at least 0")

        public_base_url = environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
        if public_base_url:
            url = urlsplit(public_base_url)
            if (url.scheme not in {"http", "https"} or not url.hostname
                    or url.username or url.password or url.query or url.fragment
                    or any(char.isspace() for char in public_base_url)):
                raise ValueError("PUBLIC_BASE_URL must be an HTTP(S) base URL")
            _ = url.port

        return cls(
            bot_token=environ["BOT_TOKEN"],
            owner_telegram_id=int(environ["OWNER_TELEGRAM_ID"]),
            database_path=Path(environ["DATABASE_PATH"]),
            temp_root=Path(environ["TEMP_ROOT"]),
            conversion_concurrency=concurrency,
            max_pending_conversions=max_pending,
            public_base_url=public_base_url,
            download_port=_read_positive_int(environ, "DOWNLOAD_PORT", 18080, maximum=65535),
            download_ttl_seconds=_read_positive_int(environ, "DOWNLOAD_TTL_SECONDS", 3600),
        )
