# Final results (committed copies)

| Algorithm | Table | Per-run values | Protocol notes |
|---|---|---|---|
| ORB-SLAM3 (stereo-inertial, EuRoC) | `orbslam3_comparison.md` | `orbslam3_summary.csv` | keyframe trajectories, median of 5, evo SE(3) |
| FAST-LIO2 (16 paper sequences) | `fastlio2_comparison.md` | `fastlio2_summary.csv` | median of 5; paper + independent re-run (arXiv 2307.07792) columns; see `docs/fastlio2_reproduction_log.md` |
| FAST-LIVO2, standard protocol (whole bag) | `fastlivo2_standard_comparison.md` | `fastlivo2_standard_summary.csv` | NTU-VIRAL vs repo README + paper; private dataset vs < 0.01 m |
| FAST-LIVO2, matched start (NTU-VIRAL) | `fastlivo2_matched_comparison.md` | `fastlivo2_matched_summary.csv` | replay from the authors' own first pose; see `docs/fastlivo2_reproduction_log.md` |

Raw outputs (trajectories, bags, logs, diagnostics): `output/` -- layout in `OUTPUT_LAYOUT.md`.
All build/test/evaluation commands: `docs/FAST-LIO2_FAST-LIVO2_Test_Commands.pdf`.
