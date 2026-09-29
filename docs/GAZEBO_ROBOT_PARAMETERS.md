# Gazebo Robot Physical Parameters
**Project**: SIH26123 — Edge-AI Distributed Fleet Coordination  
**Document**: Physical parameters of the AMR model in Gazebo Harmonic  
**Source**: `ros2_integration/models/amr/model.sdf`

---

## Chassis

| Parameter | Value | Notes |
|---|---|---|
| **Length** | 0.8 m | X-axis |
| **Width** | 0.6 m | Y-axis |
| **Height** | 0.35 m | Z-axis |
| **Bounding radius** | 0.45 m | √(0.4² + 0.3²) + safety margin |
| **Mass** | 80.0 kg | Chassis only |
| **Ixx** | 2.9 kg·m² | Roll inertia |
| **Iyy** | 5.0 kg·m² | Pitch inertia |
| **Izz** | 6.4 kg·m² | Yaw inertia (primary) |

## Collision Geometry

| Surface | Shape | Size | Friction μ |
|---|---|---|---|
| **Chassis** | Box | 0.8 × 0.6 × 0.35 m | μ=0.8 (ODE) |
| **Caster wheel** | Sphere | r=0.05 m | μ=0.0 (free rolling) |
| **Drive wheels** | Cylinder | r=0.15 m, L=0.06 m | μ=1.0 / μ₂=0.5 |

## Drive System

| Parameter | Value |
|---|---|
| **Drive type** | Differential drive |
| **Plugin** | `gz-sim-diff-drive-system` |
| **Left joint** | `left_wheel_joint` |
| **Right joint** | `right_wheel_joint` |
| **Wheel radius** | 0.15 m |
| **Wheel separation** | 0.52 m (centre-to-centre) |
| **Max linear velocity** | 1.5 m/s |
| **Max angular velocity** | 3.14 rad/s (≈180°/s) |
| **Max linear acceleration** | 1.0 m/s² |
| **Max linear deceleration** | 2.0 m/s² |
| **Max angular acceleration** | 3.14 rad/s² |
| **Odometry publish rate** | 30 Hz |

## Wheel Physical Parameters

| Parameter | Value |
|---|---|
| **Wheel mass** | 2.0 kg × 2 = 4.0 kg total |
| **Wheel Ixx/Iyy** | 0.0051 kg·m² |
| **Wheel Izz** | 0.0090 kg·m² |
| **Wheel offset Y (left)** | +0.26 m |
| **Wheel offset Y (right)** | −0.26 m |
| **Wheel offset Z** | −0.125 m (below chassis centre) |

## Total Vehicle Mass

| Component | Mass |
|---|---|
| Chassis | 80.0 kg |
| Left wheel | 2.0 kg |
| Right wheel | 2.0 kg |
| **Total** | **84.0 kg** |

## Sensors

### 2D LiDAR

| Parameter | Value |
|---|---|
| **Type** | `gpu_lidar` |
| **Pose** | (0, 0, 0.2) relative to base_link |
| **Update rate** | 10 Hz |
| **Angular range** | −180° to +180° (full 360°) |
| **Samples** | 360 |
| **Resolution** | 1° |
| **Range min** | 0.1 m |
| **Range max** | 10.0 m |
| **Range resolution** | 0.01 m |
| **Noise** | Gaussian, mean=0, σ=0.01 m |
| **ROS topic** | `/{robot_id}/scan` |
| **ROS message** | `sensor_msgs/msg/LaserScan` |

### IMU

| Parameter | Value |
|---|---|
| **Type** | `imu` |
| **Pose** | (0, 0, 0.1) relative to base_link |
| **Update rate** | 100 Hz |
| **Angular velocity noise** | Gaussian, mean=0, σ=0.001 rad/s |
| **Linear acceleration noise** | Gaussian, mean=0, σ=0.01 m/s² |
| **ROS topic** | `/{robot_id}/imu` |
| **ROS message** | `sensor_msgs/msg/Imu` |

## Topic Interface

| Topic | Direction | Message Type | Hz |
|---|---|---|---|
| `/{robot_id}/cmd_vel` | ROS → Gazebo | `geometry_msgs/Twist` | Up to 10 |
| `/{robot_id}/odom` | Gazebo → ROS | `nav_msgs/Odometry` | 30 |
| `/{robot_id}/scan` | Gazebo → ROS | `sensor_msgs/LaserScan` | 10 |
| `/{robot_id}/imu` | Gazebo → ROS | `sensor_msgs/Imu` | 100 |
| `/clock` | Gazebo → ROS | `rosgraph_msgs/Clock` | ~1000 |

## Derivation Notes

These parameters are derived from the frozen Python simulator's `RobotGeometry` class:

| Python Simulator | Gazebo Model |
|---|---|
| `footprint = 0.45 m` | Box 0.8×0.6 + caster → bounding ~0.45 m radius ✅ |
| `max_velocity = 1.5 m/s` | `max_linear_velocity = 1.5` ✅ |
| `max_accel = 1.0 m/s²` | `max_linear_accel = 1.0` ✅ |
| `mass ≈ 80 kg` | chassis mass = 80.0 kg ✅ |

## Physical Realism Assessment

| Aspect | Modeled | Not Modeled |
|---|---|---|
| Collision geometry | ✅ Box + cylinder wheels | Detailed body shape |
| Wheel kinematics | ✅ Differential drive | Slip, tire flex |
| Mass/inertia | ✅ Realistic 84 kg | Battery electrochemistry |
| Velocity limits | ✅ 1.5 m/s, 3.14 rad/s | Per-actuator torque |
| Acceleration | ✅ 1.0/2.0 m/s² | Load-dependent accel |
| Friction | ✅ μ=1.0 wheels | Road surface variability |
| Odometry | ✅ 30 Hz | Slip-based odom error |
| LiDAR | ✅ 360°, 10 Hz, σ=0.01 m | Beam divergence |
| IMU | ✅ 100 Hz, σ=0.001 rad/s | Temperature drift |
| Suspension | ❌ Not modeled | Out of scope |
| Battery | ❌ Not modeled | Out of scope |

---

*Document auto-generated from model.sdf analysis.*  
*Last updated: 2026-09-12*
