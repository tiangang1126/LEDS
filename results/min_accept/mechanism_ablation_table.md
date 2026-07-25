# Core Mechanism Ablation Table

| Setting | Event Trigger | Novelty Filter | Decision Record Map | API Calls | Penetration / Replay | Run Divergence | Replay Hamming | Interpretation |
| :--- | :---: | :---: | :---: | ---: | :--- | :--- | :---: | :--- |
| Full LEDS replay | Yes | Yes | Yes | 701 | 28.3% -> 28.3% | Not applicable | 0.0% | Fixed decision records yield exact node-level replay. |
| LEDS independent runs | Yes | Yes | No shared map | about 700 per run | 25.67% mean, range 4.67 pp | Hamming mean 14.0%, max 21.0% | Not applicable | Fresh cloud calls expose run-to-run nondeterminism. |
| Full Polling LLM | No | No/weak | Yes in baseline cache | 2400 | 7.3% | Not systematically estimated | Not applicable | Repeatedly rejudging idle nodes changes diffusion semantics. |
| High-temperature Monte Carlo (T=0.7) | Yes | Yes | Independent samples | 3993 | 17.2% +/- 4.6%, samples [8.0, 21.0, 18.0, 19.3, 19.7] | High sampling variance | Not applicable | Reference for high-temperature sampling, not a strict temperature ablation. |

Note: The high-temperature Monte Carlo row changes both temperature and sampling protocol; it must be described as a high-temperature sampling reference, not as the strict temperature ablation.
