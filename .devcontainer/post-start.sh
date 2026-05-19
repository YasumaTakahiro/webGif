#!/usr/bin/env bash
# Dev Container 起動時: Git / SSH の初期設定
set -euo pipefail

git config --global --add safe.directory /workspace 2>/dev/null || true

# ホストの .gitconfig をマウントしている場合（未設定時のみコピー）
if [[ -f /home/vscode/.host-gitconfig && ! -f /home/vscode/.gitconfig ]]; then
  cp /home/vscode/.host-gitconfig /home/vscode/.gitconfig
fi

# ホストからマウントした SSH 鍵の権限（厳しすぎると ssh が拒否する）
if [[ -d /home/vscode/.ssh ]]; then
  chmod 700 /home/vscode/.ssh 2>/dev/null || true
  find /home/vscode/.ssh -maxdepth 1 -type f -name 'id_*' ! -name '*.pub' \
    -exec chmod 600 {} + 2>/dev/null || true
fi

# uploads / DB: bind mount 由来の root 所有を vscode に揃える
mkdir -p /workspace/uploads /tmp/webgif-uploads
if command -v sudo >/dev/null 2>&1; then
  sudo chown -R vscode:vscode /workspace/uploads /workspace/webgif.db /tmp/webgif-uploads 2>/dev/null || true
fi
chmod u+rwX /workspace/uploads /tmp/webgif-uploads 2>/dev/null || true
