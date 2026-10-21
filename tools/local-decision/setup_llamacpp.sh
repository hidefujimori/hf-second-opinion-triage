#!/usr/bin/env bash
# Local decision models for TA-jev-triage evaluation: llama.cpp llama-server with the /v1/systemone API.
# Target: Ubuntu 22.04 / 24.04 (test server 172.26.1.20). Run as a user with sudo.
#   bash setup_llamacpp.sh            # build llama.cpp (CUDA if an NVIDIA GPU is found) and download the models
#   bash setup_llamacpp.sh --service  # also install systemd services (kev-4b on 8081, clef-flash on 8082)
# Models (Apache 2.0, from Hugging Face ggml-org):
#   Kev-4B      ggml-org/Kev-4B-GGUF:Q8_0          ~4.5 GB   port 8081
#   Clef-Flash  ggml-org/Clef-Flash-GGUF:Q4_K_M    ~6.5 GB   port 8082
# Needs llama.cpp with the /v1/systemone endpoint (PR #29818) and Clef support (PR #29831): latest master.
set -euo pipefail

PREFIX="${PREFIX:-$HOME/llama.cpp}"
MODELS="${MODELS:-$HOME/models}"
KEV_REPO="${KEV_REPO:-ggml-org/Kev-4B-GGUF:Q8_0}"
CLEF_REPO="${CLEF_REPO:-ggml-org/Clef-Flash-GGUF:Q4_K_M}"
KEV_PORT="${KEV_PORT:-8081}"
CLEF_PORT="${CLEF_PORT:-8082}"
CTX="${CTX:-16384}"

log() { printf '\n== %s\n' "$*"; }

log "1/5 packages"
sudo apt-get update -y
sudo apt-get install -y build-essential cmake git curl libcurl4-openssl-dev pkg-config

GPU=cpu
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
  GPU=cuda
  nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv
  if ! command -v nvcc >/dev/null 2>&1 && [ ! -x /usr/local/cuda/bin/nvcc ]; then
    echo "NVIDIA GPU found but the CUDA toolkit (nvcc) is missing."
    echo "Install it (e.g. sudo apt-get install -y nvidia-cuda-toolkit) and run this script again,"
    echo "or run with FORCE_CPU=1 to build without CUDA."
    [ "${FORCE_CPU:-0}" = 1 ] && GPU=cpu || exit 1
  fi
  export PATH="/usr/local/cuda/bin:$PATH"
fi
[ "${FORCE_CPU:-0}" = 1 ] && GPU=cpu
log "build target: $GPU"

log "2/5 llama.cpp source ($PREFIX)"
if [ -d "$PREFIX/.git" ]; then git -C "$PREFIX" pull --ff-only; else git clone --depth 1 https://github.com/ggml-org/llama.cpp "$PREFIX"; fi
git -C "$PREFIX" log -1 --format='commit %h %cd'

log "3/5 build"
cd "$PREFIX"
if [ "$GPU" = cuda ]; then cmake -B build -DGGML_CUDA=ON -DLLAMA_CURL=ON; else cmake -B build -DLLAMA_CURL=ON; fi
cmake --build build --config Release -j"$(nproc)" --target llama-server
"$PREFIX/build/bin/llama-server" --version || true
"$PREFIX/build/bin/llama-server" --help 2>&1 | grep -qi systemone && echo "systemone: found in --help" || echo "note: 'systemone' not shown in --help (check with test_systemone.sh)"

log "4/5 models (downloaded on first start into the llama.cpp cache)"
mkdir -p "$MODELS"
for r in "$KEV_REPO" "$CLEF_REPO"; do
  echo "pre-fetch $r"
  timeout 1800 "$PREFIX/build/bin/llama-server" -hf "$r" --port 18999 >/tmp/llama-prefetch.log 2>&1 &
  pid=$!
  for i in $(seq 1 360); do
    if curl -sf http://127.0.0.1:18999/health >/dev/null 2>&1; then break; fi
    kill -0 $pid 2>/dev/null || break
    sleep 5
  done
  kill $pid 2>/dev/null || true; wait $pid 2>/dev/null || true
  tail -3 /tmp/llama-prefetch.log
done

NGL=""; [ "$GPU" = cuda ] && NGL="-ngl 99"
cat > "$MODELS/run_kev.sh" <<RUN
#!/usr/bin/env bash
exec "$PREFIX/build/bin/llama-server" -hf $KEV_REPO --host 0.0.0.0 --port $KEV_PORT -c $CTX -b 4096 -ub 4096 $NGL --alias kev-4b \${LLAMA_API_KEY:+--api-key \$LLAMA_API_KEY}
RUN
cat > "$MODELS/run_clef_flash.sh" <<RUN
#!/usr/bin/env bash
exec "$PREFIX/build/bin/llama-server" -hf $CLEF_REPO --host 0.0.0.0 --port $CLEF_PORT -c $CTX -b 4096 -ub 4096 $NGL --alias clef-flash \${LLAMA_API_KEY:+--api-key \$LLAMA_API_KEY}
RUN
chmod +x "$MODELS/run_kev.sh" "$MODELS/run_clef_flash.sh"
echo "start scripts: $MODELS/run_kev.sh (port $KEV_PORT), $MODELS/run_clef_flash.sh (port $CLEF_PORT)"

if [ "${1:-}" = "--service" ]; then
  log "5/5 systemd services"
  for n in kev clef_flash; do
    sudo tee /etc/systemd/system/llama-$n.service >/dev/null <<UNIT
[Unit]
Description=llama.cpp decision model ($n) for TA-jev-triage tests
After=network-online.target

[Service]
User=$USER
Environment=HOME=$HOME
ExecStart=$MODELS/run_$n.sh
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT
  done
  sudo systemctl daemon-reload
  sudo systemctl enable --now llama-kev llama-clef_flash
  systemctl --no-pager --lines=3 status llama-kev llama-clef_flash || true
else
  log "5/5 skipped (run with --service to install systemd services, or start the scripts by hand)"
fi
echo
echo "Next: bash test_systemone.sh 127.0.0.1 $KEV_PORT && bash test_systemone.sh 127.0.0.1 $CLEF_PORT"
