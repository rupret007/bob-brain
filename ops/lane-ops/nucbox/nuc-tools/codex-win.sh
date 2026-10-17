#!/bin/bash
# Invoke the Windows Codex desktop CLI from WSL using the existing Windows sign-in.
# Never reads/copies/prints/modifies auth.json. Never login/logout.
# ChatGPT-account-compatible model: gpt-6-astra (Windows config default gpt-5.4 is NOT supported).
set -euo pipefail
BIN_ROOT="/mnt/c/Users/rupret/AppData/Local/OpenAI/Codex/bin"
CODEX_EXE=""
if [ -d "$BIN_ROOT" ]; then
  # Prefer newest bin dir that contains codex.exe
  CODEX_EXE=$(ls -td "$BIN_ROOT"/*/codex.exe 2>/dev/null | head -1 || true)
fi
if [ -z "${CODEX_EXE}" ] || [ ! -x "${CODEX_EXE}" ]; then
  echo "BLOCKER: Windows codex.exe not found under $BIN_ROOT" >&2
  exit 2
fi
MODEL="${CODEX_MODEL:-gpt-6-astra}"
# Force model on every call so a stale Windows config default cannot break lanes.
exec "$CODEX_EXE" -m "$MODEL" "$@"
