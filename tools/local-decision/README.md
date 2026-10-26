# Local decision models (llama.cpp) for TA-jev-triage tests

Jev-compatible decision models served by llama.cpp's `/v1/systemone` endpoint, to compare with TypeSafe Jev
on the evaluation set (ground_truth_v5.csv) without sending data outside.

| Model | Repo (GGUF) | License | Port | Size |
|---|---|---|---|---|
| Kev-4B | `ggml-org/Kev-4B-GGUF:Q8_0` | Apache 2.0 | 8081 | ~4.5 GB |
| Clef-Flash (Cloudflare) | `ggml-org/Clef-Flash-GGUF:Q4_K_M` | Apache 2.0 | 8082 | ~6.5 GB |

## Option A: Docker (recommended when Docker is already there)

Uses the official llama.cpp server image (no build). For the GPU, the NVIDIA Container Toolkit must be installed
(check: `docker run --rm --gpus all ubuntu nvidia-smi` shows the GPU).

If that check fails with "failed to discover GPU vendor from CDI", install the toolkit once (restarts Docker, so
other containers such as Open WebUI restart too):
```
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
sudo systemctl restart docker
docker run --rm --gpus all ubuntu nvidia-smi
```
GPU memory (16 GB on the test server): Kev-4B Q8_0 and Clef-Flash Q4_K_M with 16K context need about 13 GB together.
Ollama shares the GPU: stop its models (`ollama stop <model>`) while evaluating, or start only one decision model.

```
docker compose up -d                 # kev-4b on 8081, clef-flash on 8082 (first start downloads the models)
docker compose logs -f kev           # wait for "server is listening"
bash test_systemone.sh 127.0.0.1 8081
bash test_systemone.sh 127.0.0.1 8082
```
CPU only: `LLAMA_IMAGE=ghcr.io/ggml-org/llama.cpp:server docker compose -f docker-compose.yml -f docker-compose.cpu.yml up -d`.
AMD GPU (Vulkan): `VIDEO_GID=$(getent group video | cut -d: -f3) RENDER_GID=$(getent group render | cut -d: -f3) LLAMA_IMAGE=ghcr.io/ggml-org/llama.cpp:server-vulkan docker compose -f docker-compose.yml -f docker-compose.amd.yml up -d`
(`docker compose logs kev` should show a Vulkan device and layers offloaded to the GPU).
If `/v1/systemone` answers 404, the image is older than the decision-model support: `docker compose pull && docker compose up -d`.
Decision models score the whole input in one pass: the physical batch size must be at least the input length
(`-b 4096 -ub 4096` in the commands; otherwise "input (N tokens) is too large to process").
To require a key, add `"--api-key", "<key>"` to each `command` and put the same key in the app's Setup page.

## Larger models

- **Kev-9B on the 16 GB GPU** (alone): `docker compose stop kev clef-flash && docker compose --profile kev9 up -d kev-9b` → port 8083.
- **27B models on an Apple Silicon Mac** (48 GB): `bash mac_llamacpp.sh clef27` (Clef 27B Q4_K_M, port 8084) or
  `bash mac_llamacpp.sh kev27` (Kev-27B v2 Q4_K_M, community GGUF, port 8085). One model at a time; Homebrew llama.cpp,
  Metal, `caffeinate` keeps the Mac awake. Allow incoming connections for llama-server when macOS asks.
  For evaluation only: a desktop Mac is not a server.

## Option B: native build (steps below)

## Steps (on the test server, e.g. Ubuntu 172.26.1.20)

1. Copy this folder to the server and run `bash setup_llamacpp.sh --service`
   (builds llama.cpp with CUDA when an NVIDIA GPU and the CUDA toolkit are present; otherwise CPU).
2. Check: `bash test_systemone.sh 127.0.0.1 8081` and `bash test_systemone.sh 127.0.0.1 8082`.
   The answer has `answers.disposition.choice`, `probabilities`, `confidence`.
3. Open the ports to the Splunk search head only (e.g. `sudo ufw allow from 172.26.10.100 to any port 8081:8082 proto tcp`).
   For anything beyond a test, start the servers with an API key (`LLAMA_API_KEY=... ` in the service) and put the
   same key in the app's Setup page.
4. From the Splunk server: `curl -s http://172.26.1.20:8081/health` → `{"status":"ok"}`.

GPU memory: Ollama on the same server keeps models loaded for a while (gemma4:26b needs ~17 GB). If the decision
models do not fit, stop Ollama models first (`ollama stop <model>`) or use smaller quantizations (`KEV_REPO=ggml-org/Kev-4B-GGUF:Q4_K_M`).

## Using them from the app (0.9.15+)

- Evaluation without changing settings (admin only, results are not saved):
  `` `jev_findings` | jevtriage endpoint="http://172.26.1.20:8081/v1/systemone" model="kev-4b" ``
- Or as the decision model for the app: Setup > TypeSafe Jev > Endpoint = `http://172.26.1.20:8081/v1/systemone`,
  Model = `kev-4b` (the API key may be left empty for a server without `--api-key`).
