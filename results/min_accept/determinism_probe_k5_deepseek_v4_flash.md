# Determinism Probe K=5

- Mode: api(deepseek-v4-flash)
- Model: deepseek-v4-flash
- Endpoint: https://api.deepseek.com/v1/chat/completions
- Config: data\exp1_scalefree.json
- Config SHA256: `097657e00b6c653e6bbd8d217681396a548769387719c2517790739bab1efaf4`
- Prompt config SHA256: `cb4a6e6c71a0be8d540fd33acfa2fe3e34575299c1adb2dc92a84260df208be3`
- Schema source SHA256: `c033c2eeb3affb21e0c7cee0e0f2563f2e6d63f9f15b94ed01180c9ebb3e1595`
- Script SHA256: `c94c2213eae44bc0fd02f4bf09ea1cd5e1c713d16fd40ae5185391d3544a1e5b`
- Git commit: `unavailable`; dirty: true
- Started UTC: 2026-07-26T02:17:23+00:00
- Finished UTC: 2026-07-26T07:52:26+00:00

## Independent Runs

- K: 5
- Temperature / Top_P: 0.0 / 1.0
- Penetration samples: [56.0, 56.333, 55.667, 56.0, 55.667]
- Penetration mean: 55.933%
- Penetration sample std: 0.279%
- Penetration Student-t 95% CI: [55.587%, 56.280%]
- Penetration range: 0.667 pp
- Stable-step samples: [8.0, 9.0, 9.0, 8.0, 8.0]
- Stable-step Student-t 95% CI: [7.720, 9.080]
- Pairwise Hamming samples: [1.0, 1.667, 1.333, 1.667, 1.333, 1.667, 1.333, 1.667, 0.667, 1.667]
- Pairwise Hamming mean / std / max: 1.400% / 0.344% / 1.667%

## Decision-Record Replay

- Seed run: replay_seed_run_01
- Replay count: 3
- Replay exact match: 3/3
- Replay cloud calls during replay: [0, 0, 0]
- Replay all exact: True
- Replay all final-state hashes exact: True
