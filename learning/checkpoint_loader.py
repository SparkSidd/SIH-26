"""Checkpoint management, hash verification, and transfer learning loader."""

import hashlib
import json
import os
from typing import Any, Dict, Optional, Tuple
import torch
import torch.nn as nn

from learning.config import LearningConfig


class CheckpointLoader:
    """Manages loading, saving, and verifying neural priority policy checkpoints."""

    @staticmethod
    def compute_file_hash(filepath: str) -> str:
        """Calculate the SHA-256 hash of a checkpoint file."""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def save_checkpoint(
        model: nn.Module,
        filepath: str,
        config: LearningConfig,
        training_stage: str = "fine_tuned",
        metrics: Optional[Dict[str, Any]] = None,
        source_domain: str = "synthetic_warehouse_lifelong_mapf",
        target_domain: str = "sih26123_warehouse_24x16",
    ) -> str:
        """Save model checkpoint with configuration, metadata, and verification hash."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        checkpoint_data = {
            "model_state_dict": model.state_dict(),
            "config": {
                "feature_dim": config.feature_dim,
                "hidden_dim": config.hidden_dim,
                "num_heads": config.num_heads,
                "n_layers": config.n_layers,
                "model_name": config.model_name,
            },
            "training_stage": training_stage,
            "source_domain": source_domain,
            "target_domain": target_domain,
            "metrics": metrics or {},
        }
        torch.save(checkpoint_data, filepath)
        file_hash = CheckpointLoader.compute_file_hash(filepath)

        # Save metadata sidecar JSON
        meta_path = filepath + ".meta.json"
        with open(meta_path, "w") as f:
            json.dump({
                "filepath": filepath,
                "sha256": file_hash,
                "training_stage": training_stage,
                "source_domain": source_domain,
                "target_domain": target_domain,
                "metrics": metrics or {},
            }, f, indent=2)

        return file_hash

    @staticmethod
    def load_checkpoint(
        model: nn.Module,
        filepath: str,
        device: str = "cpu",
        strict: bool = True,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Load weights into model and return (success, status_message, metadata)."""
        if not os.path.exists(filepath):
            return False, f"Checkpoint not found at {filepath}", {}

        try:
            checkpoint = torch.load(filepath, map_location=device)
            if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
                state_dict = checkpoint["model_state_dict"]
                metadata = {k: v for k, v in checkpoint.items() if k != "model_state_dict"}
            else:
                state_dict = checkpoint
                metadata = {}

            model.load_state_dict(state_dict, strict=strict)
            file_hash = CheckpointLoader.compute_file_hash(filepath)
            metadata["sha256"] = file_hash
            return True, f"Successfully loaded checkpoint from {filepath} (hash: {file_hash[:10]}...)", metadata
        except Exception as e:
            return False, f"Failed to load checkpoint: {str(e)}", {}

    @staticmethod
    def transfer_pretrained_weights(
        base_checkpoint_path: str,
        target_model: nn.Module,
        freeze_backbone: bool = True,
        device: str = "cpu",
    ) -> Tuple[bool, str]:
        """Transfer weights from a pretrained base model and optionally freeze layers."""
        success, msg, _ = CheckpointLoader.load_checkpoint(
            target_model, base_checkpoint_path, device=device, strict=False
        )
        if not success:
            return False, msg

        if freeze_backbone and hasattr(target_model, "freeze_backbone"):
            target_model.freeze_backbone()
            return True, f"Transferred weights from {base_checkpoint_path} and froze backbone."

        return True, f"Transferred weights from {base_checkpoint_path}."
