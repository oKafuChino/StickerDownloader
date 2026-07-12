import asyncio
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
from aiogram.types import FSInputFile, Message
from aiogram.utils.chat_action import ChatActionSender

from app.access import AccessService, RedeemResult
from app.converters import ConversionError, ConversionService
from app.models import StickerAsset, sticker_kind
from app.text import chunk_lines
from app.workspace import task_workspace


logger = logging.getLogger(__name__)

UNAUTHORIZED_REPLY = "请先使用邀请码启动 Bot。"
STICKER_ACKNOWLEDGEMENT = "已收到贴纸，正在转换，请稍等。"

REDEEM_REPLIES = {
    RedeemResult.REDEEMED: "邀请码验证成功，现在可以发送贴纸了。",
    RedeemResult.INVALID: "邀请码无效。",
    RedeemResult.CLAIMED: "该邀请码已被使用。",
    RedeemResult.REVOKED: "该邀请码已被撤销。",
    RedeemResult.ALREADY_AUTHORIZED: "你的账号已经获得授权。",
}


def is_private_chat(chat_type: str) -> bool:
    return chat_type == ChatType.PRIVATE


def should_download_sticker(*, chat_type: str, is_authorized: bool) -> bool:
    return is_private_chat(chat_type) and is_authorized


def is_feature_authorized(*, is_owner: bool, is_authorized: bool) -> bool:
    return is_owner or is_authorized


def help_text(*, is_owner: bool) -> str:
    lines = [
        "可用指令：",
        "/help - 查看指令列表",
        "/start - 查看授权状态",
        "发送贴纸 - 自动转换为 PNG 或 GIF",
    ]
    if is_owner:
        lines.extend(
            [
                "",
                "管理员指令：",
                "/invite - 创建邀请码",
                "/invites - 查看邀请码",
                "/revoke <邀请码> - 撤销邀请码",
            ]
        )
    return "\n".join(lines)


def sticker_asset_from_flags(
    *,
    file_id: str,
    file_unique_id: str,
    is_animated: bool,
    is_video: bool,
) -> StickerAsset:
    return StickerAsset(
        file_id=file_id,
        file_unique_id=file_unique_id,
        kind=sticker_kind(is_animated=is_animated, is_video=is_video),
    )


def build_router(
    *,
    access: AccessService,
    converter: ConversionService,
    temp_root: Path,
    owner_telegram_id: int,
    processing_concurrency: int,
) -> Router:
    router = Router(name="private-sticker-converter")
    private_chat = F.chat.type == ChatType.PRIVATE
    processing_slots = asyncio.Semaphore(processing_concurrency)

    def is_owner(message: Message) -> bool:
        return (
            message.from_user is not None
            and message.from_user.id == owner_telegram_id
        )

    @router.message(CommandStart(), private_chat)
    async def start(message: Message, command: CommandObject) -> None:
        if message.from_user is None:
            return
        if is_owner(message):
            await message.answer("管理员账号已就绪，可以直接发送贴纸。")
            return
        if not command.args:
            if await access.is_authorized(message.from_user.id):
                await message.answer("你的账号已经获得授权，可以发送贴纸。")
            else:
                await message.answer("请使用 /start <邀请码> 完成授权。")
            return

        result = await access.redeem(
            code=command.args.strip(),
            user_id=message.from_user.id,
        )
        await message.answer(REDEEM_REPLIES[result])

    @router.message(Command("help"), private_chat)
    async def show_help(message: Message) -> None:
        if message.from_user is None:
            return
        owner = is_owner(message)
        authorized = is_feature_authorized(
            is_owner=owner,
            is_authorized=await access.is_authorized(message.from_user.id),
        )
        if not authorized:
            await message.answer(UNAUTHORIZED_REPLY)
            return
        await message.answer(help_text(is_owner=owner))

    @router.message(Command("invite"), private_chat)
    async def create_invite(message: Message) -> None:
        if not is_owner(message):
            await message.answer("无权限使用管理命令。")
            return
        invite = await access.issue_invite()
        await message.answer(f"新邀请码：{invite.code}")

    @router.message(Command("invites"), private_chat)
    async def list_invites(message: Message) -> None:
        if not is_owner(message):
            await message.answer("无权限使用管理命令。")
            return
        invites = await access.list_invites()
        if not invites:
            await message.answer("目前没有邀请码。")
            return
        lines = [
            f"{invite.code} | {invite.status} | 用户：{invite.redeemed_by or '-'}"
            for invite in invites
        ]
        for chunk in chunk_lines(lines):
            await message.answer(chunk)

    @router.message(Command("revoke"), private_chat)
    async def revoke_invite(message: Message, command: CommandObject) -> None:
        if not is_owner(message):
            await message.answer("无权限使用管理命令。")
            return
        if not command.args:
            await message.answer("用法：/revoke <邀请码>")
            return
        revoked = await access.revoke(command.args.strip())
        await message.answer("邀请码已撤销。" if revoked else "未找到该邀请码。")

    @router.message(F.sticker, private_chat)
    async def convert_sticker(message: Message) -> None:
        if message.from_user is None or message.sticker is None:
            return

        authorized = is_feature_authorized(
            is_owner=is_owner(message),
            is_authorized=await access.is_authorized(message.from_user.id),
        )
        if not should_download_sticker(
            chat_type=message.chat.type,
            is_authorized=authorized,
        ):
            await message.answer(UNAUTHORIZED_REPLY)
            return

        sticker = message.sticker
        asset = sticker_asset_from_flags(
            file_id=sticker.file_id,
            file_unique_id=sticker.file_unique_id,
            is_animated=sticker.is_animated,
            is_video=sticker.is_video,
        )

        try:
            await message.answer(STICKER_ACKNOWLEDGEMENT)
            async with ChatActionSender.typing(
                bot=message.bot,
                chat_id=message.chat.id,
            ):
                async with processing_slots:
                    async with task_workspace(temp_root) as task_dir:
                        telegram_file = await message.bot.get_file(asset.file_id)
                        if not telegram_file.file_path:
                            raise ConversionError("Telegram did not return a file path")

                        source = task_dir / (
                            "source" + ConversionService.source_suffix(asset.kind)
                        )
                        await message.bot.download_file(
                            telegram_file.file_path,
                            destination=source,
                        )
                        output = await converter.convert(
                            asset=asset,
                            source=source,
                            task_dir=task_dir,
                        )
                        filename = f"sticker-{asset.file_unique_id}{output.suffix}"
                        await message.answer_document(
                            FSInputFile(output, filename=filename),
                            disable_content_type_detection=True,
                        )
        except Exception:
            logger.exception(
                "Sticker conversion failed for user=%s file=%s",
                message.from_user.id,
                asset.file_unique_id,
            )
            await message.answer("转换失败，请稍后重试。")

    return router
