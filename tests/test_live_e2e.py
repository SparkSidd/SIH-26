"""Live End-to-End Integration and Verification Script."""

import json
import time
import urllib.request


def post(endpoint, data=None):
    req = urllib.request.Request(
        f"http://127.0.0.1:8080/api/control/{endpoint}",
        data=json.dumps(data or {}).encode("utf-8") if data is not None else b"{}",
        headers={"Content-Type": "application/json"}
    )
    return json.loads(urllib.request.urlopen(req).read().decode())


def get_state():
    return json.loads(urllib.request.urlopen("http://127.0.0.1:8080/api/state").read().decode())


def run_acceptance_sequence():
    print("==================================================================")
    print(" EXECUTING CRITICAL ACCEPTANCE TEST SUITE ON LIVE CONTROL CENTER")
    print("==================================================================")

    # 1. Test Pause & Step
    print("\n[Step 1] Testing Pause & Step Controls...")
    post("pause")
    s0 = get_state()
    print(f" -> Paused at Step: {s0['clock']['step']}, Time: {s0['clock']['sim_time']}s")

    post("step")
    s1 = get_state()
    print(f" -> Stepped to Step: {s1['clock']['step']}")
    assert s1['clock']['step'] == s0['clock']['step'] + 1, "Clock did not advance by 1 step!"

    # 2. Test Task Demand Surge
    print("\n[Step 2] Testing Demand Surge Injection (+5 Tasks)...")
    res_surge = post("task_surge")
    s2 = get_state()
    print(f" -> Added {res_surge.get('added_tasks')} tasks. Total tasks in world: {len(s2['tasks'])}")

    # 3. Test Corridor Blockage Injection
    print("\n[Step 3] Testing Aisle Blockage Injection at (7, 10)...")
    post("block_cell", {"x": 7, "y": 10})
    s3 = get_state()
    print(f" -> Blocked cells registered: {s3['warehouse']['blocked_cells']}")
    assert [7, 10] in s3['warehouse']['blocked_cells'], "Cell (7,10) not blocked!"

    # 4. Step 5 times to trigger and observe decentralized replanning
    print("\n[Step 4] Stepping 5 times to execute decentralized MAPF & safety filter...")
    for _ in range(5):
        post("step")
    s4 = get_state()
    print(f" -> Safety Interventions: {s4['kpis']['safety_interventions']}, Collisions: {s4['kpis']['total_collisions']}")
    assert s4['kpis']['total_collisions'] == 0, "Collision invariant violated!"

    # 5. Test Robot Failure Injection
    print("\n[Step 5] Testing Robot Failure Injection on AMR R2...")
    post("fail_robot", {"robot_id": "R2", "reason": "Drive motor hardware stall"})
    s5 = get_state()
    r2 = next(r for r in s5['robots'] if r['id'] == 'R2')
    print(f" -> AMR R2 State: {r2['state']}, Healthy: {r2['is_healthy']}, Reason: '{r2['failure_reason']}'")
    assert r2['is_healthy'] is False, "Robot R2 was not marked failed!"

    # 6. Test Wireless Network Degradation
    print("\n[Step 6] Testing Wireless Mesh Network Degradation (250ms latency, 30% loss)...")
    post("network", {"latency_ms": 250.0, "packet_loss_rate": 0.30})
    s6 = get_state()
    print(f" -> Latency: {s6['network']['latency_ms']}ms, Packet Loss: {s6['network']['packet_loss_rate']*100:.0f}%, Health: {s6['network']['health_pct']}%")

    # 7. Test Robot Recovery
    print("\n[Step 7] Testing Robot Recovery on AMR R2...")
    post("recover_robot", {"robot_id": "R2"})
    s7 = get_state()
    r2_rec = next(r for r in s7['robots'] if r['id'] == 'R2')
    print(f" -> AMR R2 Recovered State: {r2_rec['state']}, Healthy: {r2_rec['is_healthy']}")
    assert r2_rec['is_healthy'] is True, "Robot R2 was not recovered!"

    # 8. Unblock corridor
    print("\n[Step 8] Clearing Corridor Blockage...")
    post("unblock_cell", {"x": 7, "y": 10})
    s8 = get_state()
    print(f" -> Remaining blocked cells: {s8['warehouse']['blocked_cells']}")

    # 9. Test Resume
    print("\n[Step 9] Resuming live simulation execution...")
    post("play")
    time.sleep(1.2)
    s9 = get_state()
    print(f" -> Running at Step: {s9['clock']['step']}, Time: {s9['clock']['sim_time']}s, Completed Tasks: {s9['kpis']['tasks_completed']}")

    print("\n==================================================================")
    print(" [OK] ALL CRITICAL ACCEPTANCE TESTS COMPLETED SUCCESSFULLY!")
    print("==================================================================")


if __name__ == "__main__":
    run_acceptance_sequence()
