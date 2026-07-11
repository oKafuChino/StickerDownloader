# Telegram Sticker Converter Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build a lightweight, invite-only Telegram Bot that converts native private-chat stickers to PNG or GIF and runs as one Docker container on a Debian or Ubuntu VPS.

**Architecture:** A single Python aiogram process uses long polling and SQLite. A private-chat handler authorizes the Telegram user before downloading a sticker, then delegates conversion to a bounded in-process service with an isolated temporary workspace. Docker supplies FFmpeg and the Lottie converter; the system has no inbound port, proxy, queue, Redis, web UI, or persistent media storage.

**Tech Stack:** Python 3.12, aiogram 3.x, aiosqlite, Pillow with WebP support, python-lottie, FFmpeg, pytest, pytest-asyncio, Docker Compose.

## Global Constraints

- Use Python >=3.12,<3.13 and aiogram >=3,<4.
- Process only Telegram native stickers in private chats. Do not download messages from a group, supergroup, or channel.
- Convert WEBP to PNG, TGS to GIF, and WEBM to GIF with no user-facing duration, frame-rate, size, or format setting.
- Use an in-process conversion semaphore. It queues surplus work but never rejects it for exceeding a product limit.
- Persist invitation and authorization records only. Delete every source, intermediate, and output media file after each task.
- Require OWNER_TELEGRAM_ID for administrative commands. Keep BOT_TOKEN and real settings in an ignored .env file.
- Use long polling. Compose must expose no ports and set restart: unless-stopped.
- Write a failing test first, make it pass with the smallest change, run its focused suite, then commit each task.

---

## Planned File Structure

    app/
      __init__.py          package version
      access.py            invitation and authorization business rules
      converters.py        WEBP/TGS/WEBM conversion and bounded execution
      database.py          SQLite schema and persistence operations
      handlers.py          private-chat Telegram routes and owner commands
      main.py              settings, dependencies, router, long polling
      models.py            shared domain values
      settings.py          environment validation
      workspace.py         isolated task directories and removal
    tests/
      conftest.py          async SQLite fixture
      test_access.py       invitation lifecycle
      test_converters.py   fast and real-format conversion tests
      test_handlers.py     private-chat and authorization routing
      test_settings.py     environment configuration
    Dockerfile             runtime and test targets
    compose.yaml           one production bot container
    .dockerignore          omit local state and secrets from builds
    .env.example           deployment variable names without secrets
    .gitignore             Python, local database, temporary media, secrets
    pyproject.toml         package metadata, dependencies, pytest configuration
    README.md              local setup and VPS deployment

### Task 1: Bootstrap the Package and Test Runner

**Files:**
- Create: pyproject.toml
- Create: app/__init__.py
- Create: tests/__init__.py
- Create: tests/test_smoke.py
- Create: .gitignore
- Create: .env.example

**Interfaces:**
- Consumes: none.
- Produces: an importable app package and a pytest configuration used by all later tasks.

- [ ] **Step 1: Write the failing package smoke test**

~~~python
# tests/test_smoke.py
from app import __version__


def test_package_has_initial_version() -> None:
    assert __version__ == "0.1.0"
~~~

- [ ] **Step 2: Verify the smoke test fails**

Run: python -m pytest tests/test_smoke.py -v

Expected: FAIL with ModuleNotFoundError because app does not yet exist.

- [ ] **Step 3: Add the package metadata and initial files**

~~~toml
# pyproject.toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "telegram-sticker-converter"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
  "aiogram>=3,<4",
  "aiosqlite>=0.20,<1",
  "Pillow>=10,<12",
  "lottie>=0.7,<1",
]

[project.optional-dependencies]
dev = [
  "pytest>=8,<9",
  "pytest-asyncio>=0.24,<1",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
  "integration: runs real Pillow, Lottie, and FFmpeg conversions",
]
~~~

~~~python
# app/__init__.py
__version__ = "0.1.0"
~~~

~~~text
# .gitignore
.env
.venv/
__pycache__/
.pytest_cache/
*.py[cod]
data/
tmp/
~~~

~~~dotenv
# .env.example
BOT_TOKEN=replace-with-token-from-botfather
OWNER_TELEGRAM_ID=123456789
DATABASE_PATH=/data/sticker-bot.sqlite3
TEMP_ROOT=/tmp/sticker-bot
CONVERSION_CONCURRENCY=2
~~~

Create an empty tests/__init__.py.

- [ ] **Step 4: Install and run the smoke test**

Run: python -m pip install -e ".[dev]"

Expected: pip installs the four runtime dependencies and the two test dependencies.

Run: python -m pytest tests/test_smoke.py -v

Expected: PASS with one passing test.

- [ ] **Step 5: Commit the bootstrap**

~~~bash
git add pyproject.toml app/__init__.py tests/__init__.py tests/test_smoke.py .gitignore .env.example
git commit -m "chore: bootstrap sticker converter package"
~~~

### Task 2: Add Settings and Sticker Domain Objects

**Files:**
- Create: app/settings.py
- Create: app/models.py
- Create: tests/test_settings.py

**Interfaces:**
- Consumes: a mapping of environment variables and Telegram sticker flags.
- Produces: Settings.from_env(environ), StickerKind, StickerAsset, Invite, and sticker_kind(is_animated, is_video).

- [ ] **Step 1: Write the failing settings and classification tests**

~~~python
# tests/test_settings.py
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
~~~

- [ ] **Step 2: Verify the tests fail**

Run: python -m pytest tests/test_settings.py -v

Expected: FAIL with missing app.models and app.settings imports.

- [ ] **Step 3: Implement strict settings and immutable values**

~~~python
# app/settings.py
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
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
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
~~~

~~~python
# app/models.py
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
~~~

- [ ] **Step 4: Run the focused suite**

Run: python -m pytest tests/test_settings.py tests/test_smoke.py -v

Expected: PASS.

- [ ] **Step 5: Commit settings and domain values**

~~~bash
git add app/settings.py app/models.py tests/test_settings.py
git commit -m "feat: add bot settings and sticker models"
~~~

### Task 3: Implement SQLite Invitations and Authorization

**Files:**
- Create: app/database.py
- Create: app/access.py
- Create: tests/conftest.py
- Create: tests/test_access.py

**Interfaces:**
- Consumes: database path, Telegram user IDs, and invitation-code strings.
- Produces: AccessRepository.initialize(), AccessService.issue_invite() -> Invite, AccessService.redeem(code, user_id) -> RedeemResult, AccessService.is_authorized(user_id) -> bool, AccessService.list_invites() -> list[Invite], and AccessService.revoke(code) -> bool.

- [ ] **Step 1: Write failing invitation lifecycle tests**

~~~python
# tests/conftest.py
from pathlib import Path

import pytest

from app.database import AccessRepository


@pytest.fixture
async def repository(tmp_path: Path) -> AccessRepository:
    repo = AccessRepository(tmp_path / "test.sqlite3")
    await repo.initialize()
    yield repo
    await repo.close()
~~~

~~~python
# tests/test_access.py
import pytest

from app.access import AccessService, RedeemResult
from app.database import AccessRepository


@pytest.mark.asyncio
async def test_invitation_can_be_redeemed_once(repository: AccessRepository) -> None:
    service = AccessService(repository, code_factory=lambda: "friend-code")
    await service.issue_invite()

    assert await service.redeem(code="friend-code", user_id=100) is RedeemResult.REDEEMED
    assert await service.redeem(code="friend-code", user_id=200) is RedeemResult.CLAIMED
    assert await service.is_authorized(100)
    assert not await service.is_authorized(200)


@pytest.mark.asyncio
async def test_revoking_claimed_invite_removes_authorization(
    repository: AccessRepository,
) -> None:
    service = AccessService(repository, code_factory=lambda: "revoke-code")
    await service.issue_invite()
    await service.redeem(code="revoke-code", user_id=100)

    assert await service.revoke("revoke-code")
    assert not await service.is_authorized(100)
    assert await service.redeem(code="revoke-code", user_id=100) is RedeemResult.REVOKED


@pytest.mark.asyncio
async def test_unknown_invitation_is_invalid(repository: AccessRepository) -> None:
    service = AccessService(repository, code_factory=lambda: "unused")

    assert await service.redeem(code="missing", user_id=100) is RedeemResult.INVALID
~~~

- [ ] **Step 2: Verify the lifecycle tests fail**

Run: python -m pytest tests/test_access.py -v

Expected: FAIL with missing app.access and app.database imports.

- [ ] **Step 3: Implement the schema and atomic access service**

Create the following SQLite tables in AccessRepository.initialize():

~~~sql
CREATE TABLE IF NOT EXISTS invitations (
  code TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'claimed', 'revoked')),
  redeemed_by INTEGER UNIQUE,
  redeemed_at TEXT
);
CREATE TABLE IF NOT EXISTS authorized_users (
  user_id INTEGER PRIMARY KEY,
  invite_code TEXT NOT NULL UNIQUE REFERENCES invitations(code),
  authorized_at TEXT NOT NULL
);
~~~

Implement these exact result values:

~~~python
# app/access.py
from enum import StrEnum


class RedeemResult(StrEnum):
    REDEEMED = "redeemed"
    INVALID = "invalid"
    CLAIMED = "claimed"
    REVOKED = "revoked"
    ALREADY_AUTHORIZED = "already_authorized"
~~~

AccessRepository owns one aiosqlite connection opened from its Path, commits schema and writes, and closes it through close(). It maps invitation rows to models.Invite and provides methods to insert an active invite, fetch one invite, fetch a user authorization, atomically claim an active invite, delete an authorization by invitation code, and return invitations ordered by created_at.

AccessService accepts AccessRepository and an optional zero-argument code_factory. issue_invite() calls secrets.token_urlsafe(8) when code_factory is absent, retries uniqueness conflicts five times, and then raises RuntimeError("Unable to generate a unique invitation code"). redeem() checks existing user authorization first, returns the matching result for a missing, claimed, or revoked code, then claims the active invite and inserts the authorization in the same transaction. revoke() marks the invitation revoked and deletes its matching authorized user in one transaction.

- [ ] **Step 4: Run the access tests**

Run: python -m pytest tests/test_access.py -v

Expected: PASS with both lifecycle tests passing.

- [ ] **Step 5: Commit authorization persistence**

~~~bash
git add app/database.py app/access.py tests/conftest.py tests/test_access.py
git commit -m "feat: add invitation authorization storage"
~~~

### Task 4: Build Isolated, Bounded Media Conversion

**Files:**
- Create: app/workspace.py
- Create: app/converters.py
- Create: tests/test_converters.py

**Interfaces:**
- Consumes: StickerAsset, a downloaded source path, a writable task directory, ffmpeg, and lottie_convert.py.
- Produces: task_workspace(root), ConversionService.convert(asset, source, task_dir), and ConversionError.

- [ ] **Step 1: Write failing static conversion and cleanup tests**

~~~python
# tests/test_converters.py
from pathlib import Path

import pytest
from PIL import Image

from app.converters import ConversionService
from app.models import StickerAsset, StickerKind
from app.workspace import task_workspace


@pytest.mark.asyncio
async def test_static_webp_becomes_png(tmp_path: Path) -> None:
    source = tmp_path / "sticker.webp"
    Image.new("RGBA", (16, 16), (255, 0, 0, 128)).save(source, "WEBP")
    output = await ConversionService(1).convert(
        asset=StickerAsset("file", "unique", StickerKind.STATIC),
        source=source,
        task_dir=tmp_path,
    )

    assert output.suffix == ".png"
    assert Image.open(output).mode == "RGBA"


@pytest.mark.asyncio
async def test_workspace_is_removed_after_exception(tmp_path: Path) -> None:
    created: Path
    with pytest.raises(RuntimeError):
        async with task_workspace(tmp_path) as created:
            raise RuntimeError("conversion failed")

    assert not created.exists()
~~~

- [ ] **Step 2: Verify the conversion tests fail**

Run: python -m pytest tests/test_converters.py -v

Expected: FAIL with missing app.converters and app.workspace imports.

- [ ] **Step 3: Implement workspace cleanup and conversion commands**

~~~python
# app/workspace.py
import shutil
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path


@asynccontextmanager
async def task_workspace(root: Path) -> AsyncIterator[Path]:
    root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="conversion-", dir=root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
~~~

In app/converters.py, define ConversionError(RuntimeError) and ConversionService(concurrency: int). The constructor validates concurrency >= 1 and retains asyncio.Semaphore(concurrency). convert() acquires that semaphore and returns the result Path.

For StickerKind.STATIC, use asyncio.to_thread to open source with Pillow, convert to RGBA, and save task_dir / "result.png" with PNG format.

For StickerKind.ANIMATED, use asyncio.create_subprocess_exec with captured stdout and stderr:

~~~text
lottie_convert.py <source> <task_dir>/result.gif
~~~

For StickerKind.VIDEO, use asyncio.create_subprocess_exec with captured stdout and stderr:

~~~text
ffmpeg -y -i <source> -filter_complex [0:v]split[a][b];[a]palettegen[p];[b][p]paletteuse <task_dir>/result.gif
~~~

If either subprocess returns a nonzero exit status or fails to create the result GIF, raise ConversionError containing the decoded stderr. Do not impose a timeout or change frame timing.

- [ ] **Step 4: Run fast conversion tests**

Run: python -m pytest tests/test_converters.py -v

Expected: PASS for static conversion and workspace cleanup.

- [ ] **Step 5: Commit conversion services**

~~~bash
git add app/workspace.py app/converters.py tests/test_converters.py
git commit -m "feat: add isolated sticker conversion service"
~~~

### Task 5: Add Private-Chat Routes and Owner Commands

**Files:**
- Create: app/handlers.py
- Create: app/main.py
- Create: tests/test_handlers.py

**Interfaces:**
- Consumes: AccessService, ConversionService, task_workspace, Settings, aiogram Message, and aiogram Bot.
- Produces: build_router(access, converter, temp_root, owner_telegram_id) and run_bot(settings).

- [ ] **Step 1: Write failing private-chat and sticker-routing tests**

~~~python
# tests/test_handlers.py
from app.handlers import is_private_chat, should_download_sticker, sticker_asset_from_flags
from app.models import StickerKind


def test_only_private_chat_is_eligible_for_processing() -> None:
    assert is_private_chat("private")
    assert not is_private_chat("group")
    assert not is_private_chat("supergroup")
    assert not is_private_chat("channel")


def test_group_and_unauthorized_messages_never_download_stickers() -> None:
    assert not should_download_sticker(chat_type="group", is_authorized=True)
    assert not should_download_sticker(chat_type="private", is_authorized=False)
    assert should_download_sticker(chat_type="private", is_authorized=True)


def test_video_sticker_routes_to_video_conversion() -> None:
    asset = sticker_asset_from_flags(
        file_id="file",
        file_unique_id="unique",
        is_animated=False,
        is_video=True,
    )

    assert asset.kind is StickerKind.VIDEO
~~~

- [ ] **Step 2: Verify handler tests fail**

Run: python -m pytest tests/test_handlers.py -v

Expected: FAIL with missing app.handlers import.

- [ ] **Step 3: Implement private-only router behavior**

~~~python
# app/handlers.py
def is_private_chat(chat_type: str) -> bool:
    return chat_type == "private"


def should_download_sticker(*, chat_type: str, is_authorized: bool) -> bool:
    return is_private_chat(chat_type) and is_authorized


def sticker_asset_from_flags(
    *, file_id: str, file_unique_id: str, is_animated: bool, is_video: bool
) -> StickerAsset:
    return StickerAsset(
        file_id=file_id,
        file_unique_id=file_unique_id,
        kind=sticker_kind(is_animated=is_animated, is_video=is_video),
    )
~~~

build_router() registers /start, /invite, /invites, /revoke, and the sticker route with aiogram private-chat filters only. It registers no group route.

The /start handler expects one invitation argument and calls access.redeem(code=code, user_id=message.from_user.id). Map every RedeemResult to concise Chinese replies. The owner commands compare message.from_user.id with owner_telegram_id before calling the access service. A non-owner receives: 无权限使用管理命令。 The owner can create a code, list code status with redeemer ID, and revoke a supplied code.

The sticker route calls access.is_authorized(message.from_user.id), then calls should_download_sticker(chat_type=message.chat.type, is_authorized=result) before calling Bot.get_file. If the private user is unauthorized, reply: 请先使用邀请码启动 Bot。 and return. If the chat is not private, return without replying. For an authorized private user, derive StickerAsset from message.sticker flags, create a task workspace, call Bot.get_file, download to task_dir / "source", call converter.convert(), and send its Path through FSInputFile and message.answer_document. Catch ConversionError, call logger.exception, and reply: 转换失败，请稍后重试。 The workspace context must encompass the download, conversion, and upload so it cleans up every media file.

main.py reads Settings.from_env(os.environ), initializes AccessRepository, constructs AccessService and ConversionService, includes the router in Dispatcher, starts Bot polling, and closes the repository in finally after polling returns.

- [ ] **Step 4: Run handler and full fast suites**

Run: python -m pytest tests/test_handlers.py -v

Expected: PASS.

Run: python -m pytest -m "not integration" -v

Expected: PASS with settings, access, workspace, static conversion, and handler tests.

- [ ] **Step 5: Commit bot routing**

~~~bash
git add app/handlers.py app/main.py tests/test_handlers.py
git commit -m "feat: handle private sticker conversions"
~~~

### Task 6: Containerize, Document, and Verify Real Media Conversion

**Files:**
- Create: Dockerfile
- Create: compose.yaml
- Create: .dockerignore
- Create: README.md
- Modify: tests/test_converters.py

**Interfaces:**
- Consumes: the package from Tasks 1-5 and variables in .env.
- Produces: Docker targets runtime and test, Compose service bot, deployment documentation, and integration tests for TGS and WEBM.

- [ ] **Step 1: Write failing real-format tests**

Append these tests to tests/test_converters.py:

~~~python
import gzip
import json
import subprocess


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tgs_becomes_readable_gif(tmp_path: Path) -> None:
    source = tmp_path / "sticker.tgs"
    animation = {
        "v": "5.7.4", "fr": 30, "ip": 0, "op": 30, "w": 32, "h": 32,
        "nm": "dot", "ddd": 0, "assets": [], "layers": [],
    }
    with gzip.open(source, "wt", encoding="utf-8") as stream:
        json.dump(animation, stream)

    output = await ConversionService(1).convert(
        asset=StickerAsset("file", "unique", StickerKind.ANIMATED),
        source=source,
        task_dir=tmp_path,
    )

    assert output.suffix == ".gif"
    assert Image.open(output).format == "GIF"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_webm_becomes_readable_gif(tmp_path: Path) -> None:
    source = tmp_path / "sticker.webm"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=32x32:d=1", str(source)],
        check=True,
        capture_output=True,
    )

    output = await ConversionService(1).convert(
        asset=StickerAsset("file", "unique", StickerKind.VIDEO),
        source=source,
        task_dir=tmp_path,
    )

    assert output.suffix == ".gif"
    assert Image.open(output).format == "GIF"
~~~

- [ ] **Step 2: Verify integration prerequisites**

Run: python -m pytest -m integration -v

Expected: FAIL when the local machine lacks lottie_convert.py or ffmpeg. If both tools are already installed, this command can pass; record that fact and still run the container test in Step 4.

- [ ] **Step 3: Add Docker runtime and test targets**

~~~dockerfile
# Dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

FROM base AS test
COPY tests ./tests
RUN pip install --no-cache-dir ".[dev]"

FROM base AS runtime
CMD ["python", "-m", "app.main"]
~~~

~~~yaml
# compose.yaml
services:
  bot:
    build:
      context: .
      target: runtime
    env_file: .env
    volumes:
      - bot-data:/data
    restart: unless-stopped

volumes:
  bot-data:
~~~

~~~text
# .dockerignore
.git
.env
.venv
.pytest_cache
__pycache__
data
tmp
docs
~~~

Write README.md with these operational commands:

~~~bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f bot
docker compose up -d --build
~~~

The README must say to replace BOT_TOKEN and OWNER_TELEGRAM_ID in .env, state that the service opens no ports, and require outbound network access to Telegram.

- [ ] **Step 4: Build the test image and run every test inside it**

Run: docker build --target test -t telegram-sticker-converter:test .

Expected: the image builds with Pillow WebP support, lottie_convert.py, and ffmpeg.

Run: docker run --rm telegram-sticker-converter:test python -m pytest -v

Expected: PASS, including static, TGS, and WEBM output tests.

- [ ] **Step 5: Build the production Compose service without real credentials**

Run: docker compose build bot

Expected: the runtime image builds successfully and Compose reports no published ports.

- [ ] **Step 6: Commit deployment artifacts**

~~~bash
git add Dockerfile compose.yaml .dockerignore README.md tests/test_converters.py
git commit -m "feat: containerize sticker converter bot"
~~~

## Final Verification

- [ ] Run: python -m pytest -m "not integration" -v

  Expected: every fast unit test passes.

- [ ] Run: docker build --target test -t telegram-sticker-converter:test .

  Expected: the test image builds successfully.

- [ ] Run: docker run --rm telegram-sticker-converter:test python -m pytest -v

  Expected: every unit and real-format integration test passes.

- [ ] Inspect compose.yaml.

  Expected: one bot service, no ports section, persistent bot-data volume, and restart: unless-stopped.

- [ ] Confirm .env remains ignored and only .env.example is tracked before the final commit.
