#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPOSITORY_URL="https://github.com/oKafuChino/StickerDownloader.git"
readonly DEFAULT_INSTALL_DIR="$HOME/sticker-downloader"
INSTALL_DIR="${INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"

fail() {
  printf '安装失败：%s\n' "$1" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "缺少必要命令：$1"
}

require_command curl
require_command git
require_command docker

docker compose version >/dev/null 2>&1 || fail "Docker Compose 插件不可用"
docker info >/dev/null 2>&1 || fail "无法连接 Docker，请确认当前用户有权限访问 Docker daemon"

printf 'Bot Token：' >&2
IFS= read -r -s BOT_TOKEN || fail "未读取到 Bot Token"
printf '\n' >&2
[[ -n "$BOT_TOKEN" ]] || fail "Bot Token 不能为空"

printf '管理员 Telegram 数字用户 ID：' >&2
IFS= read -r OWNER_TELEGRAM_ID || fail "未读取到 Telegram 用户 ID"
[[ "$OWNER_TELEGRAM_ID" =~ ^[0-9]+$ ]] || fail "Telegram 用户 ID 必须是数字"

if [[ -e "$INSTALL_DIR" && ! -d "$INSTALL_DIR" ]]; then
  fail "目标路径不是目录：$INSTALL_DIR"
elif [[ -d "$INSTALL_DIR/.git" ]]; then
  origin_url="$(git -C "$INSTALL_DIR" remote get-url origin 2>/dev/null || true)"
  case "$origin_url" in
    "$REPOSITORY_URL"|https://github.com/oKafuChino/StickerDownloader|git@github.com:oKafuChino/StickerDownloader.git)
      ;;
    *)
      fail "目标目录是其他 Git 仓库：$INSTALL_DIR"
      ;;
  esac
  printf '正在更新 %s ...\n' "$INSTALL_DIR"
  git -C "$INSTALL_DIR" pull --ff-only origin main
elif [[ -e "$INSTALL_DIR" ]] && [[ -n "$(find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
  fail "目标目录非空且不是 StickerDownloader 仓库：$INSTALL_DIR"
else
  mkdir -p "$(dirname "$INSTALL_DIR")"
  printf '正在安装到 %s ...\n' "$INSTALL_DIR"
  git clone --depth 1 "$REPOSITORY_URL" "$INSTALL_DIR"
fi

umask 077
temporary_env="$INSTALL_DIR/.env.tmp.$$"
cleanup() {
  rm -f "$temporary_env"
}
trap cleanup EXIT

printf '%s\n' \
  "BOT_TOKEN=$BOT_TOKEN" \
  "OWNER_TELEGRAM_ID=$OWNER_TELEGRAM_ID" \
  "DATABASE_PATH=/data/sticker-bot.sqlite3" \
  "TEMP_ROOT=/tmp/sticker-bot" \
  "CONVERSION_CONCURRENCY=2" \
  >"$temporary_env"
chmod 600 "$temporary_env"
mv -f "$temporary_env" "$INSTALL_DIR/.env"
trap - EXIT

printf '正在构建并启动 Bot ...\n'
(
  cd "$INSTALL_DIR"
  docker compose up -d --build --wait --wait-timeout 60
  docker compose ps
)

printf '\n安装完成。\n'
printf '查看日志：cd %q && docker compose logs -f bot\n' "$INSTALL_DIR"
printf '更新服务：bash %q/update.sh\n' "$INSTALL_DIR"
