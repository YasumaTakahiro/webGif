#!/usr/bin/env bash
# ポート WEBGIF_PORT（既定 5055）で待ち受け中の webGif サーバーを停止
set -euo pipefail

PORT="${WEBGIF_PORT:-5055}"
stopped=0

if command -v fuser >/dev/null 2>&1; then
  if fuser "${PORT}/tcp" >/dev/null 2>&1; then
    fuser -k "${PORT}/tcp" >/dev/null 2>&1 || true
    stopped=1
  fi
elif command -v lsof >/dev/null 2>&1; then
  pids=$(lsof -ti ":${PORT}" 2>/dev/null || true)
  if [[ -n "${pids}" ]]; then
    # shellcheck disable=SC2086
    kill ${pids} 2>/dev/null || true
    stopped=1
  fi
else
  echo "webGif: fuser / lsof が見つかりません。" >&2
  exit 1
fi

sleep 0.3

if [[ "${stopped}" -eq 1 ]]; then
  echo "webGif: ポート ${PORT} のサーバーを停止しました。"
else
  echo "webGif: ポート ${PORT} で動作中のサーバーはありません。"
fi
