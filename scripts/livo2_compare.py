#!/usr/bin/env python3
"""Paper-vs-ours table for FAST-LIVO2.    livo2_compare.py <summary.csv>

NTU-VIRAL (ATE RMSE, m). Three published references, all reported:
  repo    -- Log/result/ntu_viral/README.md at commit 0d2c034: the authors' own runs of
             the RELEASED code with the shipped NTU_VIRAL.yaml (normal_en: true), scored
             with `evo_ape tum gt prism -a`. Same code, config and command as ours, so the
             deviation (and its band) is computed against this column.
  paper   -- Zheng et al., FAST-LIVO2, IEEE T-RO 2024 (arXiv 2408.14035), Table II "Ours".
  normal  -- same table, "Ours (w normal)": the paper variant matching normal_en: true.
Private dataset: the paper's claim (Sec. IX-C) is end-to-end error < 0.01 m on all 20.
Hilti'22/'23: ground truth is not public; scores only via the Hilti website.
Deviation = (ours - ref) / ref; green < 15 %, amber 15-30 %, red > 30 %."""
import csv, statistics, sys

NTU = {  # seq: (repo README, paper Ours, paper Ours w normal)
    "eee_01": (0.0271, 0.068, 0.066), "eee_02": (0.0211, 0.051, 0.055),
    "eee_03": (0.0261, 0.068, 0.070), "nya_01": (0.0356, 0.073, 0.078),
    "nya_02": (0.0339, 0.075, 0.081), "nya_03": (0.0352, 0.059, 0.060),
    "sbs_01": (0.0234, 0.062, 0.063), "sbs_02": (0.0283, 0.061, 0.048),
    "sbs_03": (0.0311, 0.060, 0.047),
}
# Private dataset (Google Drive copy linked from Global-LVBA; the README's SharePoint link is
# dead). Paper claims "< 0.01 m" end-to-end only for these six (Sec. IX-C / IX-D):
# HKU Cultural Center, CBD Building 03, Mining Tunnel (IX-C); SYSU 01, HKU Landmark,
# CBD Building 01 (IX-D). Mining Tunnel is not in the Drive folder.
PRIVATE = {  # seq: (paper name, paper duration, file duration, claim)
    "hku_landmark":           ("HKU Landmark",        "1:31", "1:31", True),
    "cbd_building_01":        ("CBD Building 01",     "1:58", "1:58", True),
    "hku_cultural_center_02": ("HKU Cultural Center", "4:01", "4:01", True),
    "cbd_building_03":        ("CBD Building 03",     "5:01", "4:26", True),
    "sysu_01":                ("SYSU 01",             "4:40", "2:14", True),
    "hku_cultural_center_01": ("(not in paper)",      "-",    "3:17", False),
}

def band(d): return "green" if abs(d) < 0.15 else "amber" if abs(d) <= 0.30 else "red"
def pct(a, b): return "%+.1f %%" % (100 * (a - b) / b)

runs = {}
for r in csv.DictReader(open(sys.argv[1])):
    if r["value_m"] in ("", "NA"): continue
    runs.setdefault((r["sequence"], r["metric"]), []).append(float(r["value_m"]))

print("| Sequence | Metric | Ours (median) | Runs | Spread | Repo README | Dev. vs repo | Band | Paper \"Ours\" | Dev. | Paper \"w normal\" | Dev. |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for (seq, metric), v in sorted(runs.items(), key=lambda kv: (kv[0][0] not in NTU, kv[0][0])):
    med = statistics.median(v); spread = max(v) - min(v)
    if seq in NTU and metric == "ape_rmse":
        repo, paper, normal = NTU[seq]
        print("| %s | ATE RMSE | %.4f | %d | %.4f | %.4f | %s | %s | %.3f | %s | %.3f | %s |" % (
            seq, med, len(v), spread, repo, pct(med, repo), band((med - repo) / repo),
            paper, pct(med, paper), normal, pct(med, normal)))
    elif seq.startswith("hilti"):
        print("| %s | %s | %.4f | %d | %.4f | - | - | no public GT (Hilti online scoring only) | - | - | - | - |" % (seq, metric, med, len(v), spread))
    elif metric == "end_to_end":
        name, pdur, fdur, claim = PRIVATE.get(seq, (seq, "?", "?", True))
        if not claim:
            verdict = "no paper claim (%s, %s)" % (name, fdur)
        else:
            verdict = ("PASS" if med < 0.01 else "FAIL") + " vs paper < 0.01 m"
            if pdur != fdur:
                verdict += "; NOT the paper's recording (file %s, paper %s)" % (fdur, pdur)
        print("| %s | end-to-end | %.4f | %d | %.4f | - | - | %s | < 0.01 | - | - | - |" % (
            seq, med, len(v), spread, verdict))
    else:
        print("| %s | %s | %.4f | %d | %.4f | - | - | - | - | - | - | - |" % (seq, metric, med, len(v), spread))
