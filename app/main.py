import asyncio
import logging
import os

from aiogram import Bot, Dispatcher

from app.access import AccessService
from app.converters import ConversionService
from app.database import AccessRepository
from app.handlers import build_router
from app.settings import Settings


async def run_bot(settings: Settings) -> None:
    repository = AccessRepository(settings.database_path)
    bot: Bot | None = None
    try:
        await repository.initialize()
        bot = Bot(token=settings.bot_token)
        dispatcher = Dispatcher()
        dispatcher.include_router(
            build_router(
                access=AccessService(repository),
                converter=ConversionService(settings.conversion_concurrency),
                temp_root=settings.temp_root,
                owner_telegram_id=settings.owner_telegram_id,
                processing_concurrency=settings.conversion_concurrency,
            )
        )
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
            close_bot_session=False,
        )
    finally:
        try:
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
