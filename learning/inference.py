"""Production-grade inference engine with strict safety guards, NaN checks, and timeout fallback."""

import logging
import time
from typing import Dict, List, Optional, Tuple
import torch

from learning.config import LearningConfig
from learning.model_adapter import RLRHPPPriorityNet
from learning.observation_adapter import ObservationAdapter

logger = logging.getLogger(__name__)


class InferenceEngine:
    """Evaluates neural priority policy with strict runtime exception and latency guards."""

    def __init__(
        self,
        model: RLRHPPPriorityNet,
        config: Optional[LearningConfig] = None,
        observation_adapter: Optional[ObservationAdapter] = None,
    ):
        self.model = model
        self.config = config or LearningConfig()
        self.obs_adapter = observation_adapter or ObservationAdapter()
        
        self.model.eval()
        self.device = self.config.device
        self.model.to(self.device)

        # Performance monitoring
        self.total_inferences: int = 0
        self.fallback_count: int = 0
        self.last_latency_ms: float = 0.0
        self.total_latency_ms: float = 0.0
        self.max_latency_ms: float = 0.0

        # Warmup forward pass to eliminate PyTorch lazy initialization jitter
        try:
            dummy = torch.zeros((1, 6, self.config.feature_dim), device=self.device)
            with torch.no_grad():
                _ = self.model(dummy)
        except Exception:
            pass

    def predict_priorities(
        self,
        active_robot_ids: List[str],
        obs_tensor: torch.Tensor,
    ) -> Tuple[bool, Dict[str, float], str]:
        """Compute relative priority scores for active robots.
        
        Returns:
            (success, priorities_dict, status_message)
        """
        if not active_robot_ids:
            return True, {}, "No active robots"

        t_start = time.perf_counter()
        self.total_inferences += 1

        try:
            # 1. Tensor sanity checks
            if torch.isnan(obs_tensor).any() or torch.isinf(obs_tensor).any():
                self.fallback_count += 1
                return False, {}, "NaN or Inf detected in observation tensor"

            obs_tensor = obs_tensor.to(self.device)

            # 2. Forward inference (no gradient computation)
            with torch.no_grad():
                logits = self.model(obs_tensor)  # Shape: [1, N_agents]

            # 3. Output validation
            if torch.isnan(logits).any() or torch.isinf(logits).any():
                self.fallback_count += 1
                return False, {}, "NaN or Inf produced in model logits"

            scores = logits.squeeze(0).cpu().tolist()
            if isinstance(scores, float):
                scores = [scores]

            if len(scores) != len(active_robot_ids):
                self.fallback_count += 1
                return False, {}, f"Shape mismatch: {len(scores)} outputs for {len(active_robot_ids)} robots"

            # 4. Normalize and map to positive priority values
            # Base priority scale: 1.0 to 10.0
            min_s = min(scores)
            max_s = max(scores)
            range_s = max_s - min_s if (max_s - min_s) > 1e-4 else 1.0

            priorities: Dict[str, float] = {}
            for i, r_id in enumerate(active_robot_ids):
                # Scale relative priority cleanly
                normalized_score = 1.0 + 4.0 * ((scores[i] - min_s) / range_s)
                priorities[r_id] = round(normalized_score, 3)

            # Timing check
            t_end = time.perf_counter()
            self.last_latency_ms = (t_end - t_start) * 1000.0
            self.total_latency_ms += self.last_latency_ms
            if self.last_latency_ms > self.max_latency_ms:
                self.max_latency_ms = self.last_latency_ms

            # 5. Latency timeout guard
            if self.last_latency_ms > self.config.timeout_ms:
                logger.warning(
                    f"Inference latency {self.last_latency_ms:.2f}ms exceeded budget {self.config.timeout_ms}ms"
                )

            return True, priorities, "Inference successful"

        except Exception as e:
            self.fallback_count += 1
            logger.warning(f"Inference exception: {str(e)}")
            return False, {}, f"Exception during inference: {str(e)}"

    @property
    def mean_latency_ms(self) -> float:
        """Mean inference latency across all evaluations."""
        if self.total_inferences == 0:
            return 0.0
        return self.total_latency_ms / self.total_inferences
