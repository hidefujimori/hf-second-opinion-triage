#!/usr/bin/env bash
# Run a 27B decision model on an Apple Silicon Mac (Metal) for TA-jev-triage evaluation.
#   bash mac_llamacpp.sh clef27     # Cloudflare Clef 27B  (ggml-org/Clef-GGUF:Q4_K_M, ~19 GB)  port 8084
#   bash mac_llamacpp.sh kev27      # Kev-27B v2           (kdercksen/Kev-27B-GGUF Q4_K_M, ~16 GB) port 8085
#   bash mac_llamacpp.sh kev9       # Kev-9B               (ggml-org/Kev-9B-GGUF:Q8_0, ~9.5 GB)  port 8083
# One model at a time (48 GB Mac). Stops with Ctrl+C. The Mac stays awake while it runs (caffeinate).
# First run downloads the model to ~/Library/Caches/llama.cpp.
set -euo pipefail
case "${1:-}" in
  clef27) REPO="ggml-org/Clef-GGUF:Q4_K_M"; PORT=8084; ALIAS=clef-27b ;;
  kev27)  REPO="kdercksen/Kev-27B-GGUF:Q4_K_M"; PORT=8085; ALIAS=kev-27b ;;
  kev9)   REPO="ggml-org/Kev-9B-GGUF:Q8_0"; PORT=8083; ALIAS=kev-9b ;;
  *) echo "usage: bash $0 clef27|kev27|kev9"; exit 1 ;;
esac

if ! command -v llama-server >/dev/null 2>&1; then
  command -v brew >/dev/null 2>&1 || { echo "Homebrew is needed: https://brew.sh"; exit 1; }
  brew install llama.cpp
elif [ "${UPGRADE:-1}" = 1 ]; then
  brew upgrade llama.cpp 2>/dev/null || true     # /v1/systemone and Clef need a recent build
fi
llama-server --version 2>&1 | head -2

IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "<this Mac's IP>")
echo
echo "Model $ALIAS ($REPO) on http://$IP:$PORT/v1/systemone"
echo "If macOS asks whether llama-server may accept incoming connections, choose Allow."
echo "Check from the Splunk server: curl -s http://$IP:$PORT/health"
echo
exec caffeinate -i llama-server -hf "$REPO" --host 0.0.0.0 --port "$PORT" \
  -c 8192 -np 1 -ngl 99 -b 4096 -ub 4096 --alias "$ALIAS"
