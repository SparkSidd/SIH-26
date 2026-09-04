"""Configuration settings for learning-guided fleet coordination."""

from dataclasses import dataclass, field
from typing import List, Optional
import os


@dataclass
class LearningConfig:
    """Master configuration for the learning-guided decision layer."""

    enabled: bool = False
    model_name: str = "RL-RH-PP-Attention"
    device: str = "cpu"
    
    # Model architecture parameters (compact edge profile)
    feature_dim: int = 14
    hidden_dim: int = 32
    num_heads: int = 2
    n_layers: int = 2
    dropout: float = 0.0
    
    # Checkpoint paths
    pretrained_dir: str = os.path.join("learning", "checkpoints", "pretrained")
    transferred_dir: str = os.path.join("learning", "checkpoints", "transferred")
    fine_tuned_dir: str = os.path.join("learning", "checkpoints", "fine_tuned")
    checkpoint_path: Optional[str] = os.path.join("learning", "checkpoints", "fine_tuned", "best_model.pt")
    
    # Online inference and safety guards
    timeout_ms: float = 20.0  # Max milliseconds before fallback
    enable_fallback: bool = True
    min_confidence: float = 0.0
    
    # Training parameters
    learning_rate: float = 1e-3
    fine_tune_lr: float = 2e-4
    weight_decay: float = 1e-4
    batch_size: int = 32
    epochs: int = 25
    train_seeds: List[int] = field(default_factory=lambda: [42, 101, 202, 303, 404, 505])
    val_seeds: List[int] = field(default_factory=lambda: [606, 707])
    test_seeds: List[int] = field(default_factory=lambda: [808, 909])
