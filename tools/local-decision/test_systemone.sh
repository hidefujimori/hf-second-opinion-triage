#!/usr/bin/env bash
# Send a Jev-style request (state + typed questions) to a /v1/systemone endpoint and print the answer.
#   bash test_systemone.sh <host> <port>        e.g. bash test_systemone.sh <gpu-server> 8081
# Set LLAMA_API_KEY if the server was started with --api-key.
set -euo pipefail
HOST="${1:-127.0.0.1}"; PORT="${2:-8081}"
URL="http://$HOST:$PORT/v1/systemone"
AUTH=(); [ -n "${LLAMA_API_KEY:-}" ] && AUTH=(-H "Authorization: Bearer $LLAMA_API_KEY")
read -r -d '' BODY <<'JSON' || true
{
 "model": "local",
 "state": "{\"alert_type\": \"single detection\", \"detection\": \"BOTS - SSH Brute Force Detected\", \"description\": \"SSH brute force from an internet address: several failures across 3 usernames, no successful login.\", \"context_from_siem\": [\"traffic outcome: no successful login from this source\"]}",
 "questions": {
  "disposition": {"type": "choice", "instructions": "What is the disposition of this alert?",
                  "criteria": {"true_positive": "real malicious or policy-violating activity",
                               "false_positive": "the detection logic fired on activity that does not match its intent",
                               "benign": "real activity that is expected or authorised",
                               "undetermined": "the facts are not enough to decide"}},
  "urgency": {"type": "score", "instructions": "How urgent is this alert?",
              "criteria": ["Low: failed or blocked attempts", "Medium: needs checking today", "High: likely compromise", "Critical: active compromise with impact"]},
  "escalate": {"type": "noul", "instructions": "This alert should be escalated to the incident response team now."}
 }
}
JSON
echo "POST $URL"
ms() { python3 -c "import time; print(int(time.time()*1000))" 2>/dev/null || echo 0; }
t0=$(ms)
curl -sS -m 60 "${AUTH[@]}" -H 'Content-Type: application/json' -d "$BODY" "$URL" | (command -v python3 >/dev/null && python3 -m json.tool || cat)
echo "elapsed: $(( $(ms) - t0 )) ms"
