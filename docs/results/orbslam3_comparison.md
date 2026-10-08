# ORB-SLAM3 stereo-inertial, EuRoC MAV -- ATE RMSE (m)

Paper: Campos et al., IEEE T-RO 2021 (arXiv 2007.11898), Table II, ORB-SLAM3 stereo-inertial row
(median of 10 runs, all frames). Ours: keyframe trajectories (kf_orb_*), median of 5 runs,
evo_ape euroc --align (SE(3)), evo 1.31.1. Deviation = (ours - paper) / paper.

| Seq | r1 | r2 | r3 | r4 | r5 | Median | Paper | Deviation | Band |
|---|---|---|---|---|---|---|---|---|---|
| MH01 | 0.0433 | 0.0332 | 0.0441 | 0.0439 | 0.0456 | 0.0439 | 0.036 | +21.9 % | amber |
| MH02 | 0.0356 | 0.0271 | 0.0239 | 0.0387 | 0.0295 | 0.0295 | 0.033 | -10.6 % | green |
| MH03 | 0.0351 | 0.0291 | 0.0315 | 0.0307 | 0.0305 | 0.0307 | 0.035 | -12.3 % | green |
| MH04 | 0.0456 | 0.0430 | 0.0484 | 0.0448 | 0.0469 | 0.0456 | 0.051 | -10.5 % | green |
| MH05 | 0.0574 | 0.0608 | 0.0556 | 0.0679 | 0.0633 | 0.0608 | 0.082 | -25.8 % | amber |
| V101 | 0.0377 | 0.0366 | 0.0387 | 0.0374 | 0.0381 | 0.0377 | 0.038 | -0.9 % | green |
| V102 | 0.0138 | 0.0141 | 0.0162 | 0.0140 | 0.0164 | 0.0141 | 0.014 | +0.7 % | green |
| V103 | 0.0261 | 0.0268 | 0.0263 | 0.0270 | 0.0281 | 0.0268 | 0.024 | +11.9 % | green |
| V201 | 0.0369 | 0.0376 | 0.0370 | 0.0392 | 0.0353 | 0.0370 | 0.032 | +15.6 % | amber |
| V202 | 0.0136 | 0.0114 | 0.0095 | 0.0115 | 0.0126 | 0.0115 | 0.014 | -17.7 % | amber |
| V203 | 0.0186 | 0.6946 | 0.0218 | 0.0204 | 0.0229 | 0.0218 | 0.024 | -9.1 % | green |
| Avg | | | | | | 0.0327 | 0.035 | -6.1 % | green |

V203 run 2 lost tracking (0.695 m); the median absorbs it. Protocol differences: keyframes vs all
frames, 5 vs 10 runs. Raw trajectories: output/orbslam3/trajectories; evaluation: output/orbslam3/evaluation.
