# Core Mechanism Ablation Table

| Setting | Event Trigger | Novelty Filter | Decision Record Map | API Calls | Penetration / Replay | Run Divergence | Replay Hamming | Interpretation |
| :--- | :---: | :---: | :---: | ---: | :--- | :--- | :---: | :--- |
| Full LEDS replay | Yes | Yes | Yes | 454 seed calls; 0/0/0 replay calls | 56.667% -> 56.667% / 56.667% / 56.667% | Not applicable | 0.0% / 0.0% / 0.0% | Fixed decision records yield exact replay with final-state and trace hashes both matching. |
| LEDS independent runs | Yes | Yes | No shared map | 439-450 cloud calls per run | 55.933% mean, 95% CI [55.587%, 56.280%], range 0.667 pp | Hamming mean 1.400%, 95% CI [1.154%, 1.646%], max 1.667%; all five final-state hashes differ | Not applicable | Fresh zero-temperature cloud calls remain not trajectory-deterministic even when macro penetration is stable. |
| Full Polling LLM | No | No/weak | Yes in baseline cache | 2400 | 7.3% | Not systematically estimated | Not applicable | Repeatedly rejudging idle nodes changes diffusion semantics. |
| High-temperature Monte Carlo (T=0.7) | Yes | Yes | Independent samples | 3993 | 17.2% +/- 4.6%, samples [8.0, 21.0, 18.0, 19.3, 19.7] | High sampling variance | Not applicable | Reference for high-temperature sampling, not a strict temperature ablation. |

Note: The high-temperature Monte Carlo row changes both temperature and sampling protocol; it must be described as a high-temperature sampling reference, not as the strict temperature ablation.
