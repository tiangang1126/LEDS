# DeepSeek-v4-flash Temperature Ablation Statistical Analysis

## Completeness Check

- Success rows: 2880 / 2880
- API errors included in analysis file: 0
- JSON invalid rows: 0
- Unique prompt-temperature-repeat cells: 2880

## Joint Rule Accuracy Difference vs T=0.0

| Comparison | Accuracy Difference | 95% CI | Non-inferiority Margin | Pass |
|---|---:|---:|---:|:---:|
| T=0.2 minus T=0.0 | 0.14% | [-4.71, 4.99] | -3.00% | False |
| T=0.5 minus T=0.0 | -0.42% | [-5.27, 4.44] | -3.00% | False |
| T=0.7 minus T=0.0 | -0.14% | [-4.99, 4.71] | -3.00% | False |

Note: Pass requires the lower bound of T minus T=0.0 to be greater than -3 percentage points.

## Prompt-level Disagreement

| Temperature | Prompt Count | Disagreement Count | Rate | 95% Wilson CI |
|---:|---:|---:|---:|---:|
| 0.0 | 240 | 16 | 6.67% | [4.14, 10.55] |
| 0.2 | 240 | 15 | 6.25% | [3.82, 10.05] |
| 0.5 | 240 | 17 | 7.08% | [4.47, 11.05] |
| 0.7 | 240 | 18 | 7.50% | [4.80, 11.54] |

## Top Failure Modes

### T=0.0
| Gold | Prediction | Count | Share of failures |
|---|---|---:|---:|
| Neutral/Ignore | Reject/Ignore | 97 | 41.10% |
| Accept/Share | Reject/Ignore | 55 | 23.31% |
| Reject/Ignore | Reject/Debunk | 45 | 19.07% |
| Reject/Ignore | Accept/Share | 18 | 7.63% |
| Neutral/Ignore | Accept/Share | 10 | 4.24% |
| Reject/Ignore | Neutral/Ignore | 8 | 3.39% |

### T=0.2
| Gold | Prediction | Count | Share of failures |
|---|---|---:|---:|
| Neutral/Ignore | Reject/Ignore | 99 | 42.13% |
| Accept/Share | Reject/Ignore | 54 | 22.98% |
| Reject/Ignore | Reject/Debunk | 44 | 18.72% |
| Reject/Ignore | Accept/Share | 21 | 8.94% |
| Neutral/Ignore | Accept/Share | 8 | 3.40% |
| Reject/Ignore | Neutral/Ignore | 5 | 2.13% |

### T=0.5
| Gold | Prediction | Count | Share of failures |
|---|---|---:|---:|
| Neutral/Ignore | Reject/Ignore | 95 | 39.75% |
| Accept/Share | Reject/Ignore | 54 | 22.59% |
| Reject/Ignore | Reject/Debunk | 44 | 18.41% |
| Reject/Ignore | Accept/Share | 22 | 9.21% |
| Neutral/Ignore | Accept/Share | 13 | 5.44% |
| Reject/Ignore | Neutral/Ignore | 9 | 3.77% |

### T=0.7
| Gold | Prediction | Count | Share of failures |
|---|---|---:|---:|
| Neutral/Ignore | Reject/Ignore | 95 | 40.08% |
| Accept/Share | Reject/Ignore | 54 | 22.78% |
| Reject/Ignore | Reject/Debunk | 44 | 18.57% |
| Reject/Ignore | Accept/Share | 21 | 8.86% |
| Neutral/Ignore | Accept/Share | 11 | 4.64% |
| Reject/Ignore | Neutral/Ignore | 8 | 3.38% |

