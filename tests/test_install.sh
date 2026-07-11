#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

FAKE_BIN="$TEST_ROOT/bin"
INSTALL_DIR="$TEST_ROOT/sticker-downloader"
DOCKER_LOG="$TEST_ROOT/docker.log"
mkdir -p "$FAKE_BIN"

cat >"$FAKE_BIN/curl" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF

cat >"$FAKE_BIN/git" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "${1:-}" == "clone" ]]; then
  target="${@: -1}"
  mkdir -p "$target/.git"
  exit 0
fi
if [[ "${1:-}" == "-C" && "${3:-}" == "remote" ]]; then
  printf '%s\n' 'https://github.com/oKafuChino/StickerDownloader.git'
fi
exit 0
EOF

cat >"$FAKE_BIN/docker" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "${1:-}" == "compose" && "${2:-}" == "version" ]]; then
  exit 0
fi
if [[ "${1:-}" == "info" ]]; then
  exit 0
fi
printf '%s\n' "$*" >>"$DOCKER_LOG"
EOF

chmod +x "$FAKE_BIN/curl" "$FAKE_BIN/git" "$FAKE_BIN/docker"

printf '123456:secret-token\n987654321\n' | env \
  PATH="$FAKE_BIN:$PATH" \
  INSTALL_DIR="$INSTALL_DIR" \
  DOCKER_LOG="$DOCKER_LOG" \
  bash "$ROOT_DIR/install.sh"

test -f "$INSTALL_DIR/.env"
grep -qx 'BOT_TOKEN=123456:secret-token' "$INSTALL_DIR/.env"
grep -qx 'OWNER_TELEGRAM_ID=987654321' "$INSTALL_DIR/.env"
grep -qx 'DATABASE_PATH=/data/sticker-bot.sqlite3' "$INSTALL_DIR/.env"
grep -qx 'TEMP_ROOT=/tmp/sticker-bot' "$INSTALL_DIR/.env"
grep -qx 'CONVERSION_CONCURRENCY=2' "$INSTALL_DIR/.env"
test "$(stat -c '%a' "$INSTALL_DIR/.env")" = "600"
grep -qx 'compose up -d --build' "$DOCKER_LOG"
grep -qx 'compose ps' "$DOCKER_LOG"

INVALID_DIR="$TEST_ROOT/invalid-owner"
if printf '123456:secret-token\nnot-a-number\n' | env \
  PATH="$FAKE_BIN:$PATH" \
  INSTALL_DIR="$INVALID_DIR" \
  DOCKER_LOG="$DOCKER_LOG" \
  bash "$ROOT_DIR/install.sh"; then
  printf '%s\n' 'expected invalid owner ID to fail' >&2
  exit 1
fi
test ! -e "$INVALID_DIR/.env"

UNRELATED_DIR="$TEST_ROOT/unrelated"
mkdir -p "$UNRELATED_DIR"
printf '%s\n' 'keep me' >"$UNRELATED_DIR/existing.txt"
if printf '123456:secret-token\n987654321\n' | env \
  PATH="$FAKE_BIN:$PATH" \
  INSTALL_DIR="$UNRELATED_DIR" \
  DOCKER_LOG="$DOCKER_LOG" \
  bash "$ROOT_DIR/install.sh"; then
  printf '%s\n' 'expected unrelated directory to be rejected' >&2
  exit 1
fi
grep -qx 'keep me' "$UNRELATED_DIR/existing.txt"
test ! -e "$UNRELATED_DIR/.env"

printf '%s\n' 'installer behavior tests passed'
