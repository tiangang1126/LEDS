# LEDS Temperature Sensitivity Summary

## Overall

Inference unit: Prompt. Each Prompt's three calls are averaged before analysis. Intervals are persona-stratified Prompt-cluster bootstrap percentile intervals.

| Temperature | Prompts | Outputs | Joint Rule Acc. | 95% Prompt-bootstrap CI | Stance Acc. | Action Acc. | JSON Valid | Prompt Disagreement |
| :---: | ---: | ---: | ---: | :---: | ---: | ---: | ---: | ---: |
| 0.0 | 240 | 720 | 67.22% | [61.53, 72.78] | 73.89% | 81.81% | 100.00% | 6.67% |
| 0.2 | 240 | 720 | 67.36% | [61.67, 72.92] | 74.03% | 81.81% | 100.00% | 6.25% |
| 0.5 | 240 | 720 | 66.81% | [61.11, 72.36] | 73.19% | 81.25% | 100.00% | 7.08% |
| 0.7 | 240 | 720 | 67.08% | [61.39, 72.64] | 73.61% | 81.53% | 100.00% | 7.50% |

## By Persona

| Temperature | Persona | Prompts | Outputs | Joint Rule Acc. | 95% Prompt-bootstrap CI | Stance Acc. | Action Acc. | JSON Valid |
| :---: | :---: | ---: | ---: | ---: | :---: | ---: | ---: | ---: |
| 0.0 | fact_checker | 80 | 240 | 80.00% | [71.25, 88.33] | 100.00% | 80.00% | 100.00% |
| 0.0 | neutral | 80 | 240 | 61.67% | [51.67, 71.67] | 61.67% | 80.42% | 100.00% |
| 0.0 | susceptible | 80 | 240 | 60.00% | [49.17, 70.42] | 60.00% | 85.00% | 100.00% |
| 0.2 | fact_checker | 80 | 240 | 80.00% | [71.25, 87.92] | 100.00% | 80.00% | 100.00% |
| 0.2 | neutral | 80 | 240 | 62.08% | [51.67, 72.08] | 62.08% | 79.58% | 100.00% |
| 0.2 | susceptible | 80 | 240 | 60.00% | [49.58, 70.42] | 60.00% | 85.83% | 100.00% |
| 0.5 | fact_checker | 80 | 240 | 80.83% | [72.08, 88.75] | 100.00% | 80.83% | 100.00% |
| 0.5 | neutral | 80 | 240 | 60.00% | [49.58, 70.00] | 60.00% | 78.75% | 100.00% |
| 0.5 | susceptible | 80 | 240 | 59.58% | [48.75, 70.00] | 59.58% | 84.17% | 100.00% |
| 0.7 | fact_checker | 80 | 240 | 80.42% | [71.67, 88.34] | 100.00% | 80.42% | 100.00% |
| 0.7 | neutral | 80 | 240 | 61.25% | [50.83, 71.25] | 61.25% | 80.00% | 100.00% |
| 0.7 | susceptible | 80 | 240 | 59.58% | [48.75, 70.00] | 59.58% | 84.17% | 100.00% |
