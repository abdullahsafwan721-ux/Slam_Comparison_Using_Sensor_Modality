// trajectory_driver — Gazebo 11 model plugin (Stage 2).
//
// Moves a model along a smooth, repeatable 6-DoF path WITHOUT a flight
// controller, so sensor problems can be found before any vehicle dynamics are
// involved.
//
// Why velocities and not poses: Gazebo's IMU computes linear acceleration by
// finite-differencing the link's world velocity (gazebo/sensors/ImuSensor.cc).
// Teleporting the model with SetWorldPose leaves velocity at zero, so the IMU
// would report no motion at all. Setting velocity every physics step keeps the
// IMU, the LiDAR and the ground truth mutually consistent.
//
// Path (relative to the spawn pose, which is taken as the centre):
//   position    = s(t) * [ax sin(wt),   ay sin(2wt),   az sin(wt/2)]
//   orientation = spawn * RPY(s(t) * [ar sin(1.3wt), ap sin(0.7wt), ay sin(wt)])
// with a stationary hold first (gravity initialisation) and a smoothstep
// amplitude ramp s(t) so acceleration never jumps.

#include <algorithm>
#include <cmath>
#include <functional>
#include <sstream>

#include <gazebo/common/common.hh>
#include <gazebo/gazebo.hh>
#include <gazebo/physics/physics.hh>
#include <ignition/math/Pose3.hh>
#include <ignition/math/Quaternion.hh>
#include <ignition/math/Vector3.hh>

namespace gazebo
{
using ignition::math::Pose3d;
using ignition::math::Quaterniond;
using ignition::math::Vector3d;

class TrajectoryDriver : public ModelPlugin
{
public:
  void Load(physics::ModelPtr model, sdf::ElementPtr sdf) override
  {
    model_ = model;
    hold_   = Get(sdf, "hold", 8.0);
    ramp_   = Get(sdf, "ramp", 4.0);
    period_ = Get(sdf, "period", 30.0);
    ampXyz_ = GetVec(sdf, "amp_xyz", Vector3d(3.0, 2.0, 0.5));
    ampRpy_ = GetVec(sdf, "amp_rpy", Vector3d(0.15, 0.15, 0.6));
    centre_ = model_->WorldPose();          // spawn pose = path centre
    conn_ = event::Events::ConnectWorldUpdateBegin(
        std::bind(&TrajectoryDriver::OnUpdate, this));
    gzmsg << "[trajectory_driver] hold=" << hold_ << "s ramp=" << ramp_
          << "s period=" << period_ << "s amp_xyz=" << ampXyz_
          << " amp_rpy=" << ampRpy_ << "\n";
  }

private:
  static double Get(const sdf::ElementPtr &sdf, const std::string &k, double d)
  {
    return sdf->HasElement(k) ? sdf->Get<double>(k) : d;
  }
  static Vector3d GetVec(const sdf::ElementPtr &sdf, const std::string &k, const Vector3d &d)
  {
    if (!sdf->HasElement(k)) return d;
    std::istringstream in(sdf->Get<std::string>(k));
    double x, y, z;
    return (in >> x >> y >> z) ? Vector3d(x, y, z) : d;
  }

  // Reference pose at simulation time t.
  Pose3d Ref(double t) const
  {
    const double tm = t - hold_;
    if (tm <= 0.0) return centre_;
    const double u = std::min(1.0, tm / ramp_);
    const double s = u * u * (3.0 - 2.0 * u);                     // smoothstep
    const double w = 2.0 * M_PI / period_;
    const Vector3d dp(ampXyz_.X() * std::sin(w * tm),
                      ampXyz_.Y() * std::sin(2.0 * w * tm),
                      ampXyz_.Z() * std::sin(0.5 * w * tm));
    const Quaterniond dq(s * ampRpy_.X() * std::sin(1.3 * w * tm),
                         s * ampRpy_.Y() * std::sin(0.7 * w * tm),
                         s * ampRpy_.Z() * std::sin(w * tm));
    return Pose3d(centre_.Pos() + s * dp, centre_.Rot() * dq);
  }

  // Rotation vector (axis * angle) of a unit quaternion, shortest way round.
  static Vector3d Log(Quaterniond q)
  {
    if (q.W() < 0.0) q = Quaterniond(-q.W(), -q.X(), -q.Y(), -q.Z());
    Vector3d axis;
    double angle;
    q.ToAxis(axis, angle);
    return (std::abs(angle) < 1e-12) ? Vector3d::Zero : axis * angle;
  }

  void OnUpdate()
  {
    const double t = model_->GetWorld()->SimTime().Double();
    const double h = 1e-3;
    const Pose3d ref = Ref(t), refP = Ref(t + h), refM = Ref(t - h);
    const Pose3d cur = model_->WorldPose();

    // Feed-forward from the analytic path (central differences, world frame)
    // plus gentle feedback so integration error can never accumulate.
    const Vector3d vFF = (refP.Pos() - refM.Pos()) / (2.0 * h);
    const Vector3d wFF = Log(refP.Rot() * refM.Rot().Inverse()) / (2.0 * h);
    const Vector3d v = vFF + kPos_ * (ref.Pos() - cur.Pos());
    const Vector3d w = wFF + kRot_ * Log(ref.Rot() * cur.Rot().Inverse());

    model_->SetLinearVel(v);
    model_->SetAngularVel(w);
  }

  physics::ModelPtr model_;
  event::ConnectionPtr conn_;
  Pose3d centre_;
  double hold_{8.0}, ramp_{4.0}, period_{30.0};
  Vector3d ampXyz_, ampRpy_;
  const double kPos_{2.0}, kRot_{2.0};
};

GZ_REGISTER_MODEL_PLUGIN(TrajectoryDriver)
}  // namespace gazebo
