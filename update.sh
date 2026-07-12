#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPOSITORY_URL="https://github.com/oKafuChino/StickerDownloader.git"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${INSTALL_DIR:-$SCRIPT_DIR}"

fail() {
  printf '更新失败：%s\n' "$1" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "缺少必要命令：$1"
}

require_command git
require_command docker

docker compose version >/dev/null 2>&1 || fail "Docker Compose 插件不可用"
docker info >/dev/null 2>&1 || fail "无法连接 Docker，请确认当前用户有权限访问 Docker daemon"

[[ -d "$INSTALL_DIR" ]] || fail "安装目录不存在：$INSTALL_DIR"
[[ -d "$INSTALL_DIR/.git" ]] || fail "目标目录不是 Git 仓库：$INSTALL_DIR"
[[ -f "$INSTALL_DIR/.env" ]] || fail "缺少配置文件：$INSTALL_DIR/.env"

origin_url="$(git -C "$INSTALL_DIR" remote get-url origin 2>/dev/null || true)"
case "$origin_url" in
  "$REPOSITORY_URL"|https://github.com/oKafuChino/StickerDownloader|git@github.com:oKafuChino/StickerDownloader.git)
    ;;
  *)
    fail "目标目录不是 StickerDownloader 仓库：$INSTALL_DIR"
    ;;
esac

printf '正在拉取最新版本 ...\n'
git -C "$INSTALL_DIR" pull --ff-only origin main

printf '正在重新构建并启动 Bot ...\n'
(
  cd "$INSTALL_DIR"
  docker compose up -d --build --wait --wait-timeout 60
  docker compose ps
)

printf '\n更新完成。\n'
printf '查看日志：cd %q && docker compose logs -f bot\n' "$INSTALL_DIR"
