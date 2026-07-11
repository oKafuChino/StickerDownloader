# One-Command Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Add a secure interactive installer that deploys StickerDownloader with one command on a Docker-ready Debian or Ubuntu VPS.

**Architecture:** A root-level Bash script validates prerequisites, safely collects credentials, clones or updates the repository, atomically writes .env, and invokes Docker Compose. A shell behavior test replaces git and docker with stubs so installation paths can be checked without a real deployment.

**Tech Stack:** Bash, Git, Docker Compose, curl.

## Global Constraints

- Do not install Docker or host packages.
- Default INSTALL_DIR to $HOME/sticker-downloader.
- Never place BOT_TOKEN in command history or echo it during input.
- Refuse unrelated non-empty installation directories.
- Do not use sudo, delete user files, or publish ports.

---

### Task 1: Installer Behavior

**Files:**
- Create: install.sh
- Create: tests/test_install.sh

**Interfaces:**
- Consumes: INSTALL_DIR, interactive BOT_TOKEN and OWNER_TELEGRAM_ID, git, docker, and docker compose.
- Produces: a cloned or updated checkout, mode-0600 .env, and docker compose up -d --build.

- [ ] Write tests that put stub git and docker commands first on PATH, feed a token and numeric owner ID through standard input, and assert that .env contains the five expected keys and docker compose up -d --build was invoked.
- [ ] Run bash tests/test_install.sh and observe failure because install.sh does not exist.
- [ ] Implement install.sh with set -Eeuo pipefail, prerequisite checks, hidden token input, numeric owner validation, safe clone/update handling, atomic .env replacement, and Compose startup.
- [ ] Run bash -n install.sh and bash tests/test_install.sh; both must exit 0.
- [ ] Commit with git add install.sh tests/test_install.sh and git commit -m "feat: add one-command installer".

### Task 2: Deployment Documentation

**Files:**
- Modify: README.md

**Interfaces:**
- Consumes: the public raw GitHub URL for install.sh.
- Produces: a copyable one-line install command and explicit prerequisites.

- [ ] Add a one-command section before manual configuration using:

~~~bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/oKafuChino/StickerDownloader/main/install.sh)"
~~~

- [ ] State that Git, curl, Docker Engine, and Docker Compose must already be installed and that the script installs no host packages.
- [ ] Check README references install.sh and the exact raw GitHub URL.
- [ ] Commit with git add README.md and git commit -m "docs: add one-command deployment".

