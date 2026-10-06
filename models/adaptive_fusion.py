import torch
import torch.nn as nn


class AdaptiveFusion(nn.Module):
    """Adaptive feature fusion module for combining multi-branch features.

    Replaces plain concatenation with a learned, input-dependent weighted
    sum. For `num_inputs` features that all have `in_channels` channels
    (feature maps (B, C, H, W) or vectors (B, C)):

      1. global-average-pool each input and concatenate  -> (B, n*C)
      2. a small MLP produces one score per (input, channel)  -> (B, n, C)
      3. softmax over the inputs gives per-channel fusion weights that sum
         to 1 for every channel
      4. output = sum_i weight_i * feature_i

    So the network decides, for each image and each channel, how much to
    trust each branch (or each scale). The last computed weights are kept
    in `last_weights` (B, n, C, detached) for analysis and plotting.
    """

    def __init__(
        self,
        in_channels: int,
        num_inputs: int = 2,
        reduction: int = 4
    ):
        super().__init__()

        self.in_channels = in_channels
        self.num_inputs = num_inputs

        hidden = max(in_channels // reduction, 8)

        self.gate = nn.Sequential(
            nn.Linear(in_channels * num_inputs, hidden),
            nn.GELU(),
            nn.Linear(hidden, in_channels * num_inputs)
        )

        self.last_weights = None

    def forward(self, *features: torch.Tensor):

        assert len(features) == self.num_inputs, (
            f"expected {self.num_inputs} inputs, got {len(features)}"
        )

        pooled = [
            f.mean(dim=(2, 3)) if f.dim() == 4 else f
            for f in features
        ]

        scores = self.gate(torch.cat(pooled, dim=1))

        scores = scores.view(-1, self.num_inputs, self.in_channels)

        weights = scores.softmax(dim=1)

        self.last_weights = weights.detach()

        fused = 0

        for i, feature in enumerate(features):

            weight = weights[:, i]

            if feature.dim() == 4:
                weight = weight[:, :, None, None]

            fused = fused + weight * feature

        return fused
