# Decision models compared with Jev (2026-10-21)

33 labelled findings (ground_truth_v5.csv), same enrichment and questions (q-2026-10-06-r2a), app 0.9.15,
`jevtriage endpoint=... model=...` on the on-premises Splunk (results not stored). Rules unchanged:
disposition Undetermined when confidence < 0.60 or the option-order check disagrees.

| Model | Where | Disposition | Raw choice | Urgency (±1) | TP missed | Confidence median | Latency median / max |
|---|---|---|---|---|---|---|---|
| Jev jev-1.13.0 | TypeSafe API | **32/33** | 31/33 | **31/33** (33/33) | 0 | 0.99 | 154 / 305 ms |
| Kev-4B Q8_0 | llama.cpp, RTX 5060 Ti | 2/33 | 16/33 | 15/33 (26/33) | 0 | 0.25 | 462 / 1660 ms |
| Clef-Flash Q4_K_M | llama.cpp, RTX 5060 Ti | 19/33 | 30/33 | 24/33 (27/33) | 0 | 0.65 | 560 / 2202 ms |

Notes
- Kev-4B: low confidence on every finding (0.15-0.36), often chooses "undetermined": all 33 end as Undetermined.
- Clef-Flash: chooses true_positive for 31 of 33. Raw 30/33 mostly reflects the share of TP in the set (29/33).
  On the 4 non-TP findings it was right once (#11 undetermined); FP (#32) and Benign (#14) were called TP
  (confidence 0.30 / 0.05, so Undetermined after the rule). With a 0.40 threshold: 30/33, but only because TP dominates.
- Clef-Flash urgency: 6 Low findings raised to High, both Critical findings given High.
- Jev latency is per call over the internet; local latency includes the GPU (one model at a time for Clef-Flash).
- Caveats: questions and thresholds were tuned on Jev; non-TypeSafe servers get a "compatible" form of the questions
  (score levels and yes/no criteria as plain text); local models are small and quantized.

Files: `run_2026-10-21_jev_kev.txt`, `run_2026-10-21_clef.txt` (id, status, disposition, raw, confidence, urgency,
urgency confidence, latency ms), `score.py`.
