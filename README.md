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
- 整包下载需要公网可访问的 HTTP(S) 地址；下载服务默认端口为 `18080`，可使用 HTTPS 反向代理。

> ℹ️ 安装脚本不会安装 Docker、修改系统软件包或调用 `sudo`。Compose 会映射下载端口，防火墙与 HTTPS 由管理员配置。

## 🚀 一键安装

在已经安装 Docker 的 VPS 上运行：

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/oKafuChino/StickerDownloader/main/install.sh)"
```

脚本会隐藏输入 Bot Token，并要求输入管理员的 Telegram 数字用户 ID 和公网下载地址，随后：

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
- `/getpack <贴纸包链接>`：将整包静态贴纸转为 PNG、动态和视频贴纸转为 GIF，打包 ZIP 后返回临时下载链接。
- 直接发送贴纸：自动识别并转换。

管理员指令：

- `/invite`：创建一个一次性邀请码。
- `/invites`：查看邀请码状态和兑换用户 ID。
- `/revoke <邀请码>`：撤销邀请码及其关联用户权限。

除 `/start <邀请码>` 外，其他功能只允许已授权用户和管理员使用。

`/getpack` 会在同一条状态消息中显示进度条、百分比和已转换数量，并标明当前
正在下载、转换或打包。进度按已转换的贴纸数量计算，不代表字节下载百分比；
中途更新通常最多每 2 秒一次，打包阶段单独提示，完成后原消息显示临时下载链接。

整包输出按原顺序命名为 `001.png`、`002.gif` 等。PNG 保留原始尺寸和完整 Alpha，
不会额外进行有损压缩；TGS 按原尺寸逐帧渲染，GIF 使用逐帧调色板和抖动，
不主动缩小尺寸或降低帧率。GIF 格式最多 256 色且只能表示完全透明或不透明，
帧延时精度为 10 毫秒，因此半透明边缘、渐变及帧时长无法与原始动画完全一致。
转换不会恢复源文件已丢失的细节。

ZIP 只包含转换结果，有效期默认 1 小时，重启后旧链接失效。转换后 ZIP 上限为
200 MiB；超限会提示失败，不会为缩小文件而静默降低画质。服务器最多同时保留
20 个待过期文件，持有链接的人可在有效期内下载，请勿公开转发。

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
- `PUBLIC_BASE_URL`：临时 ZIP 下载服务的公网 HTTPS 地址，例如 `https://download.example.com`。
- `DOWNLOAD_PORT`：下载服务端口，默认 `18080`；Compose 的宿主机与容器端口均跟随此配置。
- `DOWNLOAD_TTL_SECONDS`：下载链接有效期，默认 `3600` 秒；Bot 重启后所有旧链接失效。

手动启动：

旧部署如果在 `.env` 中设置过 `DOWNLOAD_PORT=8080`，请改为 `DOWNLOAD_PORT=18080`，
并同步更新反向代理的上游端口或防火墙规则。`update.sh` 会保留已有 `.env`，
所以旧值不会自动被覆盖。HTTPS 域名作为公网地址时通常无需修改域名；若使用
IP 加端口直连，`PUBLIC_BASE_URL` 也应包含 `:18080`。

例如直连配置（将地址替换为实际公网 IP；公网部署优先使用 HTTPS）：

```env
PUBLIC_BASE_URL=http://203.0.113.10:18080
DOWNLOAD_PORT=18080
```

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
