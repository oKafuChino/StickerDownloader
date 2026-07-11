# Telegram Sticker Converter Bot Design

## Goal

Build a lightweight, invite-only Telegram Bot for a small circle of friends. In a
private chat, an authorized user sends a native Telegram sticker and receives a
converted file automatically:

- Static stickers (`.webp`) become PNG files.
- Animated stickers (`.tgs`) become GIF files.
- Video stickers (`.webm`) become GIF files.

The bot is packaged with Docker and runs on a Debian or Ubuntu VPS. The first
version uses no web UI, no group support, no message queue, no Redis, no object
storage, and no user-facing conversion settings.

## User Flow

1. The owner creates a single-use invitation code through an owner-only bot
   command and sends it to a friend.
2. The friend opens a private chat with the bot and redeems the code with
   `/start <code>`.
3. The code is permanently associated with that Telegram user ID and cannot be
   redeemed again. The owner can later revoke the code and its authorization.
4. An authorized user sends a native sticker in a private chat.
5. The bot detects the sticker type, downloads its source file, converts it,
   sends the PNG or GIF as a document, and deletes all task files.

Messages from group chats, supergroups, channels, and unrecognized media types
are ignored. They are never downloaded or processed.

## Architecture

The service is a single Python process built with `aiogram`, using Telegram Bot
API long polling. It makes outbound HTTPS connections only; the VPS needs no
domain, inbound port, reverse proxy, or TLS setup.

```text
Private Telegram chat
  -> aiogram handlers
  -> access control (owner / authorized user)
  -> Telegram file download
  -> type-specific converter
  -> document upload to Telegram
  -> task directory cleanup
```

Modules have clear responsibilities:

- `main.py`: application startup, long polling, and dependency assembly.
- `settings.py`: validated environment configuration.
- `handlers.py`: `/start`, owner commands, private-chat validation, and sticker
  routing.
- `access.py`: invitation-code lifecycle and authorization checks.
- `database.py`: SQLite persistence for invitations and authorized users.
- `converters.py`: format detection and conversion entry points.
- `workspace.py`: per-task temporary directories and guaranteed cleanup.

## Conversion Rules

The Bot API's `is_animated` and `is_video` flags determine the conversion path;
the bot does not infer formats from filenames.

| Sticker type | Source | Output | Converter |
| --- | --- | --- | --- |
| Static | WEBP | PNG | Pillow with WebP support |
| Animated | TGS | GIF | `python-lottie` GIF exporter |
| Video | WEBM | GIF | FFmpeg |

Static PNG output preserves alpha transparency. GIF output uses the sticker's
original animation duration and timing. There are no product-level duration,
frame-rate, or file-size limits. Telegram Bot API download limits and the VPS's
available CPU, memory, and disk remain unavoidable runtime constraints.

Each request receives an isolated temporary directory. CPU-heavy conversion is
bounded by a small in-process semaphore, with excess requests waiting in memory.
The semaphore is a VPS protection mechanism, not a rejection rule. Every task
cleans its directory in a `finally` path whether download, conversion, or upload
succeeds or fails.

## Authorization and Administration

`OWNER_TELEGRAM_ID` identifies the sole administrator. Only that user can run:

- `/invite`: create one new random, single-use invitation code.
- `/invites`: list invitation status and the Telegram account that redeemed it.
- `/revoke <code>`: revoke an invitation and remove its recipient's access.

The SQLite database stores only the data required for authorization:

- invitations: code, creation time, status, redeemer Telegram user ID, and
  redemption time;
- authorized users: Telegram user ID, invitation code, and authorization state.

Sticker media and converted files are never stored persistently. Application logs
go to standard output for Docker to collect; no conversion history table is
needed in the first version.

## Failure Handling

- Unauthorized private users receive an invitation-required response and their
  stickers are not downloaded.
- Invalid, claimed, or revoked codes return a concise redemption error.
- Download, rendering, FFmpeg, or upload failures return a concise conversion
  failure message while logging the stage and technical error server-side.
- Cleanup failures are logged without obscuring the original conversion result.
- Process failures rely on the Docker restart policy; a persistent SQLite volume
  retains authorization state across restarts.

## Container Deployment

The Docker image contains Python, FFmpeg, WebP-capable Pillow dependencies, and
`python-lottie`. Docker Compose runs one bot container with:

- a bind mount or named volume for the SQLite data directory;
- an `.env` file for `BOT_TOKEN`, `OWNER_TELEGRAM_ID`, `DATABASE_PATH`, and the
  internal conversion concurrency setting;
- a restart policy such as `unless-stopped`;
- no published ports.

The repository includes `.env.example` but never real credentials. The target
host needs Docker and Docker Compose plus outbound access to Telegram.

## Testing and Acceptance Criteria

Unit tests cover invitation creation, redemption, duplicate redemption,
revocation, owner-only command checks, private-chat checks, and sticker-path
selection. Converter command construction and cleanup behavior are tested with
mocks.

Integration tests use local sample WEBP, TGS, and WEBM files to verify each
converter produces a readable PNG or GIF without contacting Telegram. A Docker
build test verifies all runtime conversion dependencies are present.

The first release is accepted when:

1. An owner can create, inspect, and revoke invitations.
2. A user can redeem one invitation only in a private chat.
3. An authorized user receives PNG for static stickers and GIF for animated and
   video stickers without selecting a format.
4. Group messages and unauthorized stickers are never downloaded or converted.
5. Failed and successful tasks leave no media files behind.
6. The container restarts cleanly while preserving authorization state.
