#!/usr/bin/env bash
set -euo pipefail
cd /workspace
export MAX_UPLOAD_MB="${MAX_UPLOAD_MB:-0}"
exec /opt/venv/bin/python -u app.py
