"""Deterministic Safety Supervisor: Final actuator gatekeeper guaranteeing collision-free operation."""

from typing import Dict, List, Optional, Set, Tuple
from events.event import Event, EventType
from events.event_bus import EventBus
from execution.action import RobotAction, ActionType
from safety.invariants import SafetyInvariants, SafetyInvariantReport
from safety.fallback import SafetyFallback


class SafetySupervisor:
    """Hard-constraint safety supervisor with supreme veto authority over robot actuators."""

    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus
        self.total_interventions: int = 0
        self.critical_violations: int = 0

    def filter_actions(
        self,
        candidate_actions: Dict[str, RobotAction],
        current_positions: Dict[str, Tuple[int, int]],
        blocked_cells: Set[Tuple[int, int]],
        failed_robot_ids: Set[str],
        robot_priorities: Dict[str, float],
        sim_time: float = 0.0,
        step: int = 0,
    ) -> Dict[str, RobotAction]:
        """Validate all proposed candidate actions and return safe executable actions."""
        # 1. Initial invariant check
        report = SafetyInvariants.verify_action_batch(
            candidate_actions, current_positions, blocked_cells, failed_robot_ids
        )

        if report.is_safe:
            return candidate_actions

        # 2. Invariant violation detected: Safely resolve conflicts via priority ordering
        approved_actions: Dict[str, RobotAction] = {}
        occupied_targets: Set[Tuple[int, int]] = set()

        # Sort robots by priority (descending)
        sorted_robots = sorted(
            candidate_actions.keys(),
            key=lambda r: robot_priorities.get(r, 1.0),
            reverse=True,
        )

        for robot_id in sorted_robots:
            action = candidate_actions[robot_id]
            target = action.target_cell
            curr_pos = current_positions.get(robot_id, target)

            # Check if robot is failed
            if robot_id in failed_robot_ids:
                approved_actions[robot_id] = SafetyFallback.create_estop_fallback(
                    robot_id, curr_pos, "Robot hardware failed"
                )
                occupied_targets.add(curr_pos)
                continue

            # Check if target is blocked
            if target in blocked_cells:
                self.total_interventions += 1
                approved_actions[robot_id] = SafetyFallback.create_wait_fallback(
                    robot_id, curr_pos, f"Target {target} is blocked"
                )
                occupied_targets.add(curr_pos)
                self._emit_intervention(robot_id, "BLOCKED_TARGET", sim_time, step)
                continue

            # Check vertex conflict against already approved targets
            if target in occupied_targets:
                self.total_interventions += 1
                # Must yield and WAIT in current cell
                approved_actions[robot_id] = SafetyFallback.create_wait_fallback(
                    robot_id, curr_pos, f"Yielding cell {target} to higher priority peer"
                )
                occupied_targets.add(curr_pos)
                self._emit_intervention(robot_id, "VERTEX_YIELD", sim_time, step)
                continue

            # Check edge swap against already approved actions
            edge_swap = False
            for other_id, approved_act in approved_actions.items():
                other_curr = current_positions.get(other_id, approved_act.target_cell)
                if target == other_curr and approved_act.target_cell == curr_pos and target != curr_pos:
                    edge_swap = True
                    break

            if edge_swap:
                self.total_interventions += 1
                approved_actions[robot_id] = SafetyFallback.create_wait_fallback(
                    robot_id, curr_pos, "Preventing edge-swap collision"
                )
                occupied_targets.add(curr_pos)
                self._emit_intervention(robot_id, "EDGE_SWAP_YIELD", sim_time, step)
                continue

            # Action is safe
            approved_actions[robot_id] = action
            occupied_targets.add(target)

        # 3. Post-pass: ensure strict invariant validity with cascading yield
        for _ in range(len(sorted_robots) + 1):
            report = SafetyInvariants.verify_action_batch(
                approved_actions, current_positions, blocked_cells, failed_robot_ids
            )
            if report.is_safe:
                break

            # If conflict exists, the moving robot must yield to the stationary robot
            # or lower priority robot yields if both are moving
            handled = False
            for r_viol in (report.violating_robots or []):
                act = approved_actions.get(r_viol)
                if not act:
                    continue
                curr = current_positions.get(r_viol, act.target_cell)
                if act.target_cell != curr:
                    self.total_interventions += 1
                    approved_actions[r_viol] = SafetyFallback.create_wait_fallback(
                        r_viol, curr, f"Cascading yield to resolve {report.violation_type}"
                    )
                    self._emit_intervention(r_viol, f"CASCADE_{report.violation_type}", sim_time, step)
                    handled = True
                    break

            if not handled and report.violating_robots:
                # Fallback: force the second violating robot to wait
                r_viol = report.violating_robots[-1]
                curr = current_positions.get(r_viol, approved_actions[r_viol].target_cell)
                approved_actions[r_viol] = SafetyFallback.create_wait_fallback(
                    r_viol, curr, "Emergency safety invariant enforcement"
                )

        return approved_actions

    def _emit_intervention(self, robot_id: str, reason: str, sim_time: float, step: int) -> None:
        if self.event_bus:
            self.event_bus.publish(
                Event(
                    event_type=EventType.SAFETY_INTERVENTION,
                    sim_time=sim_time,
                    step=step,
                    source="SafetySupervisor",
                    data={"robot_id": robot_id, "reason": reason},
                    description=f"Safety Supervisor intervened on robot {robot_id}: {reason}",
                )
            )
