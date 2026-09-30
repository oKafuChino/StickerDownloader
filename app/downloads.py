import asyncio
import logging
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from aiohttp import web
from aiohttp.hdrs import CONTENT_DISPOSITION
from aiohttp.helpers import content_disposition_header

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DownloadLink:
    token: str
    url: str
    expires_at: float


@dataclass
class _DownloadEntry:
    path: Path
    filename: str
    expires_at: float


class TemporaryDownloadService:
    def __init__(self, *, root: Path, public_base_url: str,
                 port: int = 18080, ttl_seconds: int = 3600,
                 max_entries: int = 20) -> None:
        if not public_base_url or ttl_seconds < 1 or max_entries < 1:
            raise ValueError("Download URL, positive TTL and capacity are required")
        if not 1 <= port <= 65535:
            raise ValueError("Invalid download port")
        self._root = root / "downloads"
        self._public_base_url = public_base_url.rstrip("/")
        self._port = port
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._entries: dict[str, _DownloadEntry] = {}
        self._runner: web.AppRunner | None = None
        self._cleanup_task: asyncio.Task | None = None

    def application(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/downloads/{token}", self._handle_download)
        return app

    async def start(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        # Tokens are process-local; remove archives left by an interrupted run.
        for path in self._root.glob("*.zip"):
            if re.fullmatch(r"[A-Za-z0-9_-]{43}\.zip", path.name):
                path.unlink(missing_ok=True)
        self._runner = web.AppRunner(self.application(), access_log=None)
        await self._runner.setup()
        await web.TCPSite(self._runner, "0.0.0.0", self._port).start()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        try:
            if self._runner is not None:
                await self._runner.cleanup()
        finally:
            await self._remove_expired(force=True)

    async def publish(self, archive: Path, *, filename: str) -> DownloadLink:
        await self._remove_expired()
        if len(self._entries) >= self._max_entries:
            raise RuntimeError("Temporary download storage is full")
        self._root.mkdir(parents=True, exist_ok=True)
        token = secrets.token_urlsafe(32)
        expires_at = time.time() + self._ttl_seconds
        destination = self._root / f"{token}.zip"
        archive.replace(destination)
        self._entries[token] = _DownloadEntry(destination, filename, expires_at)
        return DownloadLink(token, f"{self._public_base_url}/downloads/{token}", expires_at)

    async def revoke(self, token: str) -> None:
        entry = self._entries.get(token)
        if entry is not None:
            entry.expires_at = 0
            await self._remove_expired()

    async def _handle_download(self, request: web.Request) -> web.StreamResponse:
        entry = self._entries.get(request.match_info["token"])
        if entry is None or entry.expires_at <= time.time() or not entry.path.is_file():
            return web.Response(status=404, text="Download link expired or not found.")
        return web.FileResponse(entry.path, headers={
            CONTENT_DISPOSITION: content_disposition_header("attachment", filename=entry.filename),
            "Content-Type": "application/zip",
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        })

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(min(60, self._ttl_seconds))
            await self._remove_expired()

    async def _remove_expired(self, *, force: bool = False) -> None:
        now = time.time()
        for token, entry in list(self._entries.items()):
            if force or entry.expires_at <= now:
                try:
                    entry.path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Unable to remove expired archive", exc_info=True)
                else:
                    del self._entries[token]
