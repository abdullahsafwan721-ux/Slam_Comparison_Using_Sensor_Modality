#!/usr/bin/env bash
# Stage 5 evaluation (guide 5.5, extended). HOST, project root:
#   bash scripts/stage5/eval_closed_loop.sh <name>        # output/stage5/flights/<name>.bag
#   FLIGHTS=<dir> EVAL=<dir>                              # another flights / scores folder
# Guide 5.5, unchanged in substance: two numbers, two questions
#   <algo>__<name>__r1  the SLAM method's pose vs ground truth (IMU)   = SLAM accuracy in closed loop
#   px4__<name>__r1     PX4's /mavros/local_position/pose vs truth     = what the vehicle believed
# Changes (docs/stage5_log.md):
#   * PX4's estimate is scored against the ground truth of base_link (the vehicle), not of the
#     IMU: the guide noted the 0.134 m lever arm adds error under rotation; it is removed
#     exactly instead (closed_loop_metrics.py gtbase, mount from rig.yaml).
#   * bag tools run through ros_python.sh (Stage 1-2 audit); metrics_extra.py adds the
#     flight-window APE, h/v split, drift and TSR used in Stages 3-4 (tau 0.25 m indoors,
#     1.0 m outdoors, as in Stage 4).
#   * closed_loop_metrics.py report: relay check, EKF2 vs SLAM (+ lag), PX4 vs truth
#     unaligned, setpoint tracking, hover steadiness (the plan's 6.6 addition), and for a
#     fault flight what happened around the fault; bag_modes.py: PX4's mode changes.
#   * if the flight kept PX4's own log (<name>.ulg), ulog_touchdown.py: what EKF2 did at
#     touchdown -> <name>.touchdown.txt
#   * the method comes from <name>.algo (written at flight time; none = fastlio2). FAST-LIVO2
#     is scored on its own pose file (<name>.livo_result/sim.txt, state-time stamps), as in
#     Stages 3-4; its topic is stamped ~75 ms late (A8).
#   * a step that fails (a partial flight) does not stop the closed-loop report.
set -o pipefail
N=$1; D=${FLIGHTS:-output/stage5/flights}; E=${EVAL:-output/stage5/eval}   # verify_stage5.sh points these elsewhere
[ -s $D/$N.bag ] || { echo "!! $D/$N.bag missing"; exit 1; }
mkdir -p $E
A=$(cat $D/$N.algo 2>/dev/null || echo fastlio2)
W=$(sed -n 's/^world //p' $D/$N.config.txt 2>/dev/null); W=${W:-room}
case "$W" in room*|corridor*) TAU=0.25 ;; *) TAU=1.0 ;; esac
SRC="bag_to_tum /Odometry"
if [ "$A" = fastlivo2 ]; then
  if [ -s $D/$N.livo_result/sim.txt ]; then SRC="pose file"; else SRC="bag_to_tum /aft_mapped_to_init (publish-time stamps)"; fi
fi
RP="bash /scripts/common/ros_python.sh"
docker compose run --rm -T eval bash -c "
  cd /$D
  ok() { \"\$@\" || echo \"!! failed: \$*\"; }
  ok $RP /scripts/common/bag_to_tum.py $N.bag /ground_truth/odom $N.gt.tum
  ok $RP /scripts/common/bag_to_tum.py $N.bag /mavros/local_position/pose $N.px4.tum
  ok $RP /scripts/common/bag_to_tum.py $N.bag /mavros/vision_pose/pose $N.vision.tum
  ok $RP /scripts/common/bag_to_tum.py $N.bag /mavros/setpoint_position/local $N.setpoint.tum
  ok $RP /scripts/stage5/bag_modes.py $N.bag $N.modes.txt
  case '$SRC' in
    'pose file') cp $N.livo_result/sim.txt $N.$A.tum ;;
    *fastlivo2*|*aft_mapped*) ok $RP /scripts/common/bag_to_tum.py $N.bag /aft_mapped_to_init $N.$A.tum ;;
    *) ok $RP /scripts/common/bag_to_tum.py $N.bag /Odometry $N.$A.tum ;;
  esac
  ok python3 /scripts/stage5/closed_loop_metrics.py gtbase $N.gt.tum $N.gt_base.tum
  for a in $A px4; do
    g=$N.gt.tum; [ \$a = px4 ] && g=$N.gt_base.tum
    ok bash /scripts/common/eval_traj.sh \$g $N.\$a.tum /$E/\${a}__${N}__r1 && \
    ok python3 /scripts/common/metrics_extra.py \$g $N.\$a.tum /$E/\${a}__${N}__r1 --tau $TAU > /dev/null
  done
  ok python3 /scripts/common/results_table.py /$E > /dev/null
  python3 /scripts/stage5/closed_loop_metrics.py report /$D $N --algo $A" 2>&1 | grep -v "^ Container\|mode/arming changes"
RC=$?
if [ -s $D/$N.ulg ]; then
  docker compose run --rm -T sim python3 /scripts/stage5/ulog_touchdown.py /$D/$N.ulg 2>&1 | grep -v "^ Container" > $D/$N.touchdown.txt
  grep -E "^(verdict|mechanism)" $D/$N.touchdown.txt | sed 's/^/   /'
fi
docker compose run --rm -T eval chown -R "$(id -u):$(id -g)" "/$D" "/$E" > /dev/null 2>&1
exit $RC
