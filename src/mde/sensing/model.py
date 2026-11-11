"""On-scooter riding-safety model: a small 1-D CNN over 2 s of IMU, with two heads.

surface   road / sidewalk / cobblestone: sidewalk riding triggers a warning, then a slowdown
tandem    two people on one scooter

Trained with hardware randomisation (mount gain and sensor noise), because the next scooter generation will
not be the one the data came from.
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn


class RideNet(nn.Module):
    def __init__(self, channels: int = 5, width: int = 32):
        super().__init__()
        self.register_buffer("mean", torch.zeros(channels, 1))
        self.register_buffer("std", torch.ones(channels, 1))
        self.body = nn.Sequential(
            nn.Conv1d(channels, width, 7, stride=2, padding=3), nn.BatchNorm1d(width), nn.ReLU(),
            nn.Conv1d(width, 2 * width, 5, stride=2, padding=2), nn.BatchNorm1d(2 * width), nn.ReLU(),
            nn.Conv1d(2 * width, 2 * width, 5, stride=2, padding=2), nn.BatchNorm1d(2 * width), nn.ReLU(),
            nn.Conv1d(2 * width, 2 * width, 3, stride=1, padding=1), nn.ReLU(),
        )
        self.surface = nn.Linear(4 * width, 3)
        self.tandem = nn.Linear(4 * width, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        z = self.body((x - self.mean) / self.std)
        z = torch.cat([z.mean(-1), z.amax(-1)], dim=1)
        return self.surface(z), self.tandem(z).squeeze(-1)


def augment(x: torch.Tensor, gen: torch.Generator) -> torch.Tensor:
    """Hardware randomisation: per-window mount gain on the accelerometers and extra sensor noise."""
    n = x.shape[0]
    gain = 0.75 + 0.5 * torch.rand(n, 1, 1, generator=gen)
    noise = 0.15 * torch.rand(n, 1, 1, generator=gen) * torch.randn(x[:, :3].shape, generator=gen)
    x = x.clone()
    x[:, :3] = x[:, :3] * gain + noise
    return x


def fit(model: RideNet, X: np.ndarray, ys: np.ndarray, yt: np.ndarray, epochs: int, lr: float, batch: int,
        seed: int, aug: bool = True) -> list[float]:
    torch.manual_seed(seed)
    gen = torch.Generator().manual_seed(seed)
    Xt = torch.from_numpy(X)
    model.mean.copy_(Xt.mean(dim=(0, 2)).unsqueeze(-1))
    model.std.copy_(Xt.std(dim=(0, 2)).unsqueeze(-1) + 1e-6)
    s, t = torch.from_numpy(ys), torch.from_numpy(yt).float()
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=epochs * (-(-len(X) // batch)))
    pos_w = ((1 - t.mean()) / t.mean()).detach()
    losses = []
    model.train()
    for _ in range(epochs):
        perm = torch.randperm(len(X), generator=gen)
        tot = 0.0
        for i in range(0, len(X), batch):
            idx = perm[i : i + batch]
            xb = augment(Xt[idx], gen) if aug else Xt[idx]
            ls, lt = model(xb)
            loss = nn.functional.cross_entropy(ls, s[idx]) + nn.functional.binary_cross_entropy_with_logits(
                lt, t[idx], pos_weight=pos_w)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            tot += loss.item() * len(idx)
        losses.append(tot / len(X))
    model.eval()
    return losses


@torch.no_grad()
def predict(model: RideNet, X: np.ndarray, batch: int = 1024) -> tuple[np.ndarray, np.ndarray]:
    ps, pt = [], []
    for i in range(0, len(X), batch):
        ls, lt = model(torch.from_numpy(X[i : i + batch]))
        ps.append(torch.softmax(ls, -1).numpy())
        pt.append(torch.sigmoid(lt).numpy())
    return np.concatenate(ps), np.concatenate(pt)
