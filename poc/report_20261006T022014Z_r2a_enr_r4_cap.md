# Jev PoC result 20261006T022014Z_r2a_enr_r4_cap

model jev-1.13.0, questions q-2026-10-06-r2a, confidence threshold 0.6, findings 33 (errors 0)

| metric | value |
| --- | --- |
| Disposition match | 28/33 (85%) |
| TP missed (Jev said FP or Benign) | 0/26 |
| Undetermined share | 6/33 (18%) |
| Urgency exact match | 25/33 (76%) |
| Urgency within 1 level | 29/33 (88%) |

Disposition confusion (rows = ground truth, columns = Jev):

| truth \ Jev | TP | FP | Benign | Undetermined |
| --- | --- | --- | --- | --- |
| TP | 23 | 0 | 0 | 3 |
| FP | 0 | 1 | 0 | 0 |
| Benign | 0 | 0 | 1 | 0 |
| Undetermined | 2 | 0 | 0 | 3 |

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
| 9 | BOTS - Suspicious PowerShell Execution | TP | TP | 0.96 | high | high |  |
| 10 | BOTS - Suspicious PowerShell Execution | TP | TP | 0.88 | high | high |  |
| 11 | BOTS - Suspicious PowerShell Execution | Undetermined | Undetermined | 0.44 | medium | medium | low confidence 0.44 |
| 12 | BOTS - Suspicious PowerShell Execution | TP | TP | 0.99 | high | high |  |
| 13 | BOTS - Watchlist Service Account AWS Activity | TP | TP | 0.99 | critical | critical |  |
| 14 | BOTS - Watchlist Service Account AWS Activity | Benign | Benign | 0.98 | low | low |  |
| 15 | BOTS - Risk Threshold Exceeded | TP | TP | 1.0 | high | high | roll-up capped at high |
| 16 | BOTS - Risk Threshold Exceeded | TP | TP | 1.0 | low | low |  |
| 17 | BOTS - Risk Threshold Exceeded | TP | TP | 1.0 | low | low |  |
| 18 | 24 hour risk threshold exceeded for user=web_admin | TP | TP | 0.98 | high | high | roll-up capped at high |
| 19 | Excessive Failed Logins | TP | TP | 1.0 | low | low |  |
| 20 | Excessive Failed Logins | TP | TP | 1.0 | low | low |  |
| 21 | Network Change Detected On ec2.amazonaws.com | Undetermined | Undetermined | 0.49 | medium | critical | low confidence 0.49 |
| 22 | Network Change Detected On ec2.amazonaws.com | TP | Undetermined ✗ | 0.26 | medium | critical | low confidence 0.26 |
| 23 | Network Change Detected On ec2.amazonaws.com | Undetermined | TP ✗ | 0.71 | medium | critical |  |
| 24 | Network Change Detected On ec2.amazonaws.com | Undetermined | Undetermined | 0.33 | medium | critical | low confidence 0.33 |
| 25 | 24 hour risk threshold exceeded for system=ec2.amazonaws.com | TP | Undetermined ✗ | 0.24 | medium | high | low confidence 0.24 / order check disagreed (benign) / roll-up capped at high |
| 26 | 24 hour risk threshold exceeded for system=5.101.40.81 | TP | TP | 1.0 | low | low |  |
| 27 | 24 hour risk threshold exceeded for system=167.114.13.150 | TP | TP | 1.0 | low | low |  |
| 28 | Finding Group Template - Entity Exceeded Risk Threshold | TP | TP | 1.0 | low | low |  |
| 29 | Finding Group Template - Entity Exceeded Risk Threshold | TP | TP | 0.99 | high | high | roll-up capped at high |
| 30 | Finding Group Template - Entity Exceeded Risk Threshold | TP | TP | 0.65 | medium | high | roll-up capped at high |
| 31 | Finding Group Template - Entity Exceeded Risk Threshold | TP | TP | 1.0 | low | low |  |
| 32 | Default Account Activity Detected | FP | FP | 0.86 | medium | high |  |
| 33 | BOTS - Risk Threshold Exceeded | TP | Undetermined ✗ | 0.57 | medium | high | low confidence 0.57 / roll-up capped at high |
