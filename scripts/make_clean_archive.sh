#!/usr/bin/env bash
set -euo pipefail

OUTPUT="${1:-russian-market-ai-analyst-starter-clean.zip}"
OUTPUT_DIR="$(dirname "$OUTPUT")"

if [[ -n "$OUTPUT_DIR" && "$OUTPUT_DIR" != "." ]]; then
  mkdir -p "$OUTPUT_DIR"
fi

if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git archive --format=zip --output "$OUTPUT" HEAD
else
  if ! command -v zip >/dev/null 2>&1; then
    echo "zip command not found" >&2
    exit 1
  fi

  tmp_archive="$(mktemp -t russian-market-ai-analyst-starter-clean.XXXXXX.zip)"
  rm -f "$tmp_archive"
  trap 'rm -f "$tmp_archive"' EXIT

  zip -qr "$tmp_archive" . \
    -x '.git/*' \
    -x '.DS_Store' \
    -x '__MACOSX/*' \
    -x '*/.DS_Store' \
    -x '*/__pycache__/*' \
    -x 'backend/.venv/*' \
    -x 'backend/venv/*' \
    -x 'backend/env/*' \
    -x 'backend/market_ai.db' \
    -x 'backend/data/signal_model_state.json' \
    -x '*.pyc' \
    -x '*.pyo' \
    -x '*.log'

  mv "$tmp_archive" "$OUTPUT"
  trap - EXIT
fi

echo "Created clean archive: $OUTPUT"
