# 🧩 Telegram Sticker Converter Bot

一个轻量、仅限邀请使用的 Telegram Bot。授权用户在私聊中发送 Telegram
原生贴纸后，Bot 会自动识别贴纸类型并回传对应文件。

## ✨ 功能

- 🖼️ 静态 WEBP 贴纸转换为透明 PNG。
- 🎞️ 动态 TGS 贴纸转换为透明 GIF。
- 🎬 视频 WEBM 贴纸转换为透明 GIF。
- 🔐 每位朋友使用独立、可追踪、可撤销的一次性邀请码。
- 💬 仅支持与 Bot 私聊，不处理群聊消息。
- 🧹 转换文件只在临时目录中使用，完成后自动清理。

## 📦 部署要求

- Debian 或 Ubuntu VPS。
- Git 和 curl。
- Docker Engine 和 Docker Compose 插件。
- VPS 能够访问 Telegram Bot API。
- 无需域名、反向代理、TLS 证书或开放入站端口。

> ℹ️ 安装脚本不会安装 Docker、修改系统软件包、调用 `sudo` 或开放端口。

## 🚀 一键安装

在已经安装 Docker 的 VPS 上运行：

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/oKafuChino/StickerDownloader/main/install.sh)"
```

脚本会隐藏输入 Bot Token，并要求输入管理员的 Telegram 数字用户 ID，随后：

1. 将项目安装到 `~/sticker-downloader`。
2. 生成权限为 `0600` 的 `.env` 配置文件。
3. 构建容器并等待 Bot 健康启动。

使用其他安装目录：

```bash
INSTALL_DIR=/opt/sticker-downloader bash -c "$(curl -fsSL https://raw.githubusercontent.com/oKafuChino/StickerDownloader/main/install.sh)"
```

自定义目录必须允许当前用户写入。

## 🔄 一键更新

从尚未包含 `update.sh` 的旧版本首次启用短命令时，先执行一次：

```bash
cd ~/sticker-downloader && git pull --ff-only origin main
```

之后的日常更新不再需要手动输入 Git 或 Docker Compose 命令。

默认安装目录只需执行：

```bash
bash ~/sticker-downloader/update.sh
```

自定义安装目录使用：

```bash
INSTALL_DIR=/opt/sticker-downloader bash /opt/sticker-downloader/update.sh
```

更新脚本会拉取 `main` 分支最新版本、重新构建容器并等待健康检查通过。

> 🛡️ 更新不会重新询问 Token，不会修改 `.env`，也不会删除 SQLite 数据库或
> Docker 数据卷。服务器存在冲突的本地代码修改时，更新会直接停止，不会强制覆盖。

查看运行状态和日志：

```bash
cd ~/sticker-downloader
docker compose ps
docker compose logs -f bot
```

## 🤖 使用方式

朋友在 Bot 私聊中发送 `/start <邀请码>` 完成授权。管理员账号无需邀请码。
授权用户发送贴纸后，Bot 会先回复“已收到贴纸，正在转换，请稍等。”，持续显示
“正在输入”状态，随后回传 PNG 或 GIF 文件。

普通指令：

- `/start <邀请码>`：使用邀请码完成授权。
- `/help`：查看可用指令。
- 直接发送贴纸：自动识别并转换。

管理员指令：

- `/invite`：创建一个一次性邀请码。
- `/invites`：查看邀请码状态和兑换用户 ID。
- `/revoke <邀请码>`：撤销邀请码及其关联用户权限。

除 `/start <邀请码>` 外，其他功能只允许已授权用户和管理员使用。

## ⚙️ 配置

手动部署时复制环境变量模板：

```bash
cp .env.example .env
```

配置项：

- `BOT_TOKEN`：从 BotFather 获取的 Bot Token。
- `OWNER_TELEGRAM_ID`：管理员的 Telegram 数字用户 ID。
- `DATABASE_PATH`：SQLite 路径，Compose 默认使用 `/data/sticker-bot.sqlite3`。
- `TEMP_ROOT`：媒体临时目录，默认使用 `/tmp/sticker-bot`。
- `CONVERSION_CONCURRENCY`：同时处理的转换任务数，小型 VPS 建议使用 `1` 或 `2`。
- `MAX_PENDING_CONVERSIONS`：允许等待的转换任务数，默认 `8`；设为 `0` 时不排队。

手动启动：

```bash
docker compose up -d --build --wait --wait-timeout 60
```

## 🧪 测试

在有 Docker 的环境中运行 Python 与真实媒体转换测试：

```bash
docker build --target test -t telegram-sticker-converter:test .
docker run --rm telegram-sticker-converter:test python -m pytest -v
```

联网检查 Python 依赖的已知安全漏洞：

```bash
docker run --rm telegram-sticker-converter:test python -m pip_audit
```

在 Debian、Ubuntu 或其他 Linux 环境中测试安装和更新脚本：

```bash
bash tests/test_install.sh
bash tests/test_update.sh
```
