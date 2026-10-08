# Jev PoC result 20261006T021139Z_r2a_enriched

model jev-1.13.0, questions q-2026-10-06-r2a, confidence threshold 0.6, findings 33 (errors 0)

| metric | value |
| --- | --- |
| Disposition match | 24/33 (73%) |
| TP missed (Jev said FP or Benign) | 0/24 |
| Undetermined share | 6/33 (18%) |
| Urgency exact match | 23/33 (70%) |
| Urgency within 1 level | 29/33 (88%) |

Disposition confusion (rows = ground truth, columns = Jev):

| truth \ Jev | TP | FP | Benign | Undetermined |
| --- | --- | --- | --- | --- |
| TP | 20 | 0 | 0 | 4 |
| FP | 0 | 1 | 0 | 0 |
| Benign | 0 | 0 | 1 | 0 |
| Undetermined | 3 | 0 | 2 | 2 |

| # | rule | truth | Jev | disp conf | truth urg | Jev urg | policy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | BOTS - Excessive Failed Logins | TP | TP | 1.0 | low | low |  |
| 2 | BOTS - Excessive Failed Logins | TP | TP | 1.0 | low | low |  |
| 3 | BOTS - SSH Brute Force Detected | TP | TP | 1.0 | low | low |  |
| 4 | BOTS - SSH Brute Force Detected | TP | TP | 1.0 | low | low |  |
| 5 | BOTS - Unexpected Source Firewall Blocks | Undetermined | TP ✗ | 0.93 | medium | medium |  |
| 6 | BOTS - AWS EC2 Instance Created | TP | TP | 0.97 | critical | critical |  |
| 7 | 24 hour risk threshold exceeded for system=5.101.40.81 | TP | TP | 1.0 | low | low |  |
| 8 | 24 hour risk threshold exceeded for system=167.114.13.150 | TP | TP | 1.0 | low | low |  |
| 9 | BOTS - Suspicious PowerShell Execution | TP | TP | 0.97 | high | high |  |
| 10 | BOTS - Suspicious PowerShell Execution | Undetermined | TP ✗ | 0.99 | medium | high |  |
| 11 | BOTS - Suspicious PowerShell Execution | Undetermined | Undetermined | 0.46 | medium | medium | low confidence 0.46 |
| 12 | BOTS - Suspicious PowerShell Execution | Undetermined | TP ✗ | 0.99 | medium | high |  |
| 13 | BOTS - Watchlist Service Account AWS Activity | TP | TP | 0.99 | critical | critical |  |
| 14 | BOTS - Watchlist Service Account AWS Activity | Benign | Benign | 0.98 | low | low |  |
| 15 | BOTS - Risk Threshold Exceeded | TP | TP | 1.0 | high | critical |  |
| 16 | BOTS - Risk Threshold Exceeded | TP | TP | 1.0 | low | low |  |
| 17 | BOTS - Risk Threshold Exceeded | TP | TP | 1.0 | low | low |  |
| 18 | 24 hour risk threshold exceeded for user=web_admin | TP | TP | 0.98 | high | critical |  |
| 19 | Excessive Failed Logins | TP | TP | 1.0 | low | low |  |
| 20 | Excessive Failed Logins | TP | TP | 1.0 | low | low |  |
| 21 | Network Change Detected On ec2.amazonaws.com | Undetermined | Benign ✗ | 0.76 | medium | medium |  |
| 22 | Network Change Detected On ec2.amazonaws.com | TP | Undetermined ✗ | 0.34 | medium | critical | low confidence 0.34 |
| 23 | Network Change Detected On ec2.amazonaws.com | Undetermined | Undetermined | 0.58 | medium | medium | low confidence 0.58 |
| 24 | Network Change Detected On ec2.amazonaws.com | Undetermined | Benign ✗ | 0.87 | medium | medium |  |
| 25 | 24 hour risk threshold exceeded for system=ec2.amazonaws.com | TP | Undetermined ✗ | 0.29 | medium | critical | low confidence 0.29 / order check disagreed (benign) |
| 26 | 24 hour risk threshold exceeded for system=5.101.40.81 | TP | TP | 1.0 | low | low |  |
| 27 | 24 hour risk threshold exceeded for system=167.114.13.150 | TP | TP | 1.0 | low | low |  |
| 28 | Finding Group Template - Entity Exceeded Risk Threshold | TP | TP | 1.0 | low | low |  |
| 29 | Finding Group Template - Entity Exceeded Risk Threshold | TP | TP | 0.99 | high | critical |  |
| 30 | Finding Group Template - Entity Exceeded Risk Threshold | TP | Undetermined ✗ | 0.58 | medium | critical | low confidence 0.58 |
| 31 | Finding Group Template - Entity Exceeded Risk Threshold | TP | TP | 1.0 | low | low |  |
| 32 | Default Account Activity Detected | FP | FP | 0.96 | medium | low |  |
| 33 | BOTS - Risk Threshold Exceeded | TP | Undetermined ✗ | 0.52 | medium | critical | low confidence 0.52 |
