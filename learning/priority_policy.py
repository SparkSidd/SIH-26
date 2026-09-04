"""High-level priority policy advisor integrating the neural model and deterministic fallback."""

import logging
from typing import Dict, List, Optional, Set, Tuple

from coordination.priority import PriorityEngine
from learning.checkpoint_loader import CheckpointLoader
from learning.config import LearningConfig
from learning.inference import InferenceEngine
from learning.model_adapter import RLRHPPPriorityNet
from learning.observation_adapter import ObservationAdapter
from simulator.robot import Robot
from simulator.task import Task

logger = logging.getLogger(__name__)


class PriorityPolicy:
    """Advisory decision layer providing learning-guided priority scores with deterministic fallback."""

    def __init__(
        self,
        config: Optional[LearningConfig] = None,
        deterministic_engine: Optional[PriorityEngine] = None,
    ):
        self.config = config or LearningConfig()
        self.deterministic_engine = deterministic_engine or PriorityEngine()
        self.obs_adapter = ObservationAdapter(feature_dim=self.config.feature_dim)
        
        # Neural model components
        self.model = RLRHPPPriorityNet(self.config)
        self.inference_engine = InferenceEngine(
            model=self.model,
            config=self.config,
            observation_adapter=self.obs_adapter,
        )

        self.is_loaded: bool = False
        self.checkpoint_metadata: Dict = {}
        self.last_was_fallback: bool = True
        self.last_status: str = "Uninitialized"

        # Attempt checkpoint loading if specified
        if self.config.checkpoint_path:
            self.load_checkpoint(self.config.checkpoint_path)

    def load_checkpoint(self, checkpoint_path: str) -> bool:
        """Load trained weights from checkpoint."""
        success, msg, metadata = CheckpointLoader.load_checkpoint(
            self.model, checkpoint_path, device=self.config.device
        )
        self.is_loaded = success
        self.checkpoint_metadata = metadata
        self.last_status = msg
        if success:
            logger.info(f"PriorityPolicy: {msg}")
        else:
            logger.warning(f"PriorityPolicy: {msg} - Operating in deterministic fallback mode.")
        return success

    def get_fleet_priorities(
        self,
        active_robot_ids: List[str],
        robots: Dict[str, Robot],
        tasks: Dict[str, Task],
        target_goals: Dict[str, Tuple[int, int]],
        congestion_at_robots: Optional[Dict[str, float]] = None,
        blocked_cells: Optional[Set[Tuple[int, int]]] = None,
    ) -> Tuple[Dict[str, float], bool, str]:
        """Compute robot priorities.
        
        Returns:
            (priorities_dict, is_fallback, status_message)
        """
        # If learning is disabled or model weights are not loaded, use deterministic heuristic immediately
        if not self.config.enabled or not self.is_loaded:
            fallback_priorities = self._compute_deterministic_fallback(
                active_robot_ids, robots, tasks, congestion_at_robots
            )
            self.last_was_fallback = True
            reason = "Learning disabled" if not self.config.enabled else "Model checkpoint not loaded"
            self.last_status = f"Fallback ({reason})"
            return fallback_priorities, True, self.last_status

        # Try learned model inference
        try:
            obs_tensor = self.obs_adapter.encode_fleet_state(
                active_robot_ids=active_robot_ids,
                robots=robots,
                tasks=tasks,
                target_goals=target_goals,
                congestion_at_robots=congestion_at_robots,
                blocked_cells=blocked_cells,
            )

            success, learned_priorities, msg = self.inference_engine.predict_priorities(
                active_robot_ids=active_robot_ids,
                obs_tensor=obs_tensor,
            )

            if success:
                self.last_was_fallback = False
                self.last_status = "Learned Policy Active"
                return learned_priorities, False, self.last_status

            # Inference failed (NaN, timeout, or dimension mismatch) -> Fallback
            logger.warning(f"Learning inference failed: {msg}. Falling back to deterministic engine.")
            fallback_priorities = self._compute_deterministic_fallback(
                active_robot_ids, robots, tasks, congestion_at_robots
            )
            self.last_was_fallback = True
            self.last_status = f"Fallback ({msg})"
            return fallback_priorities, True, self.last_status

        except Exception as e:
            logger.error(f"Unexpected exception in PriorityPolicy: {str(e)}. Enforcing fallback.")
            fallback_priorities = self._compute_deterministic_fallback(
                active_robot_ids, robots, tasks, congestion_at_robots
            )
            self.last_was_fallback = True
            self.last_status = f"Fallback (Exception: {str(e)})"
            return fallback_priorities, True, self.last_status

    def _compute_deterministic_fallback(
        self,
        active_robot_ids: List[str],
        robots: Dict[str, Robot],
        tasks: Dict[str, Task],
        congestion_at_robots: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """Compute priorities using the proven deterministic PriorityEngine."""
        priorities = {}
        cong_map = congestion_at_robots or {}
        for r_id in active_robot_ids:
            robot = robots.get(r_id)
            if robot:
                active_task = tasks.get(robot.current_task_id) if robot.current_task_id else None
                cell_cong = cong_map.get(r_id, 0.0)
                priorities[r_id] = self.deterministic_engine.compute_robot_priority(
                    robot=robot, active_task=active_task, congestion_at_robot=cell_cong
                )
            else:
                priorities[r_id] = 1.0
        return priorities
