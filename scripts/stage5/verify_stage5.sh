#!/usr/bin/env bash
# Stage 5 verification. HOST, project root, nothing else running:
#   bash scripts/stage5/verify_stage5.sh                   # steps 1-6, ~5 min
#   FLY=1 GUI=true bash scripts/stage5/verify_stage5.sh    # + step 7: a NEW closed-loop flight with the
#                                                          #   Gazebo window open (watch the hover), ~4 min
# Reads output/stage5; writes only output/verify_stage5/ (replaced on every run).
#  1 code       committed, parses; compose has the two host-network services
#  2 frame      the offline relay check again (FAST-LIO2 run of Stage 4 -> slam_to_px4.py -> truth)
#  3 flights    every recorded flight: all EV parameters read back OK, PX4 booted without a
#               position source, mission complete (landed and disarmed)
#  4 re-score   every flight scored again from its bag; the numbers equal the stored ones
#  5 tables     stage5_tables.md and the figures regenerated from the re-scored flights
#  6 gate       guide 5.6 against the numbers (the hover's look stays a human judgement), and
#               for every flight with PX4's log: the touchdown height error explained (vision
#               never rejected; the IMU integrates only part of the touchdown impulse)
#  7 fly        (FLY=1) a new closed-loop square, scored and gated the same way; with GUI=true
#               the window(s) are open and pictures are kept (capture_windows.sh: Gazebo, or
#               RViz when RVIZ=true, because RViz's window covers Gazebo's)
#  8 matrix     (MATRIX=1) the closed loop over the Stage 4 matrix (run_closed_loop_matrix.sh):
#               every cell flown and scored, every flight re-scored identically, tables regenerated
set -o pipefail
[ -f compose.yaml ] || { echo "run from the project root"; exit 1; }
V=output/verify_stage5; S=output/stage5
C="docker compose run --rm -T"
FAILED=(); T0=$(date +%s)
step() { echo; echo "==[$1] $2   ($(date +%T))"; }
res() { [ "$2" -eq 0 ] || FAILED+=("$1"); }
exec 2> >(grep --line-buffered -v -E "^ Container .* (Creating|Created)" >&2)
echo "Stage 5 verification  $(date -Is)  git $(git rev-parse --short HEAD)"
rm -rf "$V"; mkdir -p "$V/flights" "$V/eval"

step 1 "code"
rc=0
git diff --quiet HEAD -- scripts/stage5 config/px4 compose.yaml docs/stage5_log.md \
  && echo "  PASS  scripts/stage5, config/px4, compose.yaml, docs/stage5_log.md: no uncommitted changes" \
  || echo "  WARN  uncommitted changes in scripts/stage5, config/px4, compose.yaml or docs/stage5_log.md"
bash -n scripts/stage5/*.sh && python3 -c "import ast,sys; [ast.parse(open(f).read(), f) for f in sys.argv[1:]]" scripts/stage5/*.py \
  && echo "  PASS  every Stage 5 script parses" || { echo "  FAIL  a script does not parse"; rc=1; }
svc=$(docker compose config 2>/dev/null | python3 -c "import sys,yaml; s=yaml.safe_load(sys.stdin)['services']; print(' '.join(k for k in ('sim-live','fastlio2-live') if s.get(k,{}).get('network_mode')=='host'))")
[ "$svc" = "sim-live fastlio2-live" ] && echo "  PASS  compose: sim-live and fastlio2-live on host networking" || { echo "  FAIL  compose services: '$svc'"; rc=1; }
res 1 $rc

step 2 "offline frame check of the relay"
$C sim bash -c "source /opt/ros/noetic/setup.bash; roscore >/dev/null 2>&1 & sleep 4
  rosparam set use_sim_time true
  python3 /scripts/stage5/slam_to_px4.py >/dev/null 2>&1 &
  rosbag record -O /$V/relay.bag /mavros/vision_pose/pose __name:=rec >/dev/null 2>&1 & sleep 3
  rosbag play -q --clock /output/stage4/environments/fastlio2/fastlio2__room__r1.bag >/dev/null 2>&1
  sleep 2; rosnode kill /rec >/dev/null; sleep 2" > /dev/null
$C eval bash -c "bash /scripts/common/ros_python.sh /scripts/common/bag_to_tum.py /$V/relay.bag /mavros/vision_pose/pose /$V/vision.tum >/dev/null &&
  python3 /scripts/stage5/closed_loop_metrics.py frame /output/stage4/environments/gt/room.tum /$V/vision.tum" | sed 's/^   //;s/^/  /'
res 2 $?

step 3 "recorded flights"
rc=0; NAMES=()
for b in $S/flights/*.bag; do
  n=$(basename "$b" .bag); case "$n" in *FAILED*) continue;; esac; NAMES+=("$n")
  p=$(grep -c "read back .* OK$" "$S/flights/$n.terminal1.log" 2>/dev/null); np=$(grep -cvE "^\s*(#|$)" config/px4/ev_only.params)
  boot=$(grep -c "NO position source" "$S/flights/$n.terminal1.log" 2>/dev/null)
  done_=$(grep -c "landed and disarmed" "$S/flights/$n.mission.log" 2>/dev/null)
  if [ "$p" = "$np" ] && [ "$boot" -ge 1 ] && [ "$done_" -ge 1 ]; then
    echo "  PASS  $n: $p/$np EV parameters read back, rebooted without a position source, $(grep -oE "hop [0-9.]+ m|profile done|landed and disarmed" "$S/flights/$n.mission.log" | paste -sd, -)"
  else echo "  FAIL  $n: parameters $p/$np, reboot $boot, mission complete $done_"; rc=1; fi
done
res 3 $rc

rescore() {   # rescore <src root> <dst root>: every flight of <src>/flights scored again into <dst>
  local SRC=$1 DST=$2 n x rc=0
  mkdir -p "$DST/flights" "$DST/eval"
  for b in "$SRC"/flights/*.bag; do
    n=$(basename "$b" .bag); case "$n" in *FAILED*) continue;; esac
    [ -s "$SRC/flights/$n.closed_loop.json" ] || continue
    for x in bag ulg algo config.txt fault.txt livo_result mission.log; do   # what scoring + tables read (relative links:
      [ -e "$SRC/flights/$n.$x" ] && ln -s "$(realpath --relative-to="$DST/flights" "$SRC/flights/$n.$x")" "$DST/flights/$n.$x"
    done                                                         #  the containers see the project at /output)
    FLIGHTS=$DST/flights EVAL=$DST/eval bash scripts/stage5/eval_closed_loop.sh "$n" > "$DST/flights/$n.score.log" 2>&1 || true
  done
  python3 - "$SRC" "$DST" <<'EOF' || rc=1
import glob, json, math, os, sys
S, V = sys.argv[1:3]; bad = 0
def same(a, b):
    if isinstance(a, dict):
        return all(same(a.get(k), b.get(k)) for k in set(a) | set(b))
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and isinstance(b, float):
        return (math.isnan(a) and math.isnan(b)) or abs(a - b) <= 1e-9 * max(1, abs(a))
    return a == b
for f in sorted(glob.glob(os.path.join(S, "flights", "*.closed_loop.json"))):
    n = os.path.basename(f)[:-len(".closed_loop.json")]
    new = os.path.join(V, "flights", n + ".closed_loop.json")
    old = json.load(open(f))
    ok = os.path.exists(new) and same(old, json.load(open(new)))
    for a in (old.get("algo", "fastlio2"), "px4"):
        x, y = [os.path.join(d, "eval", "%s__%s__r1_extra.json" % (a, n)) for d in (S, V)]
        jx, jy = (json.load(open(p)) if os.path.exists(p) else None for p in (x, y))
        ok = ok and jx is not None and jy is not None and same({k: v for k, v in jx.items() if k not in ("gt", "est")},
                                                            {k: v for k, v in jy.items() if k not in ("gt", "est")})
    t0, t1 = (os.path.join(d, "flights", n + ".touchdown.txt") for d in (S, V))
    extra = ""
    if os.path.exists(t0):
        same_td = os.path.exists(t1) and open(t0).read() == open(t1).read()
        ok = ok and same_td
        extra = ", touchdown analysis of PX4's log identical"
    print("  %s  %s: closed-loop metrics and both APE records identical after re-scoring%s" % ("PASS" if ok else "FAIL", n, extra))
    bad += not ok
sys.exit(bad)
EOF
  return $rc
}

step 4 "every flight re-scored from its bag"
rescore "$S" "$V"; res 4 $?

step 5 "tables and figures regenerated"
rc=0
python3 -W ignore scripts/stage5/stage5_figures.py "$V" > /dev/null || rc=1
diff -q "$S/stage5_tables.md" "$V/stage5_tables.md" > /dev/null && echo "  PASS  stage5_tables.md identical" || { echo "  FAIL  stage5_tables.md differs"; rc=1; }
for p in "$S"/figures/*.png; do
  q="$V/figures/$(basename "$p")"
  python3 -c "import sys, numpy as np, matplotlib.image as m; a, b = m.imread(sys.argv[1]), m.imread(sys.argv[2]); sys.exit(0 if a.shape == b.shape and np.array_equal(a, b) else 1)" "$p" "$q" 2>/dev/null \
    && echo "  PASS  figures/$(basename "$p") pixel-identical" || { echo "  FAIL  figures/$(basename "$p") differs"; rc=1; }
done
res 5 $rc

gate() {   # gate <dir>: guide 5.6 from the numbers
python3 - "$1" <<'EOF'
import glob, json, os, sys
D = sys.argv[1]; bad = 0
for f in sorted(glob.glob(os.path.join(D, "flights", "*.closed_loop.json"))):
    o = json.load(open(f)); n = o["name"]
    ev = lambda a: json.load(open(os.path.join(D, "eval", "%s__%s__r1_extra.json" % (a, n))))
    fl, px = ev(o.get("algo", "fastlio2"))["ape_air_rmse"], ev("px4")["ape_air_rmse"]
    pt, ek = o["px4_truth"]["rmse_m"], o["ekf"]["rmse_m"]
    ok = pt < 0.10 and ek < 0.05 and abs(o.get("ekf_lag_s") or 0) <= 0.05 and o["relay"]["climb_corr"] > 0.99
    msg = "PX4 vs truth %.1f cm in flight (%s APE %.2f cm, PX4 APE %.2f cm = %.1fx), PX4 follows SLAM to %.1f cm with %.2f s lag" % (
        pt * 100, {"fastlivo2": "FAST-LIVO2"}.get(o.get("algo"), "FAST-LIO2"), fl * 100, px * 100, px / fl, ek * 100,
        o.get("ekf_lag_s") or 0)
    for h in o.get("hover", []):
        sd = max(h["sd_xyz_cm"]); q = h.get("quarter_dev_cm", [])
        grows = len(q) == 4 and q[-1] > 1.25 * max(q[:-1]) + 1.0     # last quarter clearly worse
        ok = ok and sd < 5 and not grows
        msg += "; hover %.0f s: sd <= %.1f cm, max deviation per quarter %s cm (%s)" % (
            h["length_s"], sd, " / ".join("%.1f" % v for v in q), "GROWS" if grows else "no growth")
    print("  %s  %s: %s" % ("PASS" if ok else "FAIL", n, msg)); bad += not ok
for f in sorted(glob.glob(os.path.join(D, "flights", "*.touchdown.txt"))):
    t = open(f).read(); n = os.path.basename(f)[:-len(".touchdown.txt")]
    import re
    r = re.search(r"REJECTED in (\d+) of", t); m = re.search(r"IMU-integrated ([+-][\d.]+) m/s \((-?\d+) %", t)   # negative after a bounce
    ok = bool(r and m) and int(r.group(1)) == 0 and int(m.group(2)) < 75   # vision kept; IMU missed a large part
    print("  %s  %s touchdown: vision height rejected %s times; the IMU integrated %s %% of the true speed change" % (
        "PASS" if ok else "FAIL", n, r.group(1) if r else "?", m.group(2) if m else "?")); bad += not ok
print("  ----  the guide's last criterion -- the hover LOOKS steady in the Gazebo window -- needs you: FLY=1 GUI=true")
sys.exit(bad)
EOF
}
step 6 "gate (guide 5.6) from the numbers"
gate "$V"; res 6 $?

if [ "${FLY:-0}" = 1 ]; then
  step 7 "a new closed-loop flight (GUI=${GUI:-false})"
  mkdir -p "$V/fly/flights" "$V/fly/eval"
  # with the windows open, pictures of Gazebo and RViz are kept (capture_windows.sh)
  CAP=
  if [ "${GUI:-false}" = true ]; then
    bash scripts/stage5/capture_windows.sh "$V/fly/flights/verify_square" > "$V/shots.log" 2>&1 & CAP=$!
  fi
  FLIGHTS=$V/fly/flights EVAL=$V/fly/eval RVIZ=${RVIZ:-${GUI:-false}} bash scripts/stage5/run_closed_loop.sh verify_square room square --size 4 --alt 1.5 --speed 1 \
    | tee "$V/fly.log" | grep -E "^==|!!|RMSE|lag|verdict|mechanism" | sed 's/^/  /'
  if [ -n "$CAP" ]; then        # the pictures end at landing; give the conversion 60 s at most
    for _ in $(seq 60); do kill -0 $CAP 2>/dev/null || break; sleep 1; done
    kill $CAP 2>/dev/null; wait $CAP 2>/dev/null
    echo "  ----  $(cat "$V/shots.log" 2>/dev/null)"
    # $V is replaced on every run: the pictures are kept where the next run cannot delete them
    K=$S/verify_pictures/$(date +%Y%m%d_%H%M); mkdir -p "$K"
    cp "$V"/fly/flights/verify_square.shots/*.png "$K"/ 2>/dev/null && echo "  ----  pictures kept in $K"
  fi
  if [ -s "$V/fly/flights/verify_square.closed_loop.json" ]; then gate "$V/fly"; res 7 $?; else echo "  FAIL  no scored flight (see $V/fly.log)"; res 7 1; fi
fi

if [ "${MATRIX:-0}" = 1 ]; then
  step 8 "the closed-loop matrix (run_closed_loop_matrix.sh): complete, re-scored, tables regenerated"
  rc=0
  for a in fastlio2 fastlivo2; do
    [ -d "$S/matrix/$a/flights" ] || { echo "  FAIL  no $S/matrix/$a"; rc=1; continue; }
    rescore "$S/matrix/$a" "$V/matrix/$a" || rc=1
    [ -e "$S/matrix/$a/ev_delay.txt" ] && cp "$S/matrix/$a/ev_delay.txt" "$V/matrix/$a/"
  done
  python3 -W ignore scripts/stage5/matrix_summary.py "$V/matrix" > /dev/null || rc=1
  if diff -q "$S/matrix/matrix_tables.md" "$V/matrix/matrix_tables.md" > /dev/null; then
    echo "  PASS  matrix_tables.md identical after re-scoring"
  else echo "  FAIL  matrix_tables.md differs (diff $S/matrix/matrix_tables.md $V/matrix/matrix_tables.md)"; rc=1; fi
  python3 - "$S/matrix" <<'EOF' || rc=1
import os, sys
M = sys.argv[1]
conds = ["room", "room_plain", "corridor", "field"] + ["urban_alt%d" % h for h in (10, 20, 30, 40, 50, 60)] + \
        ["urban_speed%d" % v for v in (2, 5, 8)] + ["imu_x%d" % s for s in (3, 10, 30)] + \
        ["room_lidar_drop_2s", "room_lidar_drop_5s", "room_cam_black_5s"]
missing = []
for a in ("fastlio2", "fastlivo2"):
    for c in conds + (["room_evd%d" % d for d in (0, 40, 75, 110)] if a == "fastlivo2" else []):
        if a == "fastlio2" and c.startswith("room_cam"):
            continue
        if not os.path.exists(os.path.join(M, a, "flights", c + ".closed_loop.json")):
            missing.append("%s %s" % (a, c))
print("  %s  every matrix cell flown and scored%s" % ("PASS" if not missing else "FAIL", "" if not missing else ": missing " + ", ".join(missing)))
sys.exit(1 if missing else 0)
EOF
  res 8 $rc
fi

echo; echo "== summary ($(( ($(date +%s) - T0) / 60 )) min; details under $V/)"
[ ${#FAILED[@]} -eq 0 ] && echo "   ALL STEPS PASSED" || echo "   FAILED steps: ${FAILED[*]}"
exit ${#FAILED[@]}
