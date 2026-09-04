"""Master Fleet Coordinator integrating allocation, congestion, adaptive intensity, and MAPF."""

from typing import Callable, Dict, List, Optional, Set, Tuple
from coordination.allocator import FleetAwareTaskAllocator, BaselineNearestAllocator
from coordination.adaptive_coordination import AdaptiveCoordinator, CoordinationMode
from coordination.congestion import CongestionModel
from coordination.priority import PriorityEngine
from events.event import Event, EventType
from events.event_bus import EventBus
from execution.action import RobotAction, ActionType
from planning.deadlock import DeadlockDetector
from planning.multi_agent import MultiAgentPlanner
from planning.astar import SpaceTimeAStarPlanner
from simulator.robot import Robot, RobotState
from simulator.task import Task, TaskState

# Number of consecutive wait steps before a robot is considered "stuck" and triggers A* reroute
STUCK_THRESHOLD = 5
# Steps to hold a rerouted waypoint path before re-planning (prevents oscillation)
WAYPOINT_MAX_HOLD = 60


class FleetCoordinator:
    """Orchestrates decentralized task assignment, dynamic prioritization, and path coordination."""

    def __init__(
        self,
        map_width: int = 25,
        map_height: int = 20,
        planner_algorithm: str = "pibt",
        allocator_type: str = "fleet_aware",
        event_bus: Optional[EventBus] = None,
    ):
        self.map_width = map_width
        self.map_height = map_height
        self.congestion_model = CongestionModel(width=map_width, height=map_height)
        self.priority_engine = PriorityEngine()
        self.adaptive_coordinator = AdaptiveCoordinator()
        self.multi_agent_planner = MultiAgentPlanner(algorithm=planner_algorithm)
        self.deadlock_detector = DeadlockDetector()
        # A high-horizon A* dedicated to rerouting stuck robots
        self.reroute_astar = SpaceTimeAStarPlanner(heuristic_type="manhattan", max_horizon=200, timeout_ms=150.0)
        self.event_bus = event_bus

        self.allocator_type = allocator_type
        self.fleet_allocator = FleetAwareTaskAllocator()
        self.nearest_allocator = BaselineNearestAllocator()

        # Track forced-reroute cooldowns (robot_id -> step_last_rerouted)
        self._reroute_cooldown: Dict[str, int] = {}
        self._REROUTE_COOLDOWN_STEPS = 12

        # Active waypoint paths set by reroute A* — PIBT follows these waypoint-by-waypoint
        # robot_id -> remaining waypoints (list of positions to follow in order)
        self._active_waypoints: Dict[str, List[Tuple[int, int]]] = {}
        # Track when the waypoint path was assigned (to expire stale paths)
        self._waypoint_assigned_step: Dict[str, int] = {}

        # Real telemetry: latest Wait-For Graph edges and deadlock cycles
        self.last_wfg_edges: List[Dict[str, Any]] = []
        self.last_deadlock_cycles: List[List[str]] = []

    def _invalidate_waypoints_if_blocked(
        self, robot_id: str, blocked_cells: Set[Tuple[int, int]]
    ) -> None:
        """Clear waypoint path if any remaining waypoint is now blocked."""
        path = self._active_waypoints.get(robot_id)
        if path:
            if any(wp in blocked_cells for wp in path):
                del self._active_waypoints[robot_id]
                if robot_id in self._waypoint_assigned_step:
                    del self._waypoint_assigned_step[robot_id]

    def _advance_waypoints(self, robot_id: str, current_pos: Tuple[int, int]) -> None:
        """Pop waypoints that the robot has already reached."""
        path = self._active_waypoints.get(robot_id)
        if not path:
            return
        while path and path[0] == current_pos:
            path.pop(0)
        if not path:
            del self._active_waypoints[robot_id]
            if robot_id in self._waypoint_assigned_step:
                del self._waypoint_assigned_step[robot_id]

    def step_coordinate(
        self,
        robots: Dict[str, Robot],
        tasks: Dict[str, Task],
        is_walkable_fn: Callable[[Tuple[int, int]], bool],
        blocked_cells: Set[Tuple[int, int]],
        sim_time: float,
        step: int,
    ) -> Dict[str, RobotAction]:
        """Execute step coordination and return proposed actions for all robots."""
        # 1. Update congestion heatmap
        robot_positions = {r_id: r.position for r_id, r in robots.items()}
        robot_paths = {r_id: r.planned_path for r_id, r in robots.items() if r.planned_path}
        self.congestion_model.update_tick(robot_positions, robot_paths)

        # 2. Propagate known blocked cells to every robot's local world model
        for robot in robots.values():
            if robot.is_healthy and robot.local_world_model is not None:
                for cell in blocked_cells:
                    robot.local_world_model.known_blocked_cells.add(cell)

        # 2b. Reclaim tasks whose pickup/dropoff has become blocked (station now unreachable)
        for r_id, robot in robots.items():
            if not robot.is_healthy or not robot.current_task_id:
                continue
            task = tasks.get(robot.current_task_id)
            if not task or task.state in (TaskState.DELIVERED, TaskState.QUEUED, TaskState.CREATED):
                continue
            # Determine which goal this robot needs to reach
            if task.state == TaskState.ASSIGNED:
                current_goal = task.pickup
            elif task.state == TaskState.PICKED_UP:
                current_goal = task.dropoff
            else:
                continue
            # If the goal cell itself is in blocked_cells, reclaim the task
            if current_goal in blocked_cells:
                task.state = TaskState.QUEUED
                task.assigned_robot_id = None
                task.priority += 2.0  # Boost priority so it gets re-assigned quickly
                robot.current_task_id = None
                robot.target_position = None
                robot.set_state(RobotState.IDLE, "Task reclaimed — goal cell blocked")
                robot.wait_steps = 0
                robot.priority_boost = 0.0
                # Clear any stale waypoints
                self._active_waypoints.pop(r_id, None)
                self._waypoint_assigned_step.pop(r_id, None)
                if self.event_bus:
                    self.event_bus.publish(Event(
                        event_type=EventType.TASK_REASSIGNED,
                        sim_time=sim_time,
                        step=step,
                        source="FleetCoordinator",
                        data={"robot_id": r_id, "task_id": task.id,
                              "reason": "Goal cell blocked — task requeued for reassignment"},
                    ))

        # 3. Allocate unassigned queued tasks
        unassigned_tasks = [t for t in tasks.values() if t.state in (TaskState.CREATED, TaskState.QUEUED)]
        if unassigned_tasks:
            if self.allocator_type == "fleet_aware":
                assignments = self.fleet_allocator.allocate(
                    unassigned_tasks, robots, self.congestion_model, is_walkable_fn
                )
            else:
                assignments = self.nearest_allocator.allocate(unassigned_tasks, robots)

            for robot_id, task_id in assignments:
                robot = robots[robot_id]
                task = tasks[task_id]
                robot.current_task_id = task.id
                robot.target_position = task.pickup
                robot.set_state(RobotState.TASK_ASSIGNED, "Assigned new task")
                task.state = TaskState.ASSIGNED
                task.assigned_robot_id = robot.id
                task.assigned_time = sim_time
                # New task assignment invalidates old waypoints
                if robot_id in self._active_waypoints:
                    del self._active_waypoints[robot_id]

        # 4. Compute dynamic priorities and target goals
        priorities: Dict[str, float] = {}
        target_goals: Dict[str, Tuple[int, int]] = {}
        active_robot_ids: List[str] = []

        for r_id, robot in robots.items():
            if not robot.is_healthy or robot.state == RobotState.FAILED:
                self._active_waypoints.pop(r_id, None)
                self._waypoint_assigned_step.pop(r_id, None)
                continue

            active_robot_ids.append(r_id)
            active_task = tasks.get(robot.current_task_id) if robot.current_task_id else None
            cell_cong = self.congestion_model.get_cell_congestion(robot.position)
            priorities[r_id] = self.priority_engine.compute_robot_priority(robot, active_task, cell_cong)

            # Determine robot ultimate goal position (final destination)
            if robot.current_task_id and active_task:
                if active_task.state == TaskState.PICKED_UP or getattr(robot, "has_payload", False):
                    ultimate_goal = active_task.dropoff
                else:
                    ultimate_goal = active_task.pickup
            elif robot.battery.is_low:
                ultimate_goal = (1, 1)
            else:
                ultimate_goal = robot.position

            # Advance waypoints if robot has reached a waypoint
            self._advance_waypoints(r_id, robot.position)
            # Invalidate waypoints if any are now blocked
            self._invalidate_waypoints_if_blocked(r_id, blocked_cells)
            # Expire stale waypoint paths
            assigned_step = self._waypoint_assigned_step.get(r_id, step)
            if (step - assigned_step) > WAYPOINT_MAX_HOLD:
                self._active_waypoints.pop(r_id, None)
                self._waypoint_assigned_step.pop(r_id, None)

            # If there's an active rerouted waypoint path, follow the next waypoint
            active_wp_path = self._active_waypoints.get(r_id)
            if active_wp_path:
                # Use next waypoint as immediate PIBT target (waypoint following)
                target_goals[r_id] = active_wp_path[0]
            else:
                target_goals[r_id] = ultimate_goal

        # 5. Detect and resolve deadlocks before planning
        wait_steps_map = {r_id: robots[r_id].wait_steps for r_id in active_robot_ids}
        # Compute immediate 1-step targets for the Wait-For-Graph
        immediate_targets = {}
        for r_id in active_robot_ids:
            r = robots[r_id]
            wp_path = self._active_waypoints.get(r_id)
            if wp_path:
                immediate_targets[r_id] = wp_path[0]
            elif len(r.planned_path) > 1 and r.planned_path[0] == r.position:
                immediate_targets[r_id] = r.planned_path[1]
            else:
                goal = target_goals.get(r_id, r.position)
                if goal == r.position:
                    immediate_targets[r_id] = r.position
                else:
                    nbrs = [
                        (r.position[0] + 1, r.position[1]),
                        (r.position[0] - 1, r.position[1]),
                        (r.position[0], r.position[1] + 1),
                        (r.position[0], r.position[1] - 1),
                    ]
                    valid = [n for n in nbrs if is_walkable_fn(n) and n not in blocked_cells]
                    if valid:
                        valid.sort(key=lambda n: abs(n[0] - goal[0]) + abs(n[1] - goal[1]))
                        immediate_targets[r_id] = valid[0]
                    else:
                        immediate_targets[r_id] = r.position

        dl_report = self.deadlock_detector.detect_deadlocks(
            current_positions={r_id: robots[r_id].position for r_id in active_robot_ids},
            desired_targets=immediate_targets,
            wait_threshold=STUCK_THRESHOLD,
            robot_wait_steps=wait_steps_map,
        )

        # Record real Wait-For Graph relationships for live digital twin telemetry
        pos_to_r = {robots[r_id].position: r_id for r_id in active_robot_ids}
        edges = []
        for r_id in active_robot_ids:
            tgt = immediate_targets.get(r_id)
            if tgt and tgt != robots[r_id].position and tgt in pos_to_r:
                occ = pos_to_r[tgt]
                if occ != r_id:
                    edges.append({
                        "from_robot": r_id,
                        "to_robot": occ,
                        "target_cell": list(tgt),
                        "wait_steps": wait_steps_map.get(r_id, 0),
                        "is_cycle": any(r_id in c and occ in c for c in dl_report.cycles),
                    })
        self.last_wfg_edges = edges
        self.last_deadlock_cycles = dl_report.cycles

        if dl_report.is_deadlocked:
            for cycle in dl_report.cycles:
                if cycle:
                    breaker = cycle[0]
                    if breaker in robots:
                        robots[breaker].priority_boost += 5.0
                        robots[breaker].set_state(RobotState.REPLANNING, "Deadlock break - priority boost")
                        if self.event_bus:
                            self.event_bus.publish(Event(
                                event_type=EventType.DEADLOCK_DETECTED,
                                sim_time=sim_time,
                                step=step,
                                source="DeadlockDetector",
                                data={"cycle": cycle, "breaker": breaker},
                            ))

        # 6. For stuck robots: force a full A* reroute to bypass blocked aisles
        #    A robot is "stuck" if it has waited >= STUCK_THRESHOLD consecutive steps
        #    AND has a final goal different from its current position
        for r_id in active_robot_ids:
            robot = robots[r_id]
            active_task = tasks.get(robot.current_task_id) if robot.current_task_id else None

            # Get ultimate goal (final destination, not the waypoint step)
            if active_task:
                if active_task.state == TaskState.PICKED_UP or getattr(robot, "has_payload", False):
                    ultimate_goal = active_task.dropoff
                else:
                    ultimate_goal = active_task.pickup
            elif robot.battery.is_low:
                ultimate_goal = (1, 1)
            else:
                ultimate_goal = robot.position

            # If robot is stuck for >= STUCK_THRESHOLD, clear stale waypoints to enable fresh replanning
            if robot.wait_steps >= STUCK_THRESHOLD:
                self._active_waypoints.pop(r_id, None)
                self._waypoint_assigned_step.pop(r_id, None)

            last_rerouted = self._reroute_cooldown.get(r_id, -999)
            already_has_waypoints = r_id in self._active_waypoints

            if (
                robot.wait_steps >= STUCK_THRESHOLD
                and ultimate_goal != robot.position
                and (step - last_rerouted) >= self._REROUTE_COOLDOWN_STEPS
                and not already_has_waypoints
            ):
                # 1st attempt: treat other stationary/stuck robots as obstacles to find a clear detour
                reroute_blocked = set(blocked_cells)
                for other_id, other_robot in robots.items():
                    if other_id != r_id and other_robot.is_healthy:
                        if other_robot.position != ultimate_goal:
                            reroute_blocked.add(other_robot.position)

                reroute_result = self.reroute_astar.plan(
                    robot_id=r_id,
                    start_pos=robot.position,
                    goal_pos=ultimate_goal,
                    is_walkable_fn=is_walkable_fn,
                    blocked_cells=reroute_blocked,
                    start_timestep=step,
                )

                # Fallback: if no path exists routing around other robots, plan using only static blocked_cells
                if not reroute_result.is_success or len(reroute_result.path) <= 1:
                    reroute_result = self.reroute_astar.plan(
                        robot_id=r_id,
                        start_pos=robot.position,
                        goal_pos=ultimate_goal,
                        is_walkable_fn=is_walkable_fn,
                        blocked_cells=blocked_cells,
                        start_timestep=step,
                    )

                self._reroute_cooldown[r_id] = step

                if reroute_result.is_success and len(reroute_result.path) > 1:
                    # Store FULL rerouted path as active waypoints (skip current pos at index 0)
                    self._active_waypoints[r_id] = list(reroute_result.path[1:])
                    self._waypoint_assigned_step[r_id] = step
                    # Update planned_path for telemetry display (full path including current pos)
                    robot.planned_path = list(reroute_result.path)
                    robot.set_state(RobotState.REPLANNING, "Forced A* reroute around blockage")
                    robot.wait_steps = 0  # Reset stuck counter
                    # Override PIBT target to first waypoint
                    target_goals[r_id] = reroute_result.path[1]
                    if self.event_bus:
                        self.event_bus.publish(Event(
                            event_type=EventType.REROUTE,
                            sim_time=sim_time,
                            step=step,
                            source="FleetCoordinator",
                            data={
                                "robot_id": r_id,
                                "new_path_length": len(reroute_result.path),
                                "reason": "Forced A* reroute after stuck threshold",
                                "next_waypoint": list(reroute_result.path[1]),
                                "final_goal": list(ultimate_goal),
                            },
                        ))
                else:
                    # Truly unreachable — mark BLOCKED so UI shows it correctly
                    robot.set_state(RobotState.BLOCKED, "No path found — aisle fully blocked")
                    if self.event_bus:
                        self.event_bus.publish(Event(
                            event_type=EventType.AISLE_BLOCKED,
                            sim_time=sim_time,
                            step=step,
                            source="FleetCoordinator",
                            data={"robot_id": r_id, "reason": "No A* path available"},
                        ))

        # 7. Multi-Agent Planning step (PIBT or Space-Time A*)
        next_cells = self.multi_agent_planner.plan_fleet_step(
            robot_ids=active_robot_ids,
            current_positions=robot_positions,
            target_goals=target_goals,
            priorities=priorities,
            is_walkable_fn=is_walkable_fn,
            blocked_cells=blocked_cells,
            current_step=step,
        )

        # 8. Formulate candidate RobotActions
        candidate_actions: Dict[str, RobotAction] = {}
        for r_id in list(robots.keys()):
            robot = robots[r_id]
            if not robot.is_healthy or robot.state == RobotState.FAILED:
                candidate_actions[r_id] = RobotAction(
                    action_type=ActionType.ESTOP,
                    target_cell=robot.position,
                    reason="Robot failed",
                )
                continue

            next_pos = next_cells.get(r_id, robot.position)
            action_type = ActionType.MOVE if next_pos != robot.position else ActionType.WAIT

            # Update planned lookahead path for telemetry
            # Priority: active rerouted waypoint path > fresh A* replan > next PIBT step
            active_wp_path = self._active_waypoints.get(r_id)
            if active_wp_path and robot.state == RobotState.REPLANNING:
                # Keep the rerouted planned path (already set in reroute block above)
                pass
            else:
                goal = target_goals.get(r_id, robot.position)
                if goal != robot.position:
                    plan_res = self.multi_agent_planner.astar.plan(
                        robot_id=r_id,
                        start_pos=robot.position,
                        goal_pos=goal,
                        is_walkable_fn=is_walkable_fn,
                        blocked_cells=blocked_cells,
                        start_timestep=step,
                    )
                    if plan_res.is_success and len(plan_res.path) > 1:
                        robot.planned_path = plan_res.path
                    else:
                        robot.planned_path = [robot.position, next_pos]
                else:
                    robot.planned_path = [robot.position]

            candidate_actions[r_id] = RobotAction(
                action_type=action_type,
                target_cell=next_pos,
                task_id=robot.current_task_id,
            )

        return candidate_actions
