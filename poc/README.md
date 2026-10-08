# Jev triage PoC

Sends the 33 test-environment findings (`findings_snapshot.jsonl`) to Jev and compares the
answers with the reviewed ground truth (`../ground_truth_v1.csv`).

## Setup (once)
1. Create `../.env` (in the Jev_triage folder) with one line:
   `TYPESAFE_API_KEY=<your key from console.typesafe.ai>`
   Do not paste the key into chat.
2. `api.typesafe.ai` must be reachable (session network allowlist).

## Run
- `python3 run_poc.py --dry-run`  : show the English state sent per finding, no API calls
- `python3 run_poc.py --only 1,6` : try a few findings
- `python3 run_poc.py`            : all 33 (about 66 calls incl. the option-order check)

Outputs: `results_<time>.jsonl` (raw), `results_<time>.csv`, `report_<time>.md` (metrics, confusion table).

## Files
- `jev_questions_r2a.json` : questions in use (round 2, default)
- `jev_questions.json` : round 1 questions; `jev_questions_r2b.json` : variant without the undetermined option (rejected)
- `run_poc.py`         : state building, Jev calls, policy (confidence < 0.60 -> undetermined), report
