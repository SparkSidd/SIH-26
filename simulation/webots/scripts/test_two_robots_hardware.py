#!/usr/bin/env python3
"""
test_two_robots_hardware.py — Parallel Execution for 2 AMRs in Webots.

Launches two processes (one for R01, one for R02) to verify parallel extern
controller connectivity, motor drive, and wheel sensor feedback.
"""

import multiprocessing
import os
import sys
import time

if "WEBOTS_HOME" not in os.environ and os.path.isdir("/usr/local/webots"):
    os.environ["WEBOTS_HOME"] = "/usr/local/webots"
webots_home = os.environ.get("WEBOTS_HOME", "/usr/local/webots")
py_controller = os.path.join(webots_home, "lib", "controller", "python")
if os.path.isdir(py_controller) and py_controller not in sys.path:
    sys.path.append(py_controller)

from simulation.webots.scripts.test_webots_hardware import test_single_robot


def worker(robot_name: str, queue: multiprocessing.Queue):
    os.environ["WEBOTS_CONTROLLER_URL"] = f"ipc://1234/{robot_name}"
    success = test_single_robot(robot_name=robot_name, max_test_steps=40)
    queue.put((robot_name, success))


def main():
    print("=" * 60, flush=True)
    print("  SIH26123 — WEBOTS HARDWARE TEST B: 2 AMRs (R01 & R02)", flush=True)
    print("=" * 60, flush=True)

    queue = multiprocessing.Queue()
    p1 = multiprocessing.Process(target=worker, args=("R01", queue))
    p2 = multiprocessing.Process(target=worker, args=("R02", queue))

    p1.start()
    p2.start()

    p1.join(timeout=30)
    p2.join(timeout=30)

    results = {}
    while not queue.empty():
        r_name, status = queue.get()
        results[r_name] = status

    print(f"\n[TEST B RESULTS] Robot statuses: {results}", flush=True)
    assert results.get("R01") is True, "R01 test failed!"
    assert results.get("R02") is True, "R02 test failed!"
    print("\n[PASS] TEST B: Both R01 and R02 successfully moved and read sensors in parallel!\n", flush=True)


if __name__ == "__main__":
    main()
