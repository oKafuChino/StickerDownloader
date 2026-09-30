import asyncio
import logging
import time
from collections.abc import Callable

from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.types import Message


logger = logging.getLogger(__name__)


def pack_progress_text(title: str, completed: int, total: int, stage: str) -> str:
    completed = min(max(completed, 0), total)
    filled = completed * 12 // total if total else 0
    percent = completed * 100 // total if total else 0
    bar = "█" * filled + "░" * (12 - filled)
    current = min(completed + 1, total)
    label = {
        "downloading": f"正在下载第 {current}/{total} 张",
        "converting": f"正在转换第 {current}/{total} 张为 PNG/GIF",
        "converted": "正在处理贴纸",
        "packing": "正在打包 ZIP，请稍等",
        "done": "处理完成，文件已可下载",
    }[stage]
    return f"「{title}」\n{bar} {percent}%\n已转换 {completed}/{total} 张\n{label}"


class PackProgressReporter:
    def __init__(
        self, message: Message, title: str, *,
        interval: float = 2.0, clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._message = message
        self._title = title
        self._interval = interval
        self._clock = clock
        self._next_update = 0.0
        self._retry_after = 0.0
        self._last_text: str | None = None
        self._packing_reported = False

    async def update(self, completed: int, total: int, stage: str) -> None:
        now = self._clock()
        packing = stage == "packing" and not self._packing_reported
        if now < self._retry_after or (now < self._next_update and not packing):
            return
        text = pack_progress_text(self._title, completed, total, stage)
        if text == self._last_text:
            return
        self._next_update = now + self._interval
        try:
            await self._message.edit_text(text)
        except TelegramRetryAfter as exc:
            self._retry_after = self._clock() + exc.retry_after
        except (TelegramAPIError, OSError, TimeoutError):
            # Progress is advisory; an edit failure must not discard the pack.
            logger.warning("Unable to update pack progress")
        else:
            self._last_text = text
            self._packing_reported |= packing

    async def finish(self, text: str) -> None:
        # Unlike intermediate progress, the final download link must be delivered.
        for attempt in range(3):
            delay = max(self._next_update, self._retry_after) - self._clock()
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                await self._message.edit_text(text, disable_web_page_preview=True)
                return
            except TelegramRetryAfter as exc:
                if attempt == 2:
                    raise
                self._retry_after = self._clock() + exc.retry_after
