#!/usr/bin/env python3
"""
gazebo_data_logger.py — Per-run data recorder for Gazebo validation.

Subscribes to ROS topics for all active robots and writes structured
CSV/JSON logs to results/gazebo/<run_id>/.

Usage:
    ros2 run ros2_integration gazebo_data_logger \
        --ros-args -p run_id:=S1_proposed_001 -p scenario:=S1 \
                   -p policy:=proposed -p num_robots:=6
"""

import os
import csv
import json
import time
import math
import threading
from datetime import datetime, timezone

# ROS 2 imports (real environment)
try:
    import rclpy
    from rclpy.node import Node
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan, Imu
    from geometry_msgs.msg import Twist
    from rosgraph_msgs.msg import Clock
    REAL_ROS = True
except ImportError:
    from ros2_integration.mock_ros.rclpy_stub import Node
    REAL_ROS = False

# Project root is on PYTHONPATH
PROJECT_ROOT = os.environ.get(
    "SIH_PROJECT_ROOT",
    os.path.expanduser("~/sih26")
)
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results", "gazebo")

ROBOT_IDS = [f"R{i:02d}" for i in range(1, 7)]

DEFAULT_SPAWNS = {
    "R01": (2.0, 17.0),
    "R02": (2.0, 9.0),
    "R03": (2.0, 2.0),
    "R04": (10.0, 9.0),
    "R05": (5.0, 14.0),
    "R06": (5.0, 5.0),
}


class GazeboDataLogger(Node):
    """
    Records per-run Gazebo validation data to structured files.

    Output structure:
        results/gazebo/<run_id>/
            run_manifest.json
            robot_states.csv       (odom @ 10 Hz)
            collision_metrics.csv  (min separation, contact events)
            task_metrics.csv       (populated by AMRNode events)
            planner_metrics.csv    (planning latency from AMRNode)
            network_metrics.csv    (belief age stub)
    """

    def __init__(self):
        super().__init__("gazebo_data_logger")

        # Parameters
        self.declare_parameter("run_id", "unnamed_run")
        self.declare_parameter("scenario", "S1")
        self.declare_parameter("policy", "proposed")
        self.declare_parameter("num_robots", 6)
        self.declare_parameter("seed", 0)
        if not self.has_parameter("use_sim_time"):
            self.declare_parameter("use_sim_time", True)

        self.run_id = self.get_parameter("run_id").value
        self.scenario = self.get_parameter("scenario").value
        self.policy = self.get_parameter("policy").value
        self.num_robots = int(self.get_parameter("num_robots").value)
        self.seed = self.get_parameter("seed").value

        # Output directory
        self.run_dir = os.path.join(RESULTS_DIR, self.scenario, self.run_id)
        os.makedirs(self.run_dir, exist_ok=True)

        self.get_logger().info(f"DataLogger: writing to {self.run_dir}")

        # Get scenario spawn positions
        self.spawns = dict(DEFAULT_SPAWNS)
        try:
            from ros2_integration.fleet_launcher import SCENARIOS
            from ros2_integration.coordinate_bridge import grid_to_world
            sc_info = SCENARIOS.get(self.scenario.upper(), SCENARIOS["S1"])
            for i, rid in enumerate(ROBOT_IDS):
                if i < len(sc_info["robot_starts"]):
                    c, r = sc_info["robot_starts"][i]
                    wx, wy, _ = grid_to_world(c, r, 20)
                    self.spawns[rid] = (wx, wy)
        except Exception as e:
            self.get_logger().warn(f"Failed to load scenario spawns, using defaults: {e}")

        # State
        self._lock = threading.Lock()
        self._robot_poses = {}   # robot_id -> (x, y, yaw, vx, vy, wz, t)
        self._sim_time = 0.0
        self._start_wall = time.time()
        self._start_sim = None

        # CSV writers
        self._robot_csv = self._open_csv(
            "robot_states.csv",
            ["sim_time", "wall_time", "robot_id",
             "x", "y", "yaw", "vx", "vy", "wz"]
        )
        self._collision_csv = self._open_csv(
            "collision_metrics.csv",
            ["sim_time", "robot_i", "robot_j", "separation_m", "event"]
        )
        self._task_csv = self._open_csv(
            "task_metrics.csv",
            ["sim_time", "robot_id", "task_id", "event",
             "pickup", "dropoff", "duration_s"]
        )
        self._planner_csv = self._open_csv(
            "planner_metrics.csv",
            ["sim_time", "robot_id", "plan_latency_ms",
             "path_length_cells", "replanned"]
        )

        # Subscriptions
        self._odom_subs = []
        for rid in ROBOT_IDS[:self.num_robots]:
            sub = self.create_subscription(
                Odometry,
                f"/{rid}/odom",
                lambda msg, r=rid: self._odom_cb(msg, r),
                10
            )
            self._odom_subs.append(sub)

        self._clock_sub = self.create_subscription(
            Clock, "/clock", self._clock_cb, 10
        )

        # Periodic separation check (10 Hz)
        self._sep_timer = self.create_timer(0.1, self._check_separations)

        # Manifest at start
        self._write_manifest()

        self.get_logger().info("GazeboDataLogger ready.")

    def _open_csv(self, filename: str, headers: list) -> csv.writer:
        path = os.path.join(self.run_dir, filename)
        f = open(path, "w", newline="")
        writer = csv.writer(f)
        writer.writerow(headers)
        f.flush()
        return writer

    def _write_manifest(self):
        import subprocess
        try:
            gz_ver = subprocess.check_output(
                ["gz", "sim", "--version"], stderr=subprocess.STDOUT
            ).decode().split("\n")[0]
        except Exception:
            gz_ver = "unknown"

        manifest = {
            "run_id": self.run_id,
            "scenario": self.scenario,
            "policy": self.policy,
            "seed": self.seed,
            "robot_count": self.num_robots,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "software": {
                "ros_distro": os.environ.get("ROS_DISTRO", "jazzy"),
                "gazebo_version": gz_ver,
                "python": "3.12",
                "coordinator_checkpoint": "CHECKPOINT_FINAL_PRE_GAZEBO",
            },
            "physics": {
                "step_size_ms": 1,
                "real_time_factor": 1.0,
                "world": f"warehouse_{self.scenario.lower()}.sdf",
            },
            "network": {
                "latency_ms": 0,
                "jitter_ms": 0,
                "loss_pct": 0,
            }
        }
        path = os.path.join(self.run_dir, "run_manifest.json")
        with open(path, "w") as f:
            json.dump(manifest, f, indent=2)
        self.get_logger().info(f"Manifest written: {path}")

    def _clock_cb(self, msg):
        self._sim_time = msg.clock.sec + msg.clock.nanosec * 1e-9
        if self._start_sim is None:
            self._start_sim = self._sim_time

    def _odom_cb(self, msg: Odometry, robot_id: str):
        raw_x = msg.pose.pose.position.x
        raw_y = msg.pose.pose.position.y
        spawn = self.spawns.get(robot_id, (0.0, 0.0))
        x = spawn[0] + raw_x
        y = spawn[1] + raw_y

        q = msg.pose.pose.orientation
        # Yaw from quaternion
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        vx = msg.twist.twist.linear.x
        vy = msg.twist.twist.linear.y
        wz = msg.twist.twist.angular.z
        t = self._sim_time

        with self._lock:
            self._robot_poses[robot_id] = (x, y, yaw, vx, vy, wz, t)

        wall_t = time.time() - self._start_wall
        self._robot_csv.writerow([
            f"{t:.3f}", f"{wall_t:.3f}", robot_id,
            f"{x:.4f}", f"{y:.4f}", f"{yaw:.4f}",
            f"{vx:.4f}", f"{vy:.4f}", f"{wz:.4f}"
        ])

    def _check_separations(self):
        """Compute pairwise separations and log near-misses."""
        with self._lock:
            poses = dict(self._robot_poses)

        robots = list(poses.keys())
        for i in range(len(robots)):
            for j in range(i + 1, len(robots)):
                ri, rj = robots[i], robots[j]
                xi, yi = poses[ri][0], poses[ri][1]
                xj, yj = poses[rj][0], poses[rj][1]
                sep = math.sqrt((xi - xj)**2 + (yi - yj)**2)

                # Near-miss threshold: 0.6 m (robot width)
                if sep < 0.6:
                    event = "NEAR_MISS" if sep > 0.45 else "CONTACT"
                    self._collision_csv.writerow([
                        f"{self._sim_time:.3f}", ri, rj,
                        f"{sep:.4f}", event
                    ])
                    if event == "CONTACT":
                        self.get_logger().warn(
                            f"CONTACT: {ri}↔{rj} separation={sep:.3f} m "
                            f"at sim_t={self._sim_time:.1f}s"
                        )

    def log_task_event(self, robot_id: str, task_id: str,
                       event: str, pickup=None, dropoff=None,
                       duration_s=None):
        """Called by AMRNode when task lifecycle events occur."""
        self._task_csv.writerow([
            f"{self._sim_time:.3f}", robot_id, task_id, event,
            str(pickup), str(dropoff),
            f"{duration_s:.3f}" if duration_s else ""
        ])

    def log_plan(self, robot_id: str, latency_ms: float,
                 path_length: int, replanned: bool):
        """Called by AMRNode when a path plan completes."""
        self._planner_csv.writerow([
            f"{self._sim_time:.3f}", robot_id,
            f"{latency_ms:.2f}", path_length, replanned
        ])


def main(args=None):
    rclpy.init(args=args)
    node = GazeboDataLogger()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
