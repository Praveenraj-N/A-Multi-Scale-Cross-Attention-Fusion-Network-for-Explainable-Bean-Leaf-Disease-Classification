import torch
import torch.nn as nn


# =========================================================
# 1. Channel Shuffle
# =========================================================
class ChannelShuffle(nn.Module):

    def __init__(self, groups=3):
        super().__init__()
        self.groups = groups

    def forward(self, x):

        batch_size, channels, height, width = x.size()

        channels_per_group = channels // self.groups

        x = x.view(
            batch_size,
            self.groups,
            channels_per_group,
            height,
            width
        )

        x = x.transpose(1, 2).contiguous()

        x = x.view(
            batch_size,
            channels,
            height,
            width
        )

        return x


# =========================================================
# 2. Group Convolution
# =========================================================
class GroupConv(nn.Module):

    def __init__(
        self,
        in_channels,
        out_channels,
        groups=3,
        stride=1
    ):
        super().__init__()

        self.conv = nn.Conv2d(
            in_channels,
            out_channels,
            kernel_size=3,
            stride=stride,
            padding=1,
            groups=groups,
            bias=False
        )

        self.bn = nn.BatchNorm2d(out_channels)

        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):

        x = self.conv(x)
        x = self.bn(x)
        x = self.relu(x)

        return x


# =========================================================
# 3. Depthwise-Separable Convolution
# =========================================================
class DepthwiseSeparableConv(nn.Module):

    def __init__(
        self,
        in_channels,
        out_channels,
        stride=1
    ):
        super().__init__()

        # Depthwise convolution
        self.depthwise = nn.Conv2d(
            in_channels,
            in_channels,
            kernel_size=3,
            stride=stride,
            padding=1,
            groups=in_channels,
            bias=False
        )

        # Pointwise convolution
        self.pointwise = nn.Conv2d(
            in_channels,
            out_channels,
            kernel_size=1,
            bias=False
        )

        self.bn = nn.BatchNorm2d(out_channels)

        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):

        x = self.depthwise(x)
        x = self.pointwise(x)
        x = self.bn(x)
        x = self.relu(x)

        return x


# =========================================================
# 4. GSDW Block
#
# Group Convolution
#        ↓
# Channel Shuffle
#        ↓
# Depthwise-Separable Convolution
# =========================================================
class GSDWBlock(nn.Module):

    def __init__(
        self,
        in_channels,
        out_channels,
        groups=3,
        stride=1
    ):
        super().__init__()

        self.group_conv = GroupConv(
            in_channels=in_channels,
            out_channels=out_channels,
            groups=groups,
            stride=stride
        )

        self.channel_shuffle = ChannelShuffle(
            groups=groups
        )

        self.depthwise_separable = DepthwiseSeparableConv(
            in_channels=out_channels,
            out_channels=out_channels,
            stride=1
        )

    def forward(self, x):

        x = self.group_conv(x)

        x = self.channel_shuffle(x)

        x = self.depthwise_separable(x)

        return x


# =========================================================
# 5. Global Context Network (GCN)
#
# Paper Figure 6 depicts a 4-branch Inception-style module:
#   branch 1: MaxPool 3x3            -> Conv 1x1 ("C" filters)
#   branch 2: Conv 1x1               -> Conv 5x5 ("C" filters)
#   branch 3: Conv 1x1               -> Conv 3x3 ("C" filters)
#   branch 4: Conv 1x1 ("C" filters)
# concatenated to an output of (H, W, 4C) — this is what the paper
# text means by "the penultimate layer generates 48 channels".
#
# Note: the paper's Eq. 4 (citing GCNet) instead describes a
# squeeze-and-excitation-style context-pooling formulation, which
# contradicts Figure 6. This implementation follows Figure 6, since
# it is the concrete, checkable diagram.
# =========================================================
class GCNBlock(nn.Module):

    def __init__(self, in_channels, branch_channels):

        super().__init__()

        self.branch1 = nn.Sequential(
            nn.MaxPool2d(kernel_size=3, stride=1, padding=1),
            nn.Conv2d(in_channels, branch_channels, kernel_size=1, bias=False),
            nn.BatchNorm2d(branch_channels),
            nn.ReLU(inplace=True)
        )

        self.branch2 = nn.Sequential(
            nn.Conv2d(in_channels, branch_channels, kernel_size=1, bias=False),
            nn.BatchNorm2d(branch_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(branch_channels, branch_channels, kernel_size=5, padding=2, bias=False),
            nn.BatchNorm2d(branch_channels),
            nn.ReLU(inplace=True)
        )

        self.branch3 = nn.Sequential(
            nn.Conv2d(in_channels, branch_channels, kernel_size=1, bias=False),
            nn.BatchNorm2d(branch_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(branch_channels, branch_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(branch_channels),
            nn.ReLU(inplace=True)
        )

        self.branch4 = nn.Sequential(
            nn.Conv2d(in_channels, branch_channels, kernel_size=1, bias=False),
            nn.BatchNorm2d(branch_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x):

        b1 = self.branch1(x)
        b2 = self.branch2(x)
        b3 = self.branch3(x)
        b4 = self.branch4(x)

        return torch.cat([b1, b2, b3, b4], dim=1)


# =========================================================
# 6. GCADSN Backbone
#
# Matches paper Figure 4: stem conv -> 3x (GSDW block + BN) -> GCN.
# 224x224 -> stem(stride 4) -> 56x56x6
#          -> GSDW1(stride 2) -> 28x28x9  -> BN
#          -> GSDW2(stride 2) -> 14x14x12 -> BN
#          -> GSDW3(stride 2) -> 7x7x24   -> BN
#          -> GCN (4 branches x 12 channels) -> 7x7x48 -> BN
# =========================================================
class GCADSNBackbone(nn.Module):

    def __init__(self):

        super().__init__()

        # -------------------------------------------------
        # Initial convolution
        #
        # 224 × 224 → 56 × 56
        # -------------------------------------------------
        self.stem = nn.Sequential(

            nn.Conv2d(
                3,
                6,
                kernel_size=7,
                stride=4,
                padding=3,
                bias=False
            ),

            nn.BatchNorm2d(6),

            nn.ReLU(inplace=True)
        )

        # -------------------------------------------------
        # Stage 1
        #
        # 56 × 56 → 28 × 28
        # 9 channels
        # -------------------------------------------------
        self.stage1 = GSDWBlock(
            in_channels=6,
            out_channels=9,
            groups=3,
            stride=2
        )

        self.bn1 = nn.BatchNorm2d(9)

        # -------------------------------------------------
        # Stage 2
        #
        # 28 × 28 → 14 × 14
        # 12 channels
        # -------------------------------------------------
        self.stage2 = GSDWBlock(
            in_channels=9,
            out_channels=12,
            groups=3,
            stride=2
        )

        self.bn2 = nn.BatchNorm2d(12)

        # -------------------------------------------------
        # Stage 3
        #
        # 14 × 14 → 7 × 7
        # 24 channels
        # -------------------------------------------------
        self.stage3 = GSDWBlock(
            in_channels=12,
            out_channels=24,
            groups=3,
            stride=2
        )

        self.bn3 = nn.BatchNorm2d(24)

        # -------------------------------------------------
        # Global Context Network
        #
        # 7 × 7, 24 channels → 7 × 7, 48 channels (4 x 12)
        # -------------------------------------------------
        self.gcn = GCNBlock(
            in_channels=24,
            branch_channels=12
        )

        self.bn4 = nn.BatchNorm2d(48)

    def forward(self, x):

        # Initial convolution
        x = self.stem(x)

        # Stage 1
        stage1 = self.stage1(x)
        stage1 = self.bn1(stage1)

        # Stage 2
        stage2 = self.stage2(stage1)
        stage2 = self.bn2(stage2)

        # Stage 3
        stage3 = self.stage3(stage2)
        stage3 = self.bn3(stage3)

        # Global context
        context = self.gcn(stage3)
        context = self.bn4(context)

        return [
            stage1,
            stage2,
            stage3,
            context
        ]