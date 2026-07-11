# Telegram Sticker Converter Bot

一个轻量、仅限邀请使用的 Telegram Bot。授权用户在私聊中发送 Telegram
原生贴纸后，Bot 会自动回传对应文件：

- 静态 WEBP 贴纸转换为 PNG。
- 动态 TGS 贴纸转换为 GIF。
- 视频 WEBM 贴纸转换为 GIF。

Bot 不处理群聊消息，也不会持久保存贴纸文件。

## 部署要求

- Debian 或 Ubuntu VPS。
- Git 和 curl。
- Docker Engine 和 Docker Compose。
- 能够从 VPS 访问 Telegram Bot API。
- 无需域名、反向代理、TLS 证书或开放入站端口。

## 一键安装

在已经安装 Docker 的 VPS 上运行：

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/oKafuChino/StickerDownloader/main/install.sh)"
```

脚本会隐藏输入 Bot Token，并要求输入管理员的 Telegram 数字用户 ID，
然后把项目安装到 `~/sticker-downloader`、生成权限为 `0600` 的 `.env`，
最后构建并启动容器。脚本不会安装 Docker、修改系统软件包或开放端口。

可通过 `INSTALL_DIR` 自定义安装目录：

```bash
INSTALL_DIR=/opt/sticker-downloader bash -c "$(curl -fsSL https://raw.githubusercontent.com/oKafuChino/StickerDownloader/main/install.sh)"
```

自定义目录必须允许当前用户写入；脚本不会自动使用 `sudo`。

## 配置

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env`：

- `BOT_TOKEN`：从 BotFather 获取的 Bot Token。
- `OWNER_TELEGRAM_ID`：管理员的 Telegram 数字用户 ID。
- `DATABASE_PATH`：SQLite 路径，Compose 默认使用 `/data/sticker-bot.sqlite3`。
- `TEMP_ROOT`：媒体临时目录，默认 `/tmp/sticker-bot`。
- `CONVERSION_CONCURRENCY`：同时转换任务数，小型 VPS 建议使用 `1` 或 `2`。

## 启动与更新

```bash
docker compose up -d --build
docker compose logs -f bot
```

拉取新版本后重新构建：

```bash
docker compose up -d --build
```

## 使用方式

管理员命令：

- `/invite`：创建一个一次性邀请码。
- `/invites`：查看邀请码状态和兑换用户 ID。
- `/revoke <邀请码>`：撤销邀请码及其关联用户权限。

朋友在私聊中发送 `/start <邀请码>` 完成授权。管理员账号无需邀请码。
授权后直接发送贴纸即可，Bot 会自动识别类型并回传 PNG 或 GIF 文件。

## 测试镜像

在有 Docker 的环境中构建并运行完整测试：

```bash
docker build --target test -t telegram-sticker-converter:test .
docker run --rm telegram-sticker-converter:test python -m pytest -v
```
