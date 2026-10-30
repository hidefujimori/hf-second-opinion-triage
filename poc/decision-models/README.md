# Decision models compared with Jev (2026-10-21, 2026-10-26)

33 labelled findings (ground_truth_v5.csv), same enrichment and questions (q-2026-10-06-r2a), app 0.9.15,
`jevtriage endpoint=... model=...` on the on-premises Splunk (results not stored). Rules unchanged:
disposition Undetermined when confidence < 0.60 or the option-order check disagrees.

| Model | Where | Disposition | Raw choice | Urgency (±1) | TP missed | Confidence median | Latency median / max |
|---|---|---|---|---|---|---|---|
| Jev jev-1.13.0 | TypeSafe API | **32/33** | 31/33 | **31/33** (33/33) | 0 | 0.99 | 154 / 305 ms |
| Kev-4B Q8_0 | llama.cpp, RTX 5060 Ti | 2/33 | 16/33 | 15/33 (26/33) | 0 | 0.25 | 462 / 1660 ms |
| Clef-Flash Q4_K_M | llama.cpp, RTX 5060 Ti | 19/33 | 30/33 | 24/33 (27/33) | 0 | 0.65 | 560 / 2202 ms |
| Kev-9B Q8_0 | llama.cpp, RTX 5060 Ti | 3/33 | 23/33 | 15/33 (27/33) | 0 | 0.43 | 909 / 2914 ms |
| **Clef 27B Q4_K_M** | llama.cpp (Homebrew, Metal), MacBook Pro M4 48 GB | 23/33 (**30/33 at 0.45**) | **32/33** | **31/33 (33/33)** | 0 | 0.68 | 20.0 / 24.2 s |
| Kev-27B v2 Q4_K_M (community GGUF) | same Mac | 18/33 | 21/33 | 28/33 (29/33) | 0 | 0.57 | 26.6 / 45.0 s |

Notes
- 2026-10-26 runs (Mac, one request at a time) used app 0.9.16 `jevtriage ... parallel=1 timeout=180`; the first try
  with the default parallel 4 / timeout 30 timed out (llama-server log: "cancel task").
- Clef 27B: most likely choice 32/33 - FP (#32) and Benign (#14) right; its only miss is #5, which Jev misses too.
  Urgency misses #22 and #32, the same as Jev. Confidence runs lower than Jev's: threshold 0.60 -> 23/33,
  0.50 -> 28/33, 0.45 -> 30/33, 0.40 -> 31/33, always with one wrong non-Undetermined answer (#5). The FP finding has
  confidence 0.21, so it stays Undetermined at any of these thresholds. The threshold was chosen on these 33 findings.
- Kev-27B: FP and Benign right, but "undetermined" for many TP findings (21/33).
- Kev-4B: low confidence on every finding (0.15-0.36), often chooses "undetermined": all 33 end as Undetermined.
- Clef-Flash: chooses true_positive for 31 of 33. Raw 30/33 mostly reflects the share of TP in the set (29/33).
  On the 4 non-TP findings it was right once (#11 undetermined); FP (#32) and Benign (#14) were called TP
  (confidence 0.30 / 0.05, so Undetermined after the rule). With a 0.40 threshold: 30/33, but only because TP dominates.
- Clef-Flash urgency: 6 Low findings raised to High, both Critical findings given High.
- Jev latency is per call over the internet; local latency includes the GPU (one model at a time for Clef-Flash).
- Caveats: questions and thresholds were tuned on Jev; non-TypeSafe servers get a "compatible" form of the questions
  (score levels and yes/no criteria as plain text); local models are small and quantized.

Files: `run_2026-10-21_jev_kev.txt`, `run_2026-10-21_clef.txt`, `run_2026-10-26_kev9.txt`, `run_2026-10-26_clef27.txt`, `run_2026-10-26_kev27.txt` (id, status, disposition, raw, confidence, urgency,
urgency confidence, latency ms), `score.py`.

## Laya (Convai Innovations, laya 0.4.17, 2026-10-30)

laya-serve on the GPU server (RTX 5060 Ti, `tools/local-decision/setup_laya.sh`), app 0.11.7,
`jevtriage endpoint=... model=<checkpoint> conffield=answer_confidence parallel=2 timeout=60`, 33 labelled findings
(ground_truth_v5). Baseline "always TP" = 29/33.

| Checkpoint | Options | Disposition (policy) | Raw choice | TP missed | Urgency exact | ±1 | Median latency |
|---|---|---|---|---|---|---|---|
| laya-multilingual | max_len 4096 | 18/33 | 27/33 (TP for 29 of 33) | 12 | 14/33 | 17/33 | 45 ms |
| laya-typed-decisions | max_len 4096 | 2/33 | 19/33 | 29 | 10/33 | 18/33 | 102 ms |
| laya (English, 512 tokens) | — | 7/33 | 16/33 | 24 | 19/33 | 28/33 | 93 ms |
| (reference) Jev 1.13 | | 32/33 | | 0 | 31/33 | 33/33 | ~154 ms |
| (reference) Clef 27B Q4 | threshold 0.45 | 30/33 | 32/33 | 0 | 31/33 | 33/33 | ~20 s (Mac) |

- No checkpoint separates FP / Benign / Undetermined from TP: the multilingual one answers TP for nearly everything
  (below the always-TP baseline), the others are close to random. The yes/no question `requires_escalation` is
  almost always high, so the policy raises urgency to High (the noul bias the model card warns about).
- Requests are 1,400–2,000 tokens per call; the multilingual checkpoint with max_len 4096 reads them whole.
- Conclusion: **not usable without fine-tuning** on labelled security findings (we have 33, far too few).
  The app keeps the support for it (`request_extra`, `confidence_field`) for a fine-tuned checkpoint.

## Cloudflare Clef / Clef-flash on Workers AI (hosted, 2026-10-30)

App 0.11.8, `jevtriage endpoint="https://api.cloudflare.com/client/v4/accounts/<id>/ai/run/@cf/cloudflare/clef"
model="clef" usekey=alt parallel=4 timeout=60` (Workers AI token saved as "API key for evaluation"), 33 labelled
findings, free plan. One run = 61,505 input tokens (both calls of all 33 findings): about 1,340 neurons for Clef,
500 for Clef-flash, of the 10,000 free per day.

| Model | Raw choice | Disposition at 0.60 / 0.45 / 0.15 | TP missed at 0.15 | Wrong decided | Urgency (±1) | Latency median / max |
|---|---|---|---|---|---|---|
| Clef (hosted) | **32/33** | 16 / 17 / **31** | 0 | 1 (#5, also missed by Jev) | **31/33 (33/33)** | 504 / 1175 ms |
| Clef-flash (hosted) | 30/33 (TP for all 33) | 2 / 13 / 28 | 2 | 1 | 24/33 (27/33) | 432 / 559 ms |

- Hosted Clef chooses as well as the local Clef 27B Q4 (raw 32/33, FP #32 and Benign #14 right; urgency 31/33 with the
  same misses as Jev), but its confidence is much lower (median 0.52; correct TP answers from 0.19): the 0.60 rule turns
  half of the correct answers into Undetermined. With `confidence_threshold = 0.15` it reaches 31/33, no TP missed —
  the threshold was chosen on these 33 findings, so re-check it on more data. The option-order check disagreed on 2
  (#32 FP at confidence 0.08, #11).
- Clef-flash (hosted) behaves like the local Clef-Flash: true_positive for every finding.
- Latency over the internet: ~0.5 s per call (Jev ~0.15 s). Price: Clef $0.24 / 1M input tokens (Jev $0.042).
