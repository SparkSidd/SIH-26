import os
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
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
        learning_enabled: bool = False,
        learning_checkpoint: Optional[str] = None,
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

        # Learning-guided priority advisor (lazy loaded only if explicitly enabled)
        self.learning_policy: Optional[Any] = None
        self.learning_telemetry: Dict[str, Any] = {
            "enabled": learning_enabled,
            "is_fallback": True,
            "status": "Disabled" if not learning_enabled else "Uninitialized",
            "mean_latency_ms": 0.0,
            "last_latency_ms": 0.0,
        }
        if learning_enabled:
            from learning.config import LearningConfig
            from learning.priority_policy import PriorityPolicy

            ckpt_path = learning_checkpoint or os.path.join("learning", "checkpoints", "fine_tuned", "best_model.pt")
            config = LearningConfig(enabled=True, checkpoint_path=ckpt_path)
            self.learning_policy = PriorityPolicy(config=config, deterministic_engine=self.priority_engine)

        self.allocator_type = allocator_type
        self.fleet_allocator = FleetAwareTaskAllocator()
        self.nearest_allocator = BaselineNearestAllocator()

        # Track forced-reroute cooldowns (robot_id -> step_last_rerouted)
        self._reroute_cooldown: Dict[str, int] = {}
        self._REROUTE_COOLDOWN_STEPS = 12
        # Reroute deduplication signatures: robot_id -> (start_pos, goal_pos, frozenset(blocked_cells))
        self._last_reroute_signature: Dict[str, Tuple[Tuple[int, int], Tuple[int, int], frozenset]] = {}
        self._reroute_failures: Dict[str, int] = {}

        # Active waypoint paths set by reroute A* — PIBT follows these waypoint-by-waypoint
        self._active_waypoints: Dict[str, List[Tuple[int, int]]] = {}
        self._waypoint_assigned_step: Dict[str, int] = {}

        # Real telemetry: latest Wait-For Graph edges, deadlock cycles, and coordination mode
        self.last_wfg_edges: List[Dict[str, Any]] = []
        self.last_deadlock_cycles: List[List[str]] = []
        self.current_coordination_mode: CoordinationMode = CoordinationMode.LOCAL

        # Phase 7: Preferred corridor flow directions (soft traffic guidance)
        self.preferred_directions: Dict[Tuple[int, int], Tuple[int, int]] = {}
        self._preferred_directions_initialized: bool = False

    def _setup_topology_preferred_directions(self, is_walkable_fn: Callable[[Tuple[int, int]], bool]) -> None:
        """Assign soft flow directions according to warehouse topology (choke passages or cross-aisle highways)."""
        self.preferred_directions.clear()
        mid_x = self.map_width // 2
        # Check if central dividing wall exists (e.g. choke_point layout)
        is_choke_layout = not is_walkable_fn((mid_x, 9))

        if is_choke_layout:
            # Choke-point warehouse: choke passages are shared bidirectional conduits
            # Do not restrict flow, allowing AMRs to take the closest choke passage without vertical detours
            self.preferred_directions.clear()
        else:
            # Corridor-heavy warehouse: dual-lane paired cross-aisle highways
            for x in range(self.map_width):
                if abs(x - mid_x) <= 1:
                    continue
                self.preferred_directions[(x, 2)] = (1, 0)   # Top East-bound
                self.preferred_directions[(x, 1)] = (-1, 0)  # Top West-bound
                self.preferred_directions[(x, 9)] = (1, 0)   # Center East-bound
                self.preferred_directions[(x, 10)] = (-1, 0) # Center West-bound
                self.preferred_directions[(x, 17)] = (1, 0)  # Bottom East-bound
                self.preferred_directions[(x, 18)] = (-1, 0) # Bottom West-bound

    def _initialize_preferred_directions(self) -> None:
        """Initial default directions before topology check."""
        self._preferred_directions_initialized = False

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
            # Progress resets failure backoff
            self._reroute_failures[robot_id] = 0
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
        # 0. Initialize topology-aware highway directions once map is accessible
        if not self._preferred_directions_initialized and is_walkable_fn is not None:
            self._preferred_directions_initialized = True
            self._setup_topology_preferred_directions(is_walkable_fn)

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
                self._last_reroute_signature.pop(r_id, None)
                if self.event_bus:
                    self.event_bus.publish(Event(
                        event_type=EventType.TASK_REASSIGNED,
                        sim_time=sim_time,
                        step=step,
                        source="FleetCoordinator",
                        data={"robot_id": r_id, "task_id": task.id,
                              "reason": "Goal cell blocked — task requeued for reassignment"},
                    ))

        # 3. Allocate unassigned queued tasks with rolling lookahead handover
        pre_reserved_ids = {r.next_task_id for r in robots.values() if r.next_task_id}
        unassigned_tasks = [
            t for t in tasks.values()
            if t.state in (TaskState.CREATED, TaskState.QUEUED) and t.id not in pre_reserved_ids
        ]
        if unassigned_tasks:
            if self.allocator_type == "fleet_aware":
                assignments = self.fleet_allocator.allocate(
                    unassigned_tasks, robots, self.congestion_model, is_walkable_fn, all_tasks=tasks
                )
            else:
                assignments = self.nearest_allocator.allocate(unassigned_tasks, robots)

            for robot_id, task_id in assignments:
                robot = robots[robot_id]
                task = tasks[task_id]

                if robot.current_task_id is None:
                    # Immediate assignment for idle robot
                    robot.current_task_id = task.id
                    robot.target_position = task.pickup
                    robot.set_state(RobotState.TASK_ASSIGNED, "Assigned new task")
                    task.state = TaskState.ASSIGNED
                    task.assigned_robot_id = robot.id
                    task.assigned_time = sim_time
                    task.assignment_latency = sim_time - task.creation_time
                    if robot_id in self._active_waypoints:
                        del self._active_waypoints[robot_id]
                elif robot.next_task_id is None:
                    # Rolling handover pre-reservation (retains QUEUED state to preserve active task invariants)
                    robot.next_task_id = task.id

        # Station Clearance / Haven Retreat (Optimization Track I):
        # Clear IDLE AMRs off active pickup/dropoff stations into parking bays so they never block peers
        if self.allocator_type == "fleet_aware":
            stations = {
                (2, 2), (2, self.map_height // 2), (2, self.map_height - 3),
                (self.map_width - 3, 2), (self.map_width - 3, self.map_height // 2), (self.map_width - 3, self.map_height - 3),
            }
            for r_id, robot in robots.items():
                if robot.is_healthy and robot.state == RobotState.IDLE and robot.current_task_id is None:
                    if robot.position in stations:
                        chargers = [
                            (1, 1),
                            (1, self.map_height - 2),
                            (self.map_width - 2, 1),
                            (self.map_width - 2, self.map_height - 2),
                        ]
                        nearest = min(chargers, key=lambda c: abs(c[0] - robot.position[0]) + abs(c[1] - robot.position[1]))
                        robot.set_state(RobotState.GOING_TO_CHARGER, "Clearing station to parking bay")
                        robot.target_position = nearest

        # 4. Compute dynamic priorities and target goals
        priorities: Dict[str, float] = {}
        target_goals: Dict[str, Tuple[int, int]] = {}
        active_robot_ids: List[str] = []

        for r_id, robot in robots.items():
            if not robot.is_healthy or robot.state == RobotState.FAILED:
                self._active_waypoints.pop(r_id, None)
                self._waypoint_assigned_step.pop(r_id, None)
                self._last_reroute_signature.pop(r_id, None)
                continue

            active_robot_ids.append(r_id)
            active_task = tasks.get(robot.current_task_id) if robot.current_task_id else None
            cell_cong = self.congestion_model.get_cell_congestion(robot.position)
            priorities[r_id] = self.priority_engine.compute_robot_priority(robot, active_task, cell_cong)

            # Determine robot ultimate goal position (final destination)
            if robot.current_task_id and active_task:
                if active_task.state == TaskState.PICKED_UP:
                    ultimate_goal = active_task.dropoff
                elif active_task.state == TaskState.ASSIGNED:
                    if robot.position == active_task.pickup or (getattr(robot, "has_payload", False) and active_task.pickup_time):
                        ultimate_goal = active_task.dropoff
                    else:
                        ultimate_goal = active_task.pickup
                elif getattr(robot, "has_payload", False):
                    ultimate_goal = active_task.dropoff
                else:
                    ultimate_goal = active_task.pickup
            elif robot.state == RobotState.GOING_TO_CHARGER:
                chargers = [(1, 1), (1, 18), (23, 1), (23, 18)]
                ultimate_goal = min(chargers, key=lambda c: abs(c[0] - robot.position[0]) + abs(c[1] - robot.position[1]))
            else:
                ultimate_goal = robot.position

            # Clear waypoints if robot has already reached its ultimate destination or is idle
            if robot.position == ultimate_goal or robot.state in (RobotState.IDLE, RobotState.CHARGING):
                self._active_waypoints.pop(r_id, None)
                self._waypoint_assigned_step.pop(r_id, None)
                self._last_reroute_signature.pop(r_id, None)

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
                target_goals[r_id] = active_wp_path[0]
            else:
                target_goals[r_id] = ultimate_goal

        # 4b. Query learned priority policy if enabled
        if self.learning_policy and self.learning_policy.config.enabled:
            cong_map = {r_id: self.congestion_model.get_cell_congestion(robots[r_id].position) for r_id in active_robot_ids}
            learned_priorities, is_fallback, status = self.learning_policy.get_fleet_priorities(
                active_robot_ids=active_robot_ids,
                robots=robots,
                tasks=tasks,
                target_goals=target_goals,
                congestion_at_robots=cong_map,
                blocked_cells=blocked_cells,
            )
            for r_id in active_robot_ids:
                if r_id in learned_priorities:
                    priorities[r_id] = learned_priorities[r_id]
            self.learning_telemetry = {
                "enabled": True,
                "is_fallback": is_fallback,
                "status": status,
                "mean_latency_ms": round(self.learning_policy.inference_engine.mean_latency_ms, 3),
                "last_latency_ms": round(self.learning_policy.inference_engine.last_latency_ms, 3),
            }

        # 5. Detect and resolve deadlocks before planning
        wait_steps_map = {r_id: robots[r_id].wait_steps for r_id in active_robot_ids}
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
            current_positions=robot_positions,
            desired_targets=immediate_targets,
            wait_threshold=STUCK_THRESHOLD,
            robot_wait_steps=wait_steps_map,
        )

        # Record real WFG edges for telemetry
        edges = []
        pos_to_robot = {pos: rid for rid, pos in robot_positions.items()}
        for r_id, target in immediate_targets.items():
            if target != robot_positions.get(r_id) and target in pos_to_robot:
                occ = pos_to_robot[target]
                if occ != r_id:
                    edges.append({
                        "from": r_id,
                        "to": occ,
                        "cell": list(target),
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

        # Phase 8: Event-Triggered Adaptive Coordination Evaluation
        recent_conflicts = len(dl_report.cycles)
        has_deadlocks = dl_report.is_deadlocked
        is_aisle_blocked = len(blocked_cells) > 0
        norm_avg_cong = self.congestion_model.get_average_congestion_index()
        self.current_coordination_mode = self.adaptive_coordinator.evaluate_mode(
            average_congestion=norm_avg_cong / 100.0,
            recent_conflicts_count=recent_conflicts,
            is_aisle_blocked=is_aisle_blocked,
            has_deadlocks=has_deadlocks,
            sim_time=sim_time,
        )

        # 6. Strict Rerouting Guards (Phase 1 & Phase 9 Intelligent Rerouting)
        #    A reroute is ONLY permitted if:
        #    - robot is healthy and has an active task (or going to charger)
        #    - robot is not IDLE, CHARGING, FAILED, PICKING, or DELIVERING
        #    - ultimate_goal != robot.position
        #    - robot.wait_steps >= STUCK_THRESHOLD
        #    - not already following a waypoint path
        #    - dynamic cooldown has elapsed with backoff for unchanged scenarios
        for r_id in active_robot_ids:
            robot = robots[r_id]
            active_task = tasks.get(robot.current_task_id) if robot.current_task_id else None

            if not active_task and robot.state != RobotState.GOING_TO_CHARGER:
                self._active_waypoints.pop(r_id, None)
                self._waypoint_assigned_step.pop(r_id, None)
                self._last_reroute_signature.pop(r_id, None)
                continue

            if robot.state in (RobotState.CHARGING, RobotState.FAILED):
                continue

            if active_task:
                if active_task.state == TaskState.PICKED_UP:
                    ultimate_goal = active_task.dropoff
                elif active_task.state == TaskState.ASSIGNED:
                    if robot.position == active_task.pickup or (getattr(robot, "has_payload", False) and active_task.pickup_time):
                        ultimate_goal = active_task.dropoff
                    else:
                        ultimate_goal = active_task.pickup
                elif getattr(robot, "has_payload", False):
                    ultimate_goal = active_task.dropoff
                else:
                    ultimate_goal = active_task.pickup
            elif robot.state == RobotState.GOING_TO_CHARGER:
                chargers = [(1, 1), (1, 18), (23, 1), (23, 18)]
                ultimate_goal = min(chargers, key=lambda c: abs(c[0] - robot.position[0]) + abs(c[1] - robot.position[1]))
            else:
                continue

            if ultimate_goal == robot.position:
                self._active_waypoints.pop(r_id, None)
                self._waypoint_assigned_step.pop(r_id, None)
                self._last_reroute_signature.pop(r_id, None)
                continue

            if robot.wait_steps >= STUCK_THRESHOLD:
                self._active_waypoints.pop(r_id, None)
                self._waypoint_assigned_step.pop(r_id, None)

            last_rerouted = self._reroute_cooldown.get(r_id, -999)
            already_has_waypoints = r_id in self._active_waypoints
            consecutive_fails = self._reroute_failures.get(r_id, 0)
            dynamic_cooldown = min(40, self._REROUTE_COOLDOWN_STEPS * (1 + consecutive_fails))

            # If destination is occupied by a stationary peer, hold backoff so we don't spam replans
            dest_occupant = any(
                other.is_healthy and other.position == ultimate_goal 
                for oid, other in robots.items() if oid != r_id
            )
            if dest_occupant:
                dynamic_cooldown = max(dynamic_cooldown, 20)

            # Deduplication signature: (start_pos, goal_pos, blocked_cells)
            current_signature = (robot.position, ultimate_goal, frozenset(blocked_cells))
            last_sig = self._last_reroute_signature.get(r_id)

            reroute_allowed = (
                robot.wait_steps >= STUCK_THRESHOLD
                and ultimate_goal != robot.position
                and (step - last_rerouted) >= dynamic_cooldown
                and not already_has_waypoints
            )

            if reroute_allowed:
                self._last_reroute_signature[r_id] = current_signature

                # 1st attempt: treat other stationary robots as obstacles
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
                    congestion_model=self.congestion_model,
                    preferred_directions=self.preferred_directions,
                )

                # Fallback: plan using only static blocked cells
                if not reroute_result.is_success or len(reroute_result.path) <= 1:
                    reroute_result = self.reroute_astar.plan(
                        robot_id=r_id,
                        start_pos=robot.position,
                        goal_pos=ultimate_goal,
                        is_walkable_fn=is_walkable_fn,
                        blocked_cells=blocked_cells,
                        start_timestep=step,
                        congestion_model=self.congestion_model,
                        preferred_directions=self.preferred_directions,
                    )

                self._reroute_cooldown[r_id] = step

                if reroute_result.is_success and len(reroute_result.path) > 1:
                    self._active_waypoints[r_id] = list(reroute_result.path[1:])
                    self._waypoint_assigned_step[r_id] = step
                    robot.planned_path = list(reroute_result.path)
                    robot.set_state(RobotState.REPLANNING, "Forced A* reroute around blockage")
                    # Only reset wait_steps if the reroute genuinely found a multi-step detour path
                    if len(reroute_result.path) > 2:
                        robot.wait_steps = 0
                    self._reroute_failures[r_id] = 0
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
                    # Truly unreachable: increment failure backoff
                    self._reroute_failures[r_id] = consecutive_fails + 1
                    robot.set_state(RobotState.BLOCKED, "No path found — aisle fully blocked")
                    if self.event_bus and consecutive_fails == 0:
                        self.event_bus.publish(Event(
                            event_type=EventType.AISLE_BLOCKED,
                            sim_time=sim_time,
                            step=step,
                            source="FleetCoordinator",
                            data={"robot_id": r_id, "reason": "No A* path available"},
                        ))

        # 7. Multi-Agent Planning step (PIBT with congestion and execution awareness)
        effective_priorities = {
            r_id: priorities.get(r_id, 1.0) + getattr(robots[r_id], "priority_boost", 0.0)
            for r_id in active_robot_ids
        }
        next_cells = self.multi_agent_planner.plan_fleet_step(
            robot_ids=active_robot_ids,
            current_positions=robot_positions,
            target_goals=target_goals,
            priorities=effective_priorities,
            is_walkable_fn=is_walkable_fn,
            blocked_cells=blocked_cells,
            current_step=step,
            congestion_model=self.congestion_model,
            preferred_directions=self.preferred_directions,
        )

        # 8. Formulate candidate RobotActions with explicit waiting diagnostics
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

            # Set explicit waiting diagnostics for Robot Inspector (Phase 13)
            if action_type == ActionType.WAIT:
                if dl_report.is_deadlocked and any(r_id in c for c in dl_report.cycles):
                    robot.wait_reason = "Deadlock cycle resolution / yielding"
                elif target_goals.get(r_id) != robot.position:
                    robot.wait_reason = "Yielding to higher-priority peer"
                elif robot.state == RobotState.BLOCKED:
                    robot.wait_reason = "Corridor blocked by obstacle"
                elif robot.state == RobotState.IDLE:
                    robot.wait_reason = "Idle awaiting task"
                elif robot.state == RobotState.CHARGING:
                    robot.wait_reason = "Charging at station"

            # Update planned lookahead path for telemetry efficiently (only replan if goal changed)
            active_wp_path = self._active_waypoints.get(r_id)
            if active_wp_path and robot.state == RobotState.REPLANNING:
                pass
            else:
                goal = target_goals.get(r_id, robot.position)
                if goal != robot.position:
                    if not robot.planned_path or robot.planned_path[-1] != goal or robot.planned_path[0] != robot.position:
                        plan_res = self.multi_agent_planner.astar.plan(
                            robot_id=r_id,
                            start_pos=robot.position,
                            goal_pos=goal,
                            is_walkable_fn=is_walkable_fn,
                            blocked_cells=blocked_cells,
                            start_timestep=step,
                            congestion_model=self.congestion_model,
                            preferred_directions=self.preferred_directions,
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
