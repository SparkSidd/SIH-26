"""Action execution engine translating high-level actions to robot kinematic updates."""

from typing import Dict, Tuple
from execution.action import RobotAction, ActionType
from execution.motion_model import MotionModel
from simulator.robot import Robot, RobotState


class ActionExecutor:
    """Dispatches and applies validated actions to robots (precursor to ROS2 cmd_vel)."""

    def __init__(self):
        self._motion_models: Dict[str, MotionModel] = {}

    def get_motion_model(self, robot: Robot) -> MotionModel:
        if robot.id not in self._motion_models:
            self._motion_models[robot.id] = MotionModel(robot.geometry)
        return self._motion_models[robot.id]

    def execute_action(self, robot: Robot, action: RobotAction, dt: float) -> None:
        """Apply approved action to robot."""
        if not robot.is_healthy or robot.state == RobotState.FAILED:
            robot.velocity = 0.0
            return

        motion_model = self.get_motion_model(robot)

        if action.action_type == ActionType.MOVE:
            motion_model.step_discrete_motion(robot, action.target_cell, dt)
            # Transition out of any waiting/replanning state on movement
            if robot.current_task_id:
                if robot.has_payload or robot.state in (RobotState.PICKING, RobotState.DELIVERING, RobotState.MOVING_TO_DROPOFF):
                    robot.set_state(RobotState.DELIVERING, "Moving to dropoff")
                else:
                    robot.set_state(RobotState.MOVING_TO_PICKUP, "Moving to pickup")
            robot.reset_wait()

        elif action.action_type in (ActionType.WAIT, ActionType.ESTOP):
            motion_model.step_discrete_motion(robot, robot.position, dt)
            if not robot.current_task_id:
                if robot.state not in (RobotState.FAILED, RobotState.CHARGING):
                    robot.set_state(RobotState.IDLE, "Idle awaiting task")
            elif robot.current_task_id:
                # Only move to WAITING if not already in a more descriptive state
                if robot.state not in (
                    RobotState.FAILED,
                    RobotState.BLOCKED,
                    RobotState.REPLANNING,
                    RobotState.PICKING,
                    RobotState.CHARGING,
                ):
                    robot.set_state(RobotState.WAITING, "Waiting for path clearance")

        elif action.action_type == ActionType.CHARGE:
            robot.velocity = 0.0
            robot.battery.step_charge()
            robot.set_state(RobotState.CHARGING, "Charging at pad")
