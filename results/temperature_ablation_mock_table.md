# Temperature Ablation Tables

> Mock mode is for pipeline validation only. Use API mode for paper data.

## Prompt-level judgment quality

| Temperature | Decisions | Rule exact (%) | Stance (%) | Action (%) | Raw invalid (%) | Fallback (%) |
| :---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.0 | 54 | 100.00 | 100.00 | 100.00 | 0.000 | 0.000 |
| 0.2 | 54 | 100.00 | 100.00 | 100.00 | 0.000 | 0.000 |
| 0.5 | 54 | 100.00 | 100.00 | 100.00 | 0.000 | 0.000 |
| 0.7 | 54 | 100.00 | 100.00 | 100.00 | 0.000 | 0.000 |

## Simulation-level propagation stability

| Temperature | Runs | Penetration mean +/- 95%CI (%) | Std | Range | Mean pairwise Hamming (%) | Hamming vs Temp0 ref (%) | Invalid (%) | Fallbacks | API calls |
| :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.0 | 2 | 47.67 +/- 0.00 | 0.00 | 47.67-47.67 | 0.00 | 0.00 | 0.000 | 0 | 1122 |
| 0.2 | 2 | 47.67 +/- 0.00 | 0.00 | 47.67-47.67 | 0.00 | 0.00 | 0.000 | 0 | 1122 |
| 0.5 | 2 | 47.67 +/- 0.00 | 0.00 | 47.67-47.67 | 0.00 | 0.00 | 0.000 | 0 | 1122 |
| 0.7 | 2 | 47.67 +/- 0.00 | 0.00 | 47.67-47.67 | 0.00 | 0.00 | 0.000 | 0 | 1122 |
