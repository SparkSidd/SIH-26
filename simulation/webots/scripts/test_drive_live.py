import os
import sys
import time

if "WEBOTS_HOME" not in os.environ:
    os.environ["WEBOTS_HOME"] = "/usr/local/webots"
sys.path.append("/usr/local/webots/lib/controller/python")

from controller import Robot

os.environ["WEBOTS_CONTROLLER_URL"] = "ipc://1234/R01"
os.environ["WEBOTS_ROBOT_NAME"] = "R01"

print("Connecting to R01...", flush=True)
try:
    robot = Robot()
    ts = int(robot.getBasicTimeStep())
    lm = robot.getDevice("left wheel motor")
    rm = robot.getDevice("right wheel motor")
    lm.setPosition(float("inf"))
    rm.setPosition(float("inf"))
    lm.setVelocity(2.0)
    rm.setVelocity(2.0)
    print("Motors commanded! Stepping 50 steps...", flush=True)
    for _ in range(50):
        robot.step(ts)
        time.sleep(0.02)
    lm.setVelocity(0.0)
    rm.setVelocity(0.0)
    robot.step(ts)
    print("Done moving R01!", flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)
