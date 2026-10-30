#!/bin/sh
# Install ytdl on macOS or Linux: curl -LsSf https://raw.githubusercontent.com/Pratham71/YtDownloader/main/scripts/install.sh | sh
set -eu

if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

uv tool install --force --python 3.12 git+https://github.com/Pratham71/YtDownloader.git
uv tool update-shell || true

echo
echo "ytdl is installed. Open a new terminal and run: ytdl doctor"
