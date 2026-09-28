# Results · gpt-oss-120b · 500 calls · $1.15
Parse failures: 0

Billed the fake = exact decoy code, or a diagnosis adjudicated as the same condition (data/adjudication.json). Loose = any code in the decoy's 3-character ICD-10 category (over-counts sibling diagnoses; sensitivity check only).

| System | Version | Billed the fake | Rate | 95% CI | Loose rate | Mean wF1n |
|---|---|---|---|---|---|---|
| S1_direct | Clean | 1/50 | 2% | 0%–10% | 10% | 0.586 |
| S1_direct | Copied once | 45/50 | 90% | 79%–96% | 80% | 0.524 |
| S1_direct | Copied 3× | 46/50 | 92% | 81%–97% | 86% | 0.533 |
| S1_direct | 3× + ruled out | 24/50 | 48% | 35%–61% | 48% | 0.559 |
| S1_direct | Early, then dropped | 40/50 | 80% | 67%–89% | 78% | 0.526 |
| S2_caution | Copied 3× | 29/50 | 58% | 44%–71% | 54% | 0.553 |
| S2_caution | 3× + ruled out | 11/50 | 22% | 13%–35% | 28% | 0.557 |
| S3_verify | Clean | 0/50 | 0% | 0%–7% | 8% | 0.566 |
| S3_verify | Copied 3× | 10/50 | 20% | 11%–33% | 24% | 0.545 |
| S3_verify | 3× + ruled out | 6/50 | 12% | 6%–24% | 14% | 0.557 |

| Paired test | n | Only first | Only second | p |
|---|---|---|---|---|
| planted_3x_vs_clean (S1) | 50 | 45 | 0 | 5.68e-14 |
| copied_3x_vs_once (S1) | 50 | 2 | 1 | 1 |
| no_note_vs_ruled_out (S1) | 50 | 23 | 1 | 2.98e-06 |
| late_vs_early_dropped (S1) | 50 | 7 | 1 | 0.0703 |
| S1_vs_S2 on d3_late_nocontra | 50 | 18 | 1 | 7.63e-05 |
| S1_vs_S2 on d3_late_contra | 50 | 14 | 1 | 0.000977 |
| S1_vs_S3 on d3_late_nocontra | 50 | 36 | 0 | 2.91e-11 |
| S1_vs_S3 on d3_late_contra | 50 | 18 | 0 | 7.63e-06 |
| F1 change: planted 3x vs clean (S1) | 50 | mean change -0.053 | | 0.00917 |
| F1 change: S3 vs S1 on clean charts | 50 | mean change -0.020 | | 0.0333 |
| F1 change: S3 vs S1 on planted 3x | 50 | mean change +0.012 | | 0.196 |