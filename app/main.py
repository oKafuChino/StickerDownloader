import asyncio
import logging
import os

from aiogram import Bot, Dispatcher

from app.access import AccessService
from app.converters import ConversionService
from app.database import AccessRepository
from app.downloads import TemporaryDownloadService
from app.handlers import build_router
from app.settings import Settings


async def run_bot(settings: Settings) -> None:
    repository = AccessRepository(settings.database_path)
    bot: Bot | None = None
    downloads = TemporaryDownloadService(
        root=settings.temp_root,
        public_base_url=settings.public_base_url,
        port=settings.download_port,
        ttl_seconds=settings.download_ttl_seconds,
    ) if settings.public_base_url else None
    try:
        await repository.initialize()
        bot = Bot(token=settings.bot_token)
        if downloads is not None:
            await downloads.start()
        dispatcher = Dispatcher()
        dispatcher.include_router(
            build_router(
                access=AccessService(repository),
                converter=ConversionService(settings.conversion_concurrency),
                temp_root=settings.temp_root,
                owner_telegram_id=settings.owner_telegram_id,
                processing_concurrency=settings.conversion_concurrency,
                max_pending_conversions=settings.max_pending_conversions,
                downloads=downloads,
            )
        )
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
            close_bot_session=False,
        )
    finally:
        try:
            try:
                if downloads is not None:
                    await downloads.stop()
            finally:
                if bot is not None:
                    await bot.session.close()
        finally:
            await repository.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = Settings.from_env(os.environ)
    asyncio.run(run_bot(settings))


if __name__ == "__main__":
    main()
