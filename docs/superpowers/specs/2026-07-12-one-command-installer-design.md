# One-Command Installer Design

## Goal

Provide one command for deploying StickerDownloader on a Debian or Ubuntu VPS
that already has Git, curl, Docker Engine, and Docker Compose:

~~~bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/oKafuChino/StickerDownloader/main/install.sh)"
~~~

The installer does not install Docker or modify operating-system packages.

## Installation Flow

The repository contains a root-level install.sh script. It performs these steps
in order:

1. Verify that git, docker, and docker compose are available.
2. Verify that the Docker daemon is reachable by the current user.
3. Prompt for BOT_TOKEN without echoing it and prompt for a numeric
   OWNER_TELEGRAM_ID.
4. Use INSTALL_DIR when supplied; otherwise install to
   $HOME/sticker-downloader.
5. Clone the repository on first installation. When the target is already this
   repository, fetch and update it with a fast-forward-only pull.
6. Create .env with umask 077 so credentials are readable only by the owner.
7. Preserve the fixed container paths from .env.example and use a default
   conversion concurrency of 2.
8. Run docker compose up -d --build from the installation directory.
9. Print the service status and the commands for viewing logs and updating.

## Security Boundaries

The Bot token is read interactively and is never placed in the one-line command
or shell history. install.sh writes values with printf-style arguments rather
than evaluating user input. It rejects empty tokens and non-numeric Telegram
user IDs.

The one-line command executes the current main-branch installer from GitHub.
This is convenient but trusts the current repository state. Release
documentation will recommend replacing main with a version tag after tagged
releases exist.

The installer refuses to overwrite a non-empty target directory that is not a
checkout of the StickerDownloader repository. It does not use sudo, delete user
files, open firewall ports, or install host packages.

## Repeated Runs and Failure Handling

Repeated runs update an existing repository with git pull --ff-only and rewrite
.env only after valid input has been collected. A temporary .env file is moved
into place atomically, so interrupted input cannot destroy the prior
configuration.

Every prerequisite or deployment failure exits nonzero with a concise message.
If docker compose build or startup fails, the repository and .env remain in
place for diagnosis. The installer prints docker compose logs -f bot as the
diagnostic command.

## Documentation and Verification

README.md will add a one-command deployment section before the manual deployment
steps. It will list Git, curl, Docker, and Docker Compose as prerequisites and
state that the command does not install Docker.

Static verification will run bash -n install.sh in a Linux or Git Bash
environment. Behavior checks will cover missing commands, invalid owner IDs,
refusal to overwrite an unrelated directory, first clone, existing-checkout
update, secure .env generation, and the final Compose invocation using stub
executables so no real deployment is started.

