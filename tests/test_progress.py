import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.methods import EditMessageText

from app.progress import PackProgressReporter, pack_progress_text


def rate_limit(seconds=5):
    return TelegramRetryAfter(
        method=EditMessageText(text="progress", chat_id=1, message_id=1),
        message="Too Many Requests", retry_after=seconds,
    )


def test_progress_displays_completed_stickers_and_current_stage():
    text = pack_progress_text("Example", 5, 10, "converting")
    assert "██████░░░░░░ 50%" in text
    assert "已转换 5/10 张" in text
    assert "正在转换第 6/10 张" in text
    assert "已可下载" not in text
    text = pack_progress_text("Example", 10, 10, "packing")
    assert "100%" in text
    assert "正在打包" in text
    assert "已可下载" not in text


async def test_intermediate_updates_are_throttled_but_packing_is_visible():
    now = [100.0]
    status = SimpleNamespace(edit_text=AsyncMock())
    reporter = PackProgressReporter(status, "Example", clock=lambda: now[0])
    await reporter.update(0, 10, "downloading")
    await reporter.update(0, 10, "converting")
    await reporter.update(1, 10, "converted")
    assert status.edit_text.await_count == 1
    now[0] += 2
    await reporter.update(3, 10, "converting")
    assert status.edit_text.await_count == 2
    await reporter.update(10, 10, "packing")
    await reporter.update(10, 10, "packing")
    assert status.edit_text.await_count == 3
    assert "正在打包" in status.edit_text.call_args.args[0]


async def test_rate_limit_skips_even_packing_until_cooldown():
    now = [100.0]
    status = SimpleNamespace(edit_text=AsyncMock(side_effect=[rate_limit(), None]))
    reporter = PackProgressReporter(status, "Example", clock=lambda: now[0])
    await reporter.update(0, 10, "downloading")
    now[0] += 2
    await reporter.update(10, 10, "packing")
    assert status.edit_text.await_count == 1
    now[0] += 3
    await reporter.update(10, 10, "packing")
    assert status.edit_text.await_count == 2


async def test_progress_edit_errors_do_not_interrupt_conversion():
    error = TelegramBadRequest(
        method=EditMessageText(text="progress", chat_id=1, message_id=1),
        message="message to edit not found",
    )
    reporter = PackProgressReporter(SimpleNamespace(edit_text=AsyncMock(side_effect=error)), "Example")
    await reporter.update(0, 1, "downloading")


async def test_progress_cancellation_is_not_swallowed():
    reporter = PackProgressReporter(
        SimpleNamespace(edit_text=AsyncMock(side_effect=asyncio.CancelledError)), "Example",
    )
    with pytest.raises(asyncio.CancelledError):
        await reporter.update(0, 1, "downloading")


async def test_completion_retries_rate_limit_and_keeps_download_link(monkeypatch):
    now = [100.0]
    delays = []

    async def sleep(seconds):
        delays.append(seconds)
        now[0] += seconds

    monkeypatch.setattr("app.progress.asyncio.sleep", sleep)
    status = SimpleNamespace(edit_text=AsyncMock(side_effect=[None, rate_limit(5), None]))
    reporter = PackProgressReporter(status, "Example", clock=lambda: now[0])
    await reporter.update(1, 1, "packing")
    text = pack_progress_text("Example", 1, 1, "done") + "\nhttps://example.test/download"
    await reporter.finish(text)
    assert delays == [2, 5]
    assert status.edit_text.call_args.args == (text,)
    assert status.edit_text.call_args.kwargs["disable_web_page_preview"] is True


async def test_getpack_edits_one_message_through_completion(tmp_path, monkeypatch):
    from aiogram.filters.command import CommandObject
    from PIL import Image

    from app.converters import ConversionService
    from app.downloads import TemporaryDownloadService
    from app.handlers import build_router

    status = SimpleNamespace(edit_text=AsyncMock())
    bot = AsyncMock()
    bot.get_sticker_set.return_value = SimpleNamespace(title="Example", stickers=[
        SimpleNamespace(file_id="one", file_unique_id="one", is_animated=False, is_video=False),
    ])
    bot.get_file.return_value = SimpleNamespace(file_path="sticker.webp")

    async def download(file_path, destination):
        Image.new("RGBA", (16, 16), (255, 0, 0, 128)).save(destination, "WEBP")

    bot.download_file.side_effect = download
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=1), chat=SimpleNamespace(id=1), bot=bot,
        answer=AsyncMock(return_value=status), answer_document=AsyncMock(),
    )
    monkeypatch.setattr("app.handlers.ChatActionSender.typing", lambda **kw: AsyncMock())
    monkeypatch.setattr("app.handlers.PackProgressReporter",
                        lambda msg, title: PackProgressReporter(msg, title, interval=0))
    downloads = TemporaryDownloadService(root=tmp_path, public_base_url="https://example.test")
    router = build_router(
        access=AsyncMock(), converter=ConversionService(1), temp_root=tmp_path / "tasks",
        owner_telegram_id=1, processing_concurrency=1, max_pending_conversions=0,
        downloads=downloads,
    )
    handler = next(h.callback for h in router.message.handlers if h.callback.__name__ == "get_sticker_pack")
    try:
        await handler(message, CommandObject(command="getpack", args="https://t.me/addstickers/Example"))
        updates = [call.args[0] for call in status.edit_text.await_args_list]
        assert "0%" in updates[0] and "正在下载" in updates[0]
        assert any("正在转换" in text for text in updates)
        assert any("正在打包" in text for text in updates)
        assert "100%" in updates[-1] and "https://example.test/downloads/" in updates[-1]
        assert "已可下载" in updates[-1]
        message.answer.assert_awaited_once()
        message.answer_document.assert_not_awaited()
    finally:
        await downloads.stop()
