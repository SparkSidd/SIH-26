#!/usr/bin/env python3
import os
import subprocess
import sys
import tempfile
import time

ROBOT_IDS = [f"R{i:02d}" for i in range(1, 7)]

# Default spawns in world frame (x, y, z, yaw)
SPAWN_POSES = {
    "R01": (2.0, 17.0, 0.28, 0.0),
    "R02": (2.0, 9.0, 0.28, 0.0),
    "R03": (2.0, 2.0, 0.28, 0.0),
    "R04": (10.0, 9.0, 0.28, 0.0),
    "R05": (5.0, 14.0, 0.28, 0.0),
    "R06": (5.0, 5.0, 0.28, 0.0),
}

_ROBOT_COLORS = {
    "R01": "0.15 0.38 0.92 1",  # Precision Blue (#2563eb)
    "R02": "0.05 0.75 0.95 1",  # Electric Cyan (#06b6d4)
    "R03": "0.08 0.75 0.35 1",  # Emerald Green (#10b981)
    "R04": "0.95 0.80 0.05 1",  # Golden Yellow (#eab308)
    "R05": "0.98 0.45 0.08 1",  # Safety Orange (#f97316)
    "R06": "0.68 0.25 0.95 1",  # Vivid Purple (#a855f7)
}

SDF_DIR = "/tmp/sih26_amr"
TEMPLATE_PATH = "/home/siddharth/sih26/ros2_integration/models/amr/model.sdf"


def generate_sdfs():
    os.makedirs(SDF_DIR, exist_ok=True)
    with open(TEMPLATE_PATH, "r") as f:
        template = f.read()

    for rid in ROBOT_IDS:
        sdf = template.replace('<model name="amr">', f'<model name="{rid}">')
        color = _ROBOT_COLORS.get(rid, "0.15 0.38 0.92 1")
        sdf = sdf.replace("<ambient>0.1 0.5 0.9 1</ambient>", f"<ambient>{color}</ambient>")
        sdf = sdf.replace("<diffuse>0.1 0.5 0.9 1</diffuse>", f"<diffuse>{color}</diffuse>")

        payload_xml = f"""
      <visual name="id_face_front">
        <pose>0.024 0 0.39 0 0 0</pose>
        <geometry><box><size>0.005 0.30 0.11</size></box></geometry>
        <material><ambient>{color}</ambient><diffuse>{color}</diffuse><specular>0.6 0.6 0.6 1</specular></material>
      </visual>
      <visual name="id_face_back">
        <pose>-0.024 0 0.39 0 0 0</pose>
        <geometry><box><size>0.005 0.30 0.11</size></box></geometry>
        <material><ambient>{color}</ambient><diffuse>{color}</diffuse><specular>0.6 0.6 0.6 1</specular></material>
      </visual>
      <visual name="cargo_payload_body">
        <pose>-0.18 0 0.27 0 0 0</pose>
        <geometry><box><size>0.34 0.38 0.18</size></box></geometry>
        <material><ambient>0.82 0.52 0.12 1</ambient><diffuse>0.92 0.60 0.15 1</diffuse><specular>0.3 0.3 0.3 1</specular></material>
      </visual>
      <visual name="cargo_payload_lid">
        <pose>-0.18 0 0.365 0 0 0</pose>
        <geometry><box><size>0.36 0.40 0.02</size></box></geometry>
        <material><ambient>0.20 0.24 0.32 1</ambient><diffuse>0.25 0.30 0.40 1</diffuse><specular>0.4 0.4 0.4 1</specular></material>
      </visual>
      <visual name="cargo_payload_latch">
        <pose>-0.18 0 0.37 0 0 0</pose>
        <geometry><box><size>0.10 0.41 0.015</size></box></geometry>
        <material><ambient>0.95 0.75 0.05 1</ambient><diffuse>0.98 0.80 0.08 1</diffuse></material>
      </visual>
      <visual name="cargo_barcode_plate">
        <pose>-0.008 0 0.27 0 0 0</pose>
        <geometry><box><size>0.004 0.22 0.10</size></box></geometry>
        <material><ambient>0.95 0.95 0.95 1</ambient><diffuse>0.98 0.98 0.98 1</diffuse></material>
      </visual>
        """
        sdf = sdf.replace("<!-- ROBOT_PAYLOAD_VISUAL -->", payload_xml)
        sdf = sdf.replace("<topic>cmd_vel</topic>", f"<topic>/{rid}/cmd_vel</topic>")
        sdf = sdf.replace("<odom_topic>odometry</odom_topic>", f"<odom_topic>/{rid}/odometry</odom_topic>")
        sdf = sdf.replace("<tf_topic>tf</tf_topic>", f"<tf_topic>/{rid}/tf</tf_topic>")
        sdf = sdf.replace("<topic>scan</topic>", f"<topic>/{rid}/scan</topic>")
        sdf = sdf.replace("<topic>imu</topic>", f"<topic>/{rid}/imu</topic>")

        out_path = os.path.join(SDF_DIR, f"{rid}.sdf")
        with open(out_path, "w") as out:
            out.write(sdf)
    print(f"Generated 6 AMR SDF files in {SDF_DIR}")


def get_existing_models():
    res = subprocess.run(
        ["gz", "service", "-s", "/world/warehouse_s1/scene/info",
         "--reqtype", "gz.msgs.Empty", "--reptype", "gz.msgs.Scene",
         "--timeout", "2000", "--req", ""],
        capture_output=True, text=True
    )
    names = set()
    for line in res.stdout.splitlines():
        if "name:" in line:
            parts = line.strip().split('"')
            if len(parts) >= 2:
                names.add(parts[1])
    return names


def spawn_missing_robots():
    generate_sdfs()
    existing = get_existing_models()
    print(f"Existing models in Gazebo: {existing & set(ROBOT_IDS)}")

    for rid in ROBOT_IDS:
        if rid not in existing:
            x, y, z, yaw = SPAWN_POSES[rid]
            sdf_path = os.path.join(SDF_DIR, f"{rid}.sdf")
            print(f"Spawning {rid} at ({x}, {y}, {z})...")
            cmd = [
                "ros2", "run", "ros_gz_sim", "create",
                "-world", "warehouse_s1",
                "-name", rid,
                "-file", sdf_path,
                "-x", str(x), "-y", str(y), "-z", str(z), "-Y", str(yaw)
            ]
            subprocess.run(cmd, check=True)
            time.sleep(1.0)
        else:
            print(f"{rid} already present in scene.")


def reset_all_poses():
    print("Resetting all robot poses to initial positions...")
    for rid, (x, y, z, yaw) in SPAWN_POSES.items():
        req = f'name: "{rid}", position: {{x: {x}, y: {y}, z: {z}}}'
        cmd = [
            "gz", "service", "-s", "/world/warehouse_s1/set_pose",
            "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
            "--timeout", "2000", "--req", req
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        print(f"Reset {rid} -> ({x}, {y}, {z}): {res.stdout.strip()}")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "setup"
    if action == "setup":
        spawn_missing_robots()
        reset_all_poses()
    elif action == "reset":
        reset_all_poses()
    elif action == "sdfs":
        generate_sdfs()
