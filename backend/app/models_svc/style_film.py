from __future__ import annotations

from typing import Optional

import torch
from torch import nn


class StyleFiLMAdapter(nn.Module):
    def __init__(self, style_dim: int, hidden_channels: int, strength: float = 0.1) -> None:
        super().__init__()
        self.style_dim = int(style_dim)
        self.hidden_channels = int(hidden_channels)
        self.strength = float(strength)
        self.proj = nn.Linear(self.style_dim, self.hidden_channels * 2)
        nn.init.normal_(self.proj.weight, mean=0.0, std=1e-3)
        nn.init.zeros_(self.proj.bias)

    def forward(self, h: torch.Tensor, style_emb: Optional[torch.Tensor]) -> torch.Tensor:
        if style_emb is None or self.strength == 0.0:
            return h
        if h.dim() != 3:
            raise ValueError(f"StyleFiLMAdapter expects h with shape [B, C, T], got {tuple(h.shape)}")

        style = style_emb
        if style.dim() == 1:
            style = style.unsqueeze(0)
        if style.dim() != 2:
            raise ValueError(f"StyleFiLMAdapter expects style_emb with shape [B, D] or [D], got {tuple(style.shape)}")

        if style.size(0) == 1 and h.size(0) > 1:
            style = style.expand(h.size(0), -1)
        if style.size(0) != h.size(0):
            raise ValueError(
                f"StyleFiLMAdapter batch mismatch: hidden batch={h.size(0)} style batch={style.size(0)}"
            )

        style = style.to(device=h.device, dtype=h.dtype)
        gamma_beta = self.proj(style)
        gamma, beta = gamma_beta.chunk(2, dim=-1)
        gamma = self.strength * torch.tanh(gamma).unsqueeze(-1)
        beta = self.strength * torch.tanh(beta).unsqueeze(-1)
        return h * (1.0 + gamma) + beta
