#!/usr/bin/env bash
# Laya (Convai Innovations, Apache 2.0) for Second Opinion Triage evaluation: laya-serve with the Jev-compatible
# POST /v1/systemone API. Laya is a small encoder model (ModernBERT / mmBERT, ~0.4B): a CPU works, a GPU is faster.
#
#   bash setup_laya.sh            install into ~/laya-venv (once)
#   bash setup_laya.sh run        start laya-serve on port 8086 (foreground; Ctrl-C to stop)
#
# Security: laya-serve has no authentication unless LAYA_API_KEY is set. For the evaluation the app sends no key
# to an endpoint given in the search, so run it WITHOUT a key and allow the port from the Splunk search head only:
#   sudo ufw allow from <splunk-search-head> to any port 8086 proto tcp
set -euo pipefail
VENV="${LAYA_VENV:-$HOME/laya-venv}"
PORT="${LAYA_PORT:-8086}"

if [ "${1:-install}" = "install" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -U pip
  "$VENV/bin/pip" install "laya[serve]"
  "$VENV/bin/python" -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
  echo "Installed. Start with: bash $0 run"
  exit 0
fi

DEVICE=cpu
if "$VENV/bin/python" -c "import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)"; then DEVICE=cuda; fi
echo "laya-serve on 0.0.0.0:$PORT (device $DEVICE)"
LAYA_HOST=0.0.0.0 LAYA_PORT="$PORT" LAYA_DEVICE="$DEVICE" LAYA_PRELOAD=1 \
LAYA_MAX_TOKEN_BUDGET=8192 \
  exec "$VENV/bin/laya-serve"
