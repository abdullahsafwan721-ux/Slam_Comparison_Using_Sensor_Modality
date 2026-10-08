# output/ -- every measured output, by algorithm

Raw outputs (bags, trajectories, logs) live here and are git-ignored (size). The final tables
are also committed in `docs/results/`. Mounted as `/output` in every container.
Layout organised on 2026-10-08; nothing was deleted.

| Folder | What | Produced by |
|---|---|---|
| `orbslam3/trajectories/` | ORB-SLAM3 EuRoC, 11 seq x 5 runs: `kf_orb_<SEQ>_r<N>.txt` (keyframes, ns stamps), `f_orb_*` (all frames) | `scripts/run_orbslam3_euroc.sh` (orbslam3 container) |
| `orbslam3/evaluation/` | `*_eval.txt` (stamps in s), `*_ape.zip` (evo), `summary.csv` | `scripts/eval_orbslam3.sh` (eval container) |
| `fastlio2/` | FAST-LIO2, 16 paper sequences x 5 runs: `<seq>_r<N>.bag` (/Odometry), `.tum`, `.algo.log`, `.params.yaml`; ground truth `gt_<seq>.tum`, GNSS refs `gnssref_<seq>.tum`, UTBM `<seq>_fix.bag`; `benchmark.log` | `scripts/fl2_benchmark.sh` -> `run_fastlio2.sh` / `run_fastlio2_utbm.sh` |
| `fastlivo2/` | FAST-LIVO2 standard protocol (whole bag): NTU-VIRAL 9 seq + private 6 seq x 5 runs: `<seq>_r<N>.txt` (TUM, IMU frame), `_prism.tum`, `.bag`, `.algo.log`, `.params.yaml`; `gt_<seq>.tum`; `benchmark.log` | `scripts/livo2_benchmark.sh` -> `run_fastlivo2.sh` |
| `fastlivo2_matched/` | FAST-LIVO2 NTU-VIRAL "matched start" protocol (replay from the authors' own first pose) | `scripts/livo2_ntu_matched.sh` |
| `results/fastlio2_final/` | final FAST-LIO2 evaluation: `summary.csv`, `comparison.md`, per-run `*_ape.zip/.txt` | `scripts/eval_fastlio2.sh` |
| `results/fastlivo2_standard_final/` | final FAST-LIVO2 evaluation, standard protocol | `scripts/eval_fastlivo2.sh` |
| `results/fastlivo2_matched_final/` | final FAST-LIVO2 evaluation, matched-start protocol | `IN=/output/fastlivo2_matched eval_fastlivo2.sh` |
| `results/history/` | every earlier, timestamped evaluation run (superseded, kept for traceability) | same scripts |
| `diagnostics/fastlio2/avia_functional_test/` | first FAST-LIO2 run (Sept 2026): Avia demo bag, not a paper sequence | manual |
| `diagnostics/fastlio2/smoke_lili6_slice/` | pipeline smoke test on an 89 s lili slice | `run_fastlio2.sh` |
| `diagnostics/fastlio2/smoke_parallel_vs_serial/` | proof that parallel runs = serial runs (identical results) | `fl2_parallel.sh` |
| `diagnostics/fastlio2/lili7_config_variants/` | lili 7 with Xsens IMU / no extrinsic estimation / point_filter_num 3 | `run_fastlio2.sh` |
| `diagnostics/fastlivo2/native_avx512_build/` | FAST-LIVO2 built with upstream `-march=native` (AVX-512): sbs_02 diverges; runs truncated by the old 5 s drain | old image |
| `diagnostics/fastlivo2/skylake_build_test/` | first Skylake-ISA build test (sbs_02 / eee_02) | diagnostic image |
| `diagnostics/fastlivo2/INVALID_generic_build_abi_mismatch/` | invalid: only FAST-LIVO2 rebuilt without -march (Eigen ABI mismatch with vikit) -- do not use | diagnostic image |
| `diagnostics/fastlivo2/eee02_start_offset_0.3s/` | eee_02 replayed from 0.3 s (start-offset test) | `run_fastlivo2.sh ... -s 0.3` |
| `diagnostics/fastlivo2/private_paper_default_config/` | private dataset with the paper's Sec. IX-A defaults | `avia_private_g*_paperdefault.yaml` |

Reports: `docs/fastlio2_reproduction_log.md`, `docs/fastlivo2_reproduction_log.md`,
`docs/FAST-LIO2_FAST-LIVO2_Test_Commands.pdf` (all commands to build, test and evaluate).
