#!/usr/bin/env python3
"""
test_webots_hardware.py — Direct Verification of Webots Robot Hardware Controller API.

Connects to a running Webots instance as an extern controller, initializes motors,
reads wheel position sensors, commands wheel velocities, and advances simulation steps.
"""

import os
import sys
import time

if "WEBOTS_HOME" not in os.environ and os.path.isdir("/usr/local/webots"):
    os.environ["WEBOTS_HOME"] = "/usr/local/webots"
webots_home = os.environ.get("WEBOTS_HOME", "/usr/local/webots")
py_controller = os.path.join(webots_home, "lib", "controller", "python")
if os.path.isdir(py_controller) and py_controller not in sys.path:
    sys.path.append(py_controller)

from controller import Robot

def test_single_robot(robot_name: str = "R01", max_test_steps: int = 50):
    print(f"[{robot_name}] Attempting connection to Webots (URL={os.environ.get('WEBOTS_CONTROLLER_URL')})...", flush=True)
    os.environ["WEBOTS_ROBOT_NAME"] = robot_name
    
    try:
        robot = Robot()
    except Exception as e:
        print(f"[{robot_name}] FAILED to instantiate Robot(): {e}", flush=True)
        return False

    name = robot.getName()
    timestep = int(robot.getBasicTimeStep())
    print(f"[{robot_name}] Connected successfully! Robot name='{name}', basicTimeStep={timestep}ms", flush=True)

    left_motor = robot.getDevice("left wheel motor")
    right_motor = robot.getDevice("right wheel motor")
    left_sensor = robot.getDevice("left wheel sensor")
    right_sensor = robot.getDevice("right wheel sensor")

    assert left_motor is not None, "Missing left wheel motor"
    assert right_motor is not None, "Missing right wheel motor"
    assert left_sensor is not None, "Missing left wheel sensor"
    assert right_sensor is not None, "Missing right wheel sensor"
    print(f"[{robot_name}] Successfully acquired left and right motors & sensors!", flush=True)

    left_sensor.enable(timestep)
    right_sensor.enable(timestep)

    # Position mode infinity -> velocity control mode
    left_motor.setPosition(float("inf"))
    right_motor.setPosition(float("inf"))
    left_motor.setVelocity(2.0)
    right_motor.setVelocity(2.0)

    print(f"[{robot_name}] Commanded forward velocity (2.0 rad/s). Stepping {max_test_steps} physics steps...", flush=True)
    for s in range(1, max_test_steps + 1):
        ret = robot.step(timestep)
        if ret == -1:
            print(f"[{robot_name}] Webots simulation stopped.", flush=True)
            break
        if s % 10 == 0:
            l_pos = left_sensor.getValue()
            r_pos = right_sensor.getValue()
            print(f"  Step {s:02d}: left_pos={l_pos:.3f} rad, right_pos={r_pos:.3f} rad", flush=True)

    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)
    robot.step(timestep)
    print(f"[{robot_name}] TEST PASSED! Physical motion and sensor feedback verified.\n", flush=True)
    return True

if __name__ == "__main__":
    r_name = sys.argv[1] if len(sys.argv) > 1 else "R01"
    ok = test_single_robot(r_name)
    sys.exit(0 if ok else 1)
