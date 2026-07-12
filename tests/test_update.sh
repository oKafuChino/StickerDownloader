#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

FAKE_BIN="$TEST_ROOT/bin"
GIT_LOG="$TEST_ROOT/git.log"
DOCKER_LOG="$TEST_ROOT/docker.log"
mkdir -p "$FAKE_BIN"

cat >"$FAKE_BIN/git" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "${1:-}" == "-C" && "${3:-}" == "remote" ]]; then
  printf '%s\n' "$FAKE_ORIGIN"
  exit 0
fi
printf '%s\n' "$*" >>"$GIT_LOG"
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

chmod +x "$FAKE_BIN/git" "$FAKE_BIN/docker"

run_update() {
  local install_dir="$1"
  local origin="$2"
  env \
    PATH="$FAKE_BIN:$PATH" \
    INSTALL_DIR="$install_dir" \
    FAKE_ORIGIN="$origin" \
    GIT_LOG="$GIT_LOG" \
    DOCKER_LOG="$DOCKER_LOG" \
    bash "$ROOT_DIR/update.sh"
}

INSTALL_DIR="$TEST_ROOT/sticker-downloader"
mkdir -p "$INSTALL_DIR/.git"
printf '%s\n' 'BOT_TOKEN=preserve-me' >"$INSTALL_DIR/.env"

run_update "$INSTALL_DIR" 'https://github.com/oKafuChino/StickerDownloader.git'

grep -qx -- "-C $INSTALL_DIR pull --ff-only origin main" "$GIT_LOG"
grep -qx 'compose up -d --build --wait --wait-timeout 60' "$DOCKER_LOG"
grep -qx 'compose ps' "$DOCKER_LOG"
grep -qx 'BOT_TOKEN=preserve-me' "$INSTALL_DIR/.env"

: >"$GIT_LOG"
: >"$DOCKER_LOG"
MISSING_GIT="$TEST_ROOT/missing-git"
mkdir -p "$MISSING_GIT"
printf '%s\n' 'BOT_TOKEN=preserve-me' >"$MISSING_GIT/.env"
if run_update "$MISSING_GIT" 'https://github.com/oKafuChino/StickerDownloader.git'; then
  printf '%s\n' 'expected a directory without .git to fail' >&2
  exit 1
fi
test ! -s "$GIT_LOG"
test ! -s "$DOCKER_LOG"

MISSING_ENV="$TEST_ROOT/missing-env"
mkdir -p "$MISSING_ENV/.git"
if run_update "$MISSING_ENV" 'https://github.com/oKafuChino/StickerDownloader.git'; then
  printf '%s\n' 'expected a directory without .env to fail' >&2
  exit 1
fi
test ! -s "$GIT_LOG"
test ! -s "$DOCKER_LOG"

UNRELATED="$TEST_ROOT/unrelated"
mkdir -p "$UNRELATED/.git"
printf '%s\n' 'BOT_TOKEN=preserve-me' >"$UNRELATED/.env"
if run_update "$UNRELATED" 'https://github.com/example/unrelated.git'; then
  printf '%s\n' 'expected an unrelated repository to fail' >&2
  exit 1
fi
test ! -s "$GIT_LOG"
test ! -s "$DOCKER_LOG"

printf '%s\n' 'updater behavior tests passed'
