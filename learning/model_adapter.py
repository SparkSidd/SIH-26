"""Neural network architecture adapted from RL-RH-PP (Zheng et al., JAIR 2026).

This module implements a lightweight spatial-temporal attention encoder and
priority decoder designed for real-time edge CPU inference (< 1 ms).
"""

import math
from typing import Dict, List, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F

from learning.config import LearningConfig


class MultiHeadAttentionBlock(nn.Module):
    """Multi-Head Self-Attention block with residual connection and LayerNorm."""

    def __init__(self, embed_dim: int, num_heads: int, dropout: float = 0.0):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        assert self.head_dim * num_heads == embed_dim, "embed_dim must be divisible by num_heads"

        self.q_proj = nn.Linear(embed_dim, embed_dim, bias=False)
        self.k_proj = nn.Linear(embed_dim, embed_dim, bias=False)
        self.v_proj = nn.Linear(embed_dim, embed_dim, bias=False)
        self.out_proj = nn.Linear(embed_dim, embed_dim, bias=True)

        self.norm1 = nn.LayerNorm(embed_dim)
        self.norm2 = nn.LayerNorm(embed_dim)

        self.ffn = nn.Sequential(
            nn.Linear(embed_dim, embed_dim * 2),
            nn.LeakyReLU(0.1),
            nn.Dropout(dropout),
            nn.Linear(embed_dim * 2, embed_dim),
        )

    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        # x shape: [Batch, N_agents, embed_dim]
        B, N, D = x.shape
        residual = x
        x_norm = self.norm1(x)

        q = self.q_proj(x_norm).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x_norm).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x_norm).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        # Scaled dot-product attention: [B, H, N, N]
        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        if mask is not None:
            scores = scores + mask.unsqueeze(1).unsqueeze(2)

        attn_weights = F.softmax(scores, dim=-1)
        context = torch.matmul(attn_weights, v)  # [B, H, N, head_dim]
        context = context.transpose(1, 2).contiguous().view(B, N, D)
        out = self.out_proj(context) + residual

        # Feed-forward block
        out = out + self.ffn(self.norm2(out))
        return out


class RLRHPPPriorityNet(nn.Module):
    """GNN & Attention-based Priority Assignment Network adapted from RL-RH-PP.
    
    Given agent feature vectors (positions, task urgency, battery, wait steps, congestion),
    the network encodes inter-agent spatial-temporal dependencies via self-attention
    and outputs relative priority scores for MAPF scheduling.
    """

    def __init__(self, config: Optional[LearningConfig] = None):
        super().__init__()
        self.config = config or LearningConfig()
        
        feature_dim = self.config.feature_dim
        hidden_dim = self.config.hidden_dim
        num_heads = self.config.num_heads
        n_layers = self.config.n_layers
        dropout = self.config.dropout

        # 1. Feature projection layer (converts agent attributes to hidden embedding)
        self.agent_encoder = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.LeakyReLU(0.1),
            nn.Linear(hidden_dim, hidden_dim),
        )

        # 2. Inter-agent attention layers (captures spatial proximity and conflict risk)
        self.attention_layers = nn.ModuleList([
            MultiHeadAttentionBlock(hidden_dim, num_heads, dropout=dropout)
            for _ in range(n_layers)
        ])

        # 3. Priority decoding head (outputs relative priority scores per agent)
        self.priority_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.LeakyReLU(0.1),
            nn.Linear(hidden_dim // 2, 1),
        )

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor, mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """Forward pass predicting priority scores for each agent.
        
        Args:
            x: Agent feature tensor of shape [Batch, N_agents, feature_dim]
            mask: Optional attention mask
            
        Returns:
            Priority scores of shape [Batch, N_agents]
        """
        # x: [B, N, F] -> [B, N, H]
        h = self.agent_encoder(x)

        for layer in self.attention_layers:
            h = layer(h, mask=mask)

        # Priority scoring: [B, N, 1] -> [B, N]
        logits = self.priority_head(h).squeeze(-1)
        return logits

    def freeze_backbone(self) -> None:
        """Freeze the spatial attention backbone for transfer learning."""
        for param in self.agent_encoder.parameters():
            param.requires_grad = False
        for param in self.attention_layers.parameters():
            param.requires_grad = False

    def unfreeze_all(self) -> None:
        """Unfreeze all layers for full fine-tuning."""
        for param in self.parameters():
            param.requires_grad = True

    def count_parameters(self) -> int:
        """Return the total number of trainable and non-trainable parameters."""
        return sum(p.numel() for p in self.parameters())

    def get_model_size_kb(self) -> float:
        """Calculate the in-memory parameter footprint in KB."""
        param_bytes = sum(p.numel() * p.element_size() for p in self.parameters())
        buffer_bytes = sum(b.numel() * b.element_size() for b in self.buffers())
        return (param_bytes + buffer_bytes) / 1024.0
