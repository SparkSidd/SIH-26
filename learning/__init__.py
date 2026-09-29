"""Learning-guided fleet coordination package for SIH26123."""

from learning.config import LearningConfig

__all__ = [
    "LearningConfig",
    "RLRHPPPriorityNet",
    "MultiHeadAttentionBlock",
    "ObservationAdapter",
    "CheckpointLoader",
    "InferenceEngine",
    "PriorityPolicy",
]


def __getattr__(name: str):
    """Lazy import PyTorch-dependent components only when explicitly accessed."""
    if name in ("RLRHPPPriorityNet", "MultiHeadAttentionBlock"):
        from learning import model_adapter
        val = getattr(model_adapter, name)
        globals()[name] = val
        return val
    if name == "ObservationAdapter":
        from learning.observation_adapter import ObservationAdapter
        globals()[name] = ObservationAdapter
        return ObservationAdapter
    if name == "CheckpointLoader":
        from learning.checkpoint_loader import CheckpointLoader
        globals()[name] = CheckpointLoader
        return CheckpointLoader
    if name == "InferenceEngine":
        from learning.inference import InferenceEngine
        globals()[name] = InferenceEngine
        return InferenceEngine
    if name == "PriorityPolicy":
        from learning.priority_policy import PriorityPolicy
        globals()[name] = PriorityPolicy
        return PriorityPolicy
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
