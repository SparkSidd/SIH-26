"""Core Simulation Orchestrator strictly enforcing the 16-step tick contract."""

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import numpy as np

from coordination.coordinator import FleetCoordinator
from events.event import Event, EventType
from events.event_bus import EventBus
from execution.action import RobotAction, ActionType
from execution.executor import ActionExecutor
from metrics.metrics import FleetMetrics
from metrics.resource_monitor import EdgeResourceMonitor
from network.communication import CommunicationMesh
from network.message import MessageType
from network.network_conditions import NetworkConditions
from network.topology import NetworkTopology
from planning.deadlock import DeadlockDetector
import time
from replay.recorder import SimulationRecorder
from safety.collision_checker import CollisionChecker
from safety.supervisor import SafetySupervisor
from simulator.clock import SimulationClock
from simulator.obstacle import Obstacle, ObstacleType
from simulator.robot import Robot, RobotState, RobotGeometry, RobotBattery
from simulator.sensors import RobotSensorSuite, SensorNoiseMode
from simulator.task import Task, TaskState, TaskGenerator
from simulator.warehouse import Warehouse, CellType
from simulator.world import SimulatorWorld
from world_model.local_world import LocalWorldModel


class AMRSimulation:
    """Master AMR Fleet Simulator implementing the strict 16-step tick contract."""

    def __init__(
        self,
        warehouse: Optional[Warehouse] = None,
        robot_count: int = 6,
        planner_algorithm: str = "pibt",
        allocator_type: str = "fleet_aware",
        timestep: float = 0.1,
        seed: int = 42,
        realtime_factor: float = 1.0,
        enable_recorder: bool = False,
        learning_enabled: bool = False,
        learning_checkpoint: Optional[str] = None,
    ):
        self.seed = seed
        self.timestep = timestep
        self.clock = SimulationClock(timestep=timestep, realtime_factor=realtime_factor)
        self.event_bus = EventBus()
        self.warehouse = warehouse or Warehouse(layout_type="corridor_heavy")
        self.world = SimulatorWorld(self.warehouse)
        
        # Perception & Network subsystems
        self.sensor_suite = RobotSensorSuite(range_cells=5.0, seed=seed)
        self.comm_mesh = CommunicationMesh(
            conditions=NetworkConditions(),
            topology=NetworkTopology(),
            seed=seed,
        )
        
        # Coordinator, Safety & Execution layers
        self.coordinator = FleetCoordinator(
            map_width=self.warehouse.width,
            map_height=self.warehouse.height,
            planner_algorithm=planner_algorithm,
            allocator_type=allocator_type,
            event_bus=self.event_bus,
            learning_enabled=learning_enabled,
            learning_checkpoint=learning_checkpoint,
        )
        self.safety_supervisor = SafetySupervisor(event_bus=self.event_bus)
        self.executor = ActionExecutor()
        
        # Metrics & Profiling
        self.metrics = FleetMetrics()
        self.resource_monitor = EdgeResourceMonitor()
        self.recorder = SimulationRecorder() if enable_recorder else None
        
        # Task stream
        self.task_generator = TaskGenerator(
            pickup_stations=self.warehouse.pickup_stations,
            dropoff_stations=self.warehouse.dropoff_stations,
            mode="poisson",
            arrival_rate=0.25,
            seed=seed,
        )

        # Dynamic disturbance schedules
        self.scheduled_blockages: List[Tuple[int, Tuple[int, int]]] = []  # (step, cell)
        self.scheduled_failures: List[Tuple[int, str, str]] = []           # (step, robot_id, reason)

        # Initialize robots and seed initial fleet tasks
        self._init_robots(robot_count)
        self._init_tasks(robot_count + 2)

    def _init_tasks(self, count: int) -> None:
        """Seed initial tasks so all robots in fleet are active immediately."""
        for _ in range(count):
            task = self.task_generator._create_random_task(current_time=0.0)
            self.world.add_task(task)

    def _init_robots(self, count: int) -> None:
        """Spawn initial fleet of AMRs at unoccupied starting positions."""
        free_cells = self.warehouse.get_free_cells()
        # Choose spread out starting cells
        start_indices = np.linspace(0, len(free_cells) - 1, count, dtype=int)
        
        for i, idx in enumerate(start_indices):
            robot_id = f"R{i+1}"
            pos = free_cells[idx]
            robot = Robot(id=robot_id, initial_position=pos)
            
            # Create decentralized LocalWorldModel for each AMR
            robot.local_world_model = LocalWorldModel(
                self_id=robot_id,
                map_width=self.warehouse.width,
                map_height=self.warehouse.height,
                static_grid=self.warehouse.grid,
            )
            self.world.add_robot(robot)

    def schedule_blockage(self, step: int, cell: Tuple[int, int]) -> None:
        """Schedule a dynamic aisle blockage event."""
        self.scheduled_blockages.append((step, cell))

    def schedule_failure(self, step: int, robot_id: str, reason: str = "Motor stall") -> None:
        """Schedule a robot hardware fault event."""
        self.scheduled_failures.append((step, robot_id, reason))

    def step(self) -> None:
        """Execute exactly one simulation tick strictly adhering to the 16-step contract."""
        # 1. Advance simulation clock
        sim_time = self.clock.tick()
        step = self.clock.current_step

        # 2. Apply external events (scheduled blockages and failures)
        self._apply_scheduled_events(step, sim_time)

        # 3. Update ground-truth world
        gt_robots = self.world.get_ground_truth_robot_positions()
        gt_obstacles = self.world.get_ground_truth_obstacles(sim_time)

        # 4. Generate sensor observations (per-robot observation with range & noise limits)
        observations = {}
        for r_id, robot in self.world.robots.items():
            if robot.is_healthy:
                obs = self.sensor_suite.scan(
                    robot_id=r_id,
                    robot_pos=robot.position,
                    sim_time=sim_time,
                    ground_truth_robots=gt_robots,
                    ground_truth_obstacles=gt_obstacles,
                )
                observations[r_id] = obs

        # 5. Deliver network messages whose delay has elapsed
        active_ids = {r_id for r_id, r in self.world.robots.items() if r.is_healthy}
        self.comm_mesh.step_deliver(sim_time, gt_robots, active_ids)

        # 6. Update each robot's local belief/world model (sensor sweeps + received P2P packets)
        for r_id, robot in self.world.robots.items():
            if not robot.is_healthy:
                continue

            # Update from local sensors
            if r_id in observations:
                robot.local_world_model.update_from_sensor_observation(observations[r_id])

            # Update from received P2P network inbox
            inbox_msgs = self.comm_mesh.receive_inbox(r_id)
            for msg in inbox_msgs:
                if msg.message_type == MessageType.STATE:
                    p = msg.payload
                    robot.local_world_model.update_from_peer_message(
                        sender_id=msg.sender_id,
                        position=tuple(p.get("position", (0, 0))),
                        velocity=p.get("velocity", 0.0),
                        heading=p.get("heading", 0.0),
                        intended_action=p.get("intended_action", "WAIT"),
                        planned_path=[tuple(x) for x in p.get("planned_path", [])],
                        current_task_id=p.get("current_task_id"),
                        priority=p.get("priority", 1.0),
                        timestamp=msg.creation_time,
                        sequence_number=msg.sequence_number,
                    )
                elif msg.message_type == MessageType.BLOCKAGE:
                    b_cell = tuple(msg.payload.get("cell", (0, 0)))
                    robot.local_world_model.known_blocked_cells.add(b_cell)

            # Broadcast own state to peers via P2P network
            self.comm_mesh.send_message(
                sender_id=r_id,
                receiver_id="*",
                msg_type=MessageType.STATE,
                payload={
                    "position": list(robot.position),
                    "velocity": robot.velocity,
                    "heading": robot.heading,
                    "intended_action": "MOVE",
                    "planned_path": [list(p) for p in robot.planned_path[:5]],
                    "current_task_id": robot.current_task_id,
                    "priority": robot.dynamic_priority,
                },
                current_sim_time=sim_time,
            )

        # 7. Update task/robot state machines & Dynamic task generation
        new_tasks = self.task_generator.generate_step(sim_time, self.timestep)
        for t in new_tasks:
            self.world.add_task(t)
            self.event_bus.publish(
                Event(
                    event_type=EventType.TASK_CREATED,
                    sim_time=sim_time,
                    step=step,
                    source="TaskGenerator",
                    data=t.to_dict(),
                )
            )

        self._update_task_lifecycles(sim_time, step)

        # 8 & 9 & 10 & 11 & 12: Coordination, Allocation, Deadlock detection, Planning & Trajectory Gen
        candidate_actions = self.coordinator.step_coordinate(
            robots=self.world.robots,
            tasks=self.world.tasks,
            is_walkable_fn=self.warehouse.is_walkable,
            blocked_cells=self.warehouse.blocked_cells,
            sim_time=sim_time,
            step=step,
        )
        # Record pure planning latency
        self.metrics.record_planning_latency(self.coordinator.multi_agent_planner.last_planning_latency_ms)

        # 13. Safety supervisor validation (hard invariant checking & fallback replacement)
        current_pos_map = {r_id: r.position for r_id, r in self.world.robots.items()}
        failed_ids = {r_id for r_id, r in self.world.robots.items() if not r.is_healthy}
        priorities = {r_id: r.dynamic_priority for r_id, r in self.world.robots.items()}

        approved_actions = self.safety_supervisor.filter_actions(
            candidate_actions=candidate_actions,
            current_positions=current_pos_map,
            blocked_cells=self.warehouse.blocked_cells,
            failed_robot_ids=failed_ids,
            robot_priorities=priorities,
            sim_time=sim_time,
            step=step,
        )

        # 14. Execute only approved actions via ActionExecutor
        prev_positions = {r_id: r.position for r_id, r in self.world.robots.items()}
        for r_id, robot in self.world.robots.items():
            if r_id in approved_actions:
                act = approved_actions[r_id]
                self.executor.execute_action(robot, act, self.timestep)

        # 14b. Ground-truth collision audit at every simulation tick
        self._check_physical_collisions(step, sim_time, prev_positions)

        # 15. Update metrics & resource profiling
        self._update_metrics(sim_time, step)

        # 16. Record replay state frame
        if self.recorder is not None:
            self.recorder.record_step(
                step=step,
                sim_time=sim_time,
                robots={r_id: r.to_dict() for r_id, r in self.world.robots.items()},
                tasks={t_id: t.to_dict() for t_id, t in self.world.tasks.items()},
                blocked_cells=[list(c) for c in self.warehouse.blocked_cells],
                events_this_step=self.event_bus.get_history()[-5:],
                metrics_dict=self.metrics.get_summary(),
            )

    def _apply_scheduled_events(self, step: int, sim_time: float) -> None:
        """Apply dynamic blockages or hardware faults scheduled for this step."""
        # Blockages
        for b_step, b_cell in list(self.scheduled_blockages):
            if step >= b_step:
                self.warehouse.block_cell(b_cell)
                # Broadcast blockage discovery
                self.comm_mesh.send_message(
                    sender_id="ENVIRONMENT",
                    receiver_id="*",
                    msg_type=MessageType.BLOCKAGE,
                    payload={"cell": list(b_cell)},
                    current_sim_time=sim_time,
                )
                self.event_bus.publish(
                    Event(
                        event_type=EventType.AISLE_BLOCKED,
                        sim_time=sim_time,
                        step=step,
                        source="Environment",
                        data={"cell": list(b_cell)},
                    )
                )
                self.scheduled_blockages.remove((b_step, b_cell))

        # Failures
        for f_step, f_robot_id, f_reason in list(self.scheduled_failures):
            if step >= f_step:
                robot = self.world.robots.get(f_robot_id)
                if robot and robot.is_healthy:
                    robot.is_healthy = False
                    robot.set_state(RobotState.FAILED, f_reason)
                    # Reclaim task
                    if robot.current_task_id:
                        task = self.world.tasks.get(robot.current_task_id)
                        if task and task.state != TaskState.DELIVERED:
                            task.state = TaskState.QUEUED
                            task.assigned_robot_id = None
                            task.priority += 1.0
                            robot.current_task_id = None
                            self.event_bus.publish(
                                Event(
                                    event_type=EventType.TASK_REASSIGNED,
                                    sim_time=sim_time,
                                    step=step,
                                    source="FailureRecovery",
                                    data={"robot_id": robot.id, "task_id": task.id},
                                )
                            )
                    self.event_bus.publish(
                        Event(
                            event_type=EventType.ROBOT_FAILED,
                            sim_time=sim_time,
                            step=step,
                            source="Environment",
                            data={"robot_id": robot.id, "reason": f_reason},
                        )
                    )
                self.scheduled_failures.remove((f_step, f_robot_id, f_reason))

    def _update_task_lifecycles(self, sim_time: float, step: int) -> None:
        """Advance robot task interaction states (picking up, delivering)."""
        for r_id, robot in self.world.robots.items():
            if not robot.current_task_id or not robot.is_healthy:
                continue

            task = self.world.tasks.get(robot.current_task_id)
            if not task:
                continue

            # Arrived at pickup
            if robot.position == task.pickup and task.state == TaskState.ASSIGNED:
                task.state = TaskState.PICKED_UP
                task.pickup_time = sim_time
                robot.has_payload = True
                robot.set_state(RobotState.DELIVERING, "Arrived at pickup, transitioning to delivery")
                robot.target_position = task.dropoff
                self.event_bus.publish(
                    Event(
                        event_type=EventType.TASK_PICKED_UP,
                        sim_time=sim_time,
                        step=step,
                        source="Simulation",
                        data={"robot_id": robot.id, "task_id": task.id},
                    )
                )

            # Arrived at dropoff
            elif robot.position == task.dropoff and task.state == TaskState.PICKED_UP:
                task.state = TaskState.DELIVERED
                task.completion_time = sim_time
                robot.has_payload = False
                robot.set_state(RobotState.IDLE, "Delivered payload")
                robot.current_task_id = None
                robot.target_position = None
                robot.reset_wait()
                
                # Record metrics
                duration = task.total_completion_duration or (sim_time - task.creation_time)
                self.metrics.record_task_completed(duration)
                
                self.event_bus.publish(
                    Event(
                        event_type=EventType.TASK_COMPLETED,
                        sim_time=sim_time,
                        step=step,
                        source="Simulation",
                        data={"robot_id": robot.id, "task_id": task.id, "duration": duration},
                    )
                )

    def _update_metrics(self, sim_time: float, step: int) -> None:
        """Gather edge profiling samples and compute snapshot."""
        cpu, mem = self.resource_monitor.sample()
        total_created = len(self.world.tasks)
        total_completed = len([t for t in self.world.tasks.values() if t.is_completed])
        active_robots = len([r for r in self.world.robots.values() if r.is_healthy])
        total_waiting = sum(r.wait_steps for r in self.world.robots.values())

        self.metrics.record_snapshot(
            step=step,
            sim_time=sim_time,
            total_created=total_created,
            total_completed=total_completed,
            active_robots=active_robots,
            waiting_steps=total_waiting,
            messages_sent=self.comm_mesh.total_messages_sent,
            messages_dropped=self.comm_mesh.total_messages_dropped,
            cpu_pct=cpu,
            mem_mb=mem,
        )

    def _check_physical_collisions(self, step: int, sim_time: float, prev_positions: Dict[str, Tuple[int, int]]) -> None:
        """Physical ground-truth collision auditor verifying zero collisions at every simulation tick."""
        robots_list = [r for r in self.world.robots.values() if r.is_healthy]

        # 1. Obstacle collision
        for r in robots_list:
            if not self.warehouse.is_walkable(r.position) or r.position in self.warehouse.blocked_cells:
                self.metrics.total_collisions += 1
                self.event_bus.publish(
                    Event(
                        event_type=EventType.CRITICAL_SAFETY_VIOLATION,
                        sim_time=sim_time,
                        step=step,
                        source="CollisionAuditor",
                        data={"type": "OBSTACLE_COLLISION", "robot_id": r.id, "position": list(r.position)},
                    )
                )

        # 2. Pairwise conflicts: Vertex, Edge Swap, and Continuous swept geometric overlap
        n = len(robots_list)
        for i in range(n):
            r1 = robots_list[i]
            p1_curr = r1.position
            p1_prev = prev_positions.get(r1.id, p1_curr)

            for j in range(i + 1, n):
                r2 = robots_list[j]
                p2_curr = r2.position
                p2_prev = prev_positions.get(r2.id, p2_curr)

                # Same cell collision (Vertex)
                if p1_curr == p2_curr:
                    self.metrics.total_collisions += 1
                    self.event_bus.publish(
                        Event(
                            event_type=EventType.CRITICAL_SAFETY_VIOLATION,
                            sim_time=sim_time,
                            step=step,
                            source="CollisionAuditor",
                            data={"type": "SAME_CELL_COLLISION", "robots": [r1.id, r2.id], "position": list(p1_curr)},
                        )
                    )

                # Edge swap collision
                elif p1_curr == p2_prev and p2_curr == p1_prev and p1_curr != p1_prev:
                    self.metrics.total_collisions += 1
                    self.event_bus.publish(
                        Event(
                            event_type=EventType.CRITICAL_SAFETY_VIOLATION,
                            sim_time=sim_time,
                            step=step,
                            source="CollisionAuditor",
                            data={"type": "EDGE_SWAP_COLLISION", "robots": [r1.id, r2.id]},
                        )
                    )
