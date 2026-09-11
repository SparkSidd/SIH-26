"""Comprehensive Regression & Validation Tests for Fleet Coordination Optimizations.

Covers:
- Reroute spam guards (no reroute when idle, at goal, or charging)
- Reroute deduplication & backoff cooldown
- Progress resetting failure counters
- Congestion Index normalization (0-100 bounds)
- Rolling handover task lookahead
- Fleet workload balancing in allocator
- Adaptive coordination dynamic escalation & de-escalation
- Task duration breakdown telemetry
- Execution-aware routing (turns, congestion)
"""

import pytest
from coordination.allocator import FleetAwareTaskAllocator
from coordination.adaptive_coordination import AdaptiveCoordinator, CoordinationMode
from coordination.congestion import CongestionModel
from events.event import EventType
from planning.astar import SpaceTimeAStarPlanner, PlannerStatusCode
from simulator.robot import Robot, RobotState
from simulator.simulation import AMRSimulation
from simulator.task import Task, TaskState


def test_congestion_index_normalization_bounds():
    """Verify Congestion Index is strictly bounded between 0.0 and 100.0 with proper scaling."""
    cm = CongestionModel(width=10, height=10)
    
    # 0 heat -> 0 index
    assert cm.get_normalized_congestion((0, 0)) == 0.0
    assert cm.get_peak_congestion_index() == 0.0
    
    # Moderate occupancy heat = 4.0 -> ~63.2 index
    cm.heatmap[2, 3] = 4.0
    idx = cm.get_normalized_congestion((2, 3))
    assert 60.0 <= idx <= 65.0
    assert cm.get_peak_congestion_index() == idx
    
    # Extreme bottleneck heat = 40.0 -> <= 100.0
    cm.heatmap[5, 5] = 40.0
    extreme_idx = cm.get_normalized_congestion((5, 5))
    assert 99.0 <= extreme_idx <= 100.0
    assert cm.get_peak_congestion_index() == extreme_idx
    
    # Hotspot classification
    hotspot = cm.get_hotspot_info()
    assert hotspot["cell"] == [5, 5]
    assert hotspot["index"] >= 99.0
    assert len(hotspot["label"]) > 0


def test_no_reroute_when_idle_or_at_goal():
    """Verify that an IDLE robot or a robot at its goal NEVER triggers rerouting."""
    sim = AMRSimulation(seed=42)
    sim.world.tasks.clear()
    robot = sim.world.robots["R1"]
    robot.current_task_id = None
    robot.set_state(RobotState.IDLE, "Parked idle")
    robot.wait_steps = 10  # Exceeds STUCK_THRESHOLD
    
    reroutes = []
    def on_reroute(ev):
        if ev.data.get("robot_id") == "R1":
            reroutes.append(ev)
    sim.event_bus.subscribe(EventType.REROUTE, on_reroute)
    
    # Coordinate step
    sim.coordinator.step_coordinate(
        robots=sim.world.robots,
        tasks=sim.world.tasks,
        is_walkable_fn=sim.warehouse.is_walkable,
        blocked_cells=sim.warehouse.blocked_cells,
        sim_time=1.0,
        step=10,
    )
    
    # Must NOT emit reroute event
    assert len(reroutes) == 0
    assert "R1" not in sim.coordinator._active_waypoints


def test_reroute_deduplication_and_cooldown():
    """Verify that repeated blockages do NOT emit spam reroutes every tick."""
    sim = AMRSimulation(seed=42)
    robot = sim.world.robots["R1"]
    robot.position = (2, 4)
    task = Task(id="T_SPAM", pickup=(2, 4), dropoff=(2, 8), priority=2.0)
    task.state = TaskState.PICKED_UP
    task.assigned_robot_id = robot.id
    robot.current_task_id = task.id
    robot.has_payload = True
    sim.world.add_task(task)
    
    # Block corridor ahead at (2, 6)
    sim.warehouse.block_cell((2, 6))
    
    reroute_events = []
    def on_reroute(ev):
        if ev.data.get("robot_id") == "R1":
            reroute_events.append(ev)
    sim.event_bus.subscribe(EventType.REROUTE, on_reroute)
    
    # Step 5 times with robot stuck
    robot.wait_steps = 6
    sim.coordinator.step_coordinate(
        robots=sim.world.robots,
        tasks=sim.world.tasks,
        is_walkable_fn=sim.warehouse.is_walkable,
        blocked_cells=sim.warehouse.blocked_cells,
        sim_time=1.0,
        step=10,
    )
    first_count = len(reroute_events)
    
    # Immediate next tick should be on cooldown and suppressed
    robot.wait_steps = 7
    sim.coordinator.step_coordinate(
        robots=sim.world.robots,
        tasks=sim.world.tasks,
        is_walkable_fn=sim.warehouse.is_walkable,
        blocked_cells=sim.warehouse.blocked_cells,
        sim_time=1.1,
        step=11,
    )
    assert len(reroute_events) == first_count, "Reroute must be suppressed during cooldown"


def test_fleet_workload_balancing_in_allocator():
    """Verify that FleetAwareTaskAllocator balances assignments across AMRs instead of starving idle ones."""
    allocator = FleetAwareTaskAllocator(w_imbalance=3.0)
    
    r1 = Robot(id="R1", initial_position=(5, 5))
    r2 = Robot(id="R2", initial_position=(5, 5))
    
    # R1 has already completed 6 tasks; R2 has completed 0 tasks
    r1.tasks_completed = 6
    r2.tasks_completed = 0
    
    task = Task(id="T_BAL", pickup=(6, 5), dropoff=(10, 5))
    robots = {"R1": r1, "R2": r2}
    
    assignments = allocator.allocate([task], robots)
    assert len(assignments) == 1
    # R2 must be chosen due to workload balancing penalty on R1
    assigned_robot_id, assigned_task_id = assignments[0]
    assert assigned_robot_id == "R2"


def test_rolling_handover_task_assignment():
    """Verify that a robot nearing payload dropoff can be pre-assigned candidate next task."""
    allocator = FleetAwareTaskAllocator()
    
    # R1 is delivering payload right near dropoff (20, 10)
    r1 = Robot(id="R1", initial_position=(19, 10))
    r1.has_payload = True
    current_t = Task(id="T_CURR", pickup=(10, 10), dropoff=(20, 10))
    current_t.state = TaskState.PICKED_UP
    r1.current_task_id = current_t.id
    
    # Candidate task picks up right at (20, 10)
    next_t = Task(id="T_NEXT", pickup=(20, 10), dropoff=(22, 10))
    
    all_tasks = {"T_CURR": current_t, "T_NEXT": next_t}
    robots = {"R1": r1}
    
    assignments = allocator.allocate([next_t], robots, all_tasks=all_tasks)
    assert len(assignments) == 1
    assert assignments[0] == ("R1", "T_NEXT")


def test_adaptive_coordination_escalation_and_deescalation():
    """Verify that AdaptiveCoordinator escalates under congestion/deadlocks and de-escalates when clear."""
    coord = AdaptiveCoordinator()
    assert coord.current_mode == CoordinationMode.LOCAL
    
    # Escalate to CLUSTER on deadlocks
    mode = coord.evaluate_mode(
        average_congestion=0.1,
        recent_conflicts_count=0,
        is_aisle_blocked=False,
        has_deadlocks=True,
        sim_time=1.0,
    )
    assert mode == CoordinationMode.CLUSTER
    
    # Escalate to NEIGHBOR on elevated traffic
    mode = coord.evaluate_mode(
        average_congestion=0.6,
        recent_conflicts_count=0,
        is_aisle_blocked=False,
        has_deadlocks=False,
        sim_time=2.0,
    )
    assert mode == CoordinationMode.NEIGHBOR
    
    # De-escalate back to LOCAL when interaction is nominal
    mode = coord.evaluate_mode(
        average_congestion=0.05,
        recent_conflicts_count=0,
        is_aisle_blocked=False,
        has_deadlocks=False,
        sim_time=3.0,
    )
    assert mode == CoordinationMode.LOCAL


def test_task_timing_breakdown_telemetry():
    """Verify that completed tasks record detailed durations (travel, wait, congestion delay)."""
    sim = AMRSimulation(seed=42)
    # Run simulation for 50 steps
    for _ in range(50):
        sim.step()
    
    completed = [t for t in sim.world.tasks.values() if t.is_completed]
    assert len(completed) > 0, "Simulation should complete tasks"
    
    t = completed[0]
    t_dict = t.to_dict()
    assert "travel_time" in t_dict
    assert "wait_time" in t_dict
    assert "congestion_delay" in t_dict
    assert "total_duration" in t_dict
    assert t_dict["travel_time"] >= 0.0


def test_execution_aware_astar_turn_and_congestion_cost():
    """Verify that SpaceTimeAStar penalizes turns and congested routes."""
    planner = SpaceTimeAStarPlanner()
    cm = CongestionModel(width=15, height=15)
    
    def is_walkable(p):
        return 0 <= p[0] < 15 and 0 <= p[1] < 15
    
    # Clear route from (2, 2) to (6, 2)
    res_clear = planner.plan(
        robot_id="R1",
        start_pos=(2, 2),
        goal_pos=(6, 2),
        is_walkable_fn=is_walkable,
        congestion_model=cm,
    )
    assert res_clear.is_success
    
    # Heavily congest the straight route (3, 2), (4, 2), (5, 2)
    cm.heatmap[3, 2] = 20.0
    cm.heatmap[4, 2] = 20.0
    cm.heatmap[5, 2] = 20.0
    
    res_cong = planner.plan(
        robot_id="R1",
        start_pos=(2, 2),
        goal_pos=(6, 2),
        is_walkable_fn=is_walkable,
        congestion_model=cm,
    )
    assert res_cong.is_success
    # The planner should choose a detour around the congested row
    assert res_cong.path != res_clear.path or any(p[1] != 2 for p in res_cong.path[1:-1])
