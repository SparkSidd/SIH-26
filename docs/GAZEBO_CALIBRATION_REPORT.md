# Gazebo Calibration Report
**Project**: SIH26123 — Edge-AI Distributed Fleet Coordination  
**Purpose**: Single-robot physical calibration results  
**Status**: ⏳ PENDING — to be completed after Gate 5 (single AMR spawn)

---

> [!NOTE]
> This report is populated during Gate 18 (single robot calibration).
> All values below are placeholders — they will be replaced with actual
> Gazebo-measured data after the physical environment is live.

---

## Test Platform

| Property | Value |
|---|---|
| **Robot ID** | R01 |
| **World** | warehouse_s1.sdf (open, no obstacles) |
| **ROS** | jazzy |
| **Gazebo** | Harmonic 8.x.x |
| **Date** | TBD |

---

## Calibration Sequence

### Test 1: Straight 5 m Forward

| Metric | Expected | Actual | Error |
|---|---|---|---|
| X displacement | 5.00 m | TBD | TBD |
| Y displacement | 0.00 m | TBD | TBD |
| Heading drift | 0.0° | TBD | TBD |
| Travel time | ~3.3 s (@ 1.5 m/s) | TBD | TBD |
| Odom X reading | 5.00 m | TBD | TBD |

**Command**:
```bash
ros2 topic pub --once /R01/cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 1.5}, angular: {z: 0.0}}"
sleep 3.5
ros2 topic pub --once /R01/cmd_vel geometry_msgs/msg/Twist "{}"
```

### Test 2: Straight 10 m Forward

| Metric | Expected | Actual | Error |
|---|---|---|---|
| X displacement | 10.00 m | TBD | TBD |
| Y displacement | 0.00 m | TBD | TBD |
| Heading drift | 0.0° | TBD | TBD |
| Odom X reading | 10.00 m | TBD | TBD |

### Test 3: Acceleration Profile

| Metric | Target | Actual |
|---|---|---|
| 0 → 1.0 m/s time | ~1.0 s (1.0 m/s²) | TBD |
| Distance during accel | ~0.5 m | TBD |

### Test 4: Deceleration / Stopping

| Metric | Target | Actual |
|---|---|---|
| 1.0 m/s → 0 time | ~0.5 s (2.0 m/s²) | TBD |
| Stopping distance | ~0.25 m | TBD |
| Residual motion | 0 | TBD |

### Test 5: Reverse (5 m)

| Metric | Expected | Actual | Error |
|---|---|---|---|
| X displacement | −5.00 m | TBD | TBD |
| Heading change | 0.0° | TBD | TBD |

**Command**:
```bash
ros2 topic pub --once /R01/cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: -1.0}, angular: {z: 0.0}}"
sleep 5.5
ros2 topic pub --once /R01/cmd_vel geometry_msgs/msg/Twist "{}"
```

### Test 6: 90° Left Turn (in-place)

| Metric | Expected | Actual | Error |
|---|---|---|---|
| Yaw change | +90° (+π/2 rad) | TBD | TBD |
| X displacement | ~0 m | TBD | TBD |
| Y displacement | ~0 m | TBD | TBD |

**Derived turn time**:
- Angular velocity: 1.0 rad/s (conservative)
- Required: π/2 ÷ 1.0 = ~1.57 s

```bash
ros2 topic pub --once /R01/cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.0}, angular: {z: 1.0}}"
sleep 1.6
ros2 topic pub --once /R01/cmd_vel geometry_msgs/msg/Twist "{}"
```

### Test 7: 90° Right Turn (in-place)

| Metric | Expected | Actual | Error |
|---|---|---|---|
| Yaw change | −90° (−π/2 rad) | TBD | TBD |

### Test 8: 360° Rotation in Place

| Metric | Expected | Actual | Error |
|---|---|---|---|
| Net yaw change | 360° (2π rad) | TBD | TBD |
| X displacement | ~0 m | TBD | TBD |
| Y displacement | ~0 m | TBD | TBD |
| X/Y drift | < 0.1 m | TBD | TBD |

---

## Odometry Accuracy Summary

| Test | Odom Error | Category |
|---|---|---|
| 5 m straight | TBD | Translational |
| 10 m straight | TBD | Translational (accumulated) |
| 90° left | TBD | Rotational |
| 90° right | TBD | Rotational |
| 360° | TBD | Rotational (accumulated) |

---

## Sensor Verification

### LiDAR (during calibration)

| Check | Expected | Actual |
|---|---|---|
| Range to north wall (at y=17, wall at y=19.9) | ~2.9 m | TBD |
| Range to south wall (at y=17, wall at y=0.1) | ~16.9 m | TBD |
| Scan update frequency | 10 Hz | TBD |
| Sample count | 360 | TBD |
| NaN count | 0 (open space) | TBD |

### IMU (at rest)

| Check | Expected | Actual |
|---|---|---|
| Linear accel Z | ~9.81 m/s² | TBD |
| Linear accel X/Y | ~0 m/s² | TBD |
| Angular velocity | ~0 rad/s | TBD |
| Update frequency | 100 Hz | TBD |

---

## Calibration Conclusions

> **To be filled in after physical tests complete.**

- Odometry accuracy: TBD
- Translational error per meter: TBD
- Rotational error per radian: TBD
- Stopping distance: TBD
- Sensor timing: TBD

---

## Tuning Applied (if any)

> Document any SDF parameter changes made to correct calibration errors.
> 
> **RULE**: Do NOT tune to reproduce the Python benchmark result.
> Tune only for physical realism.

| Parameter | Original | Tuned | Reason |
|---|---|---|---|
| (none yet) | — | — | — |

---

*This report will be completed during Gate 18.*  
*Last updated: 2026-09-12 — TEMPLATE ONLY*
