import torch
import torch.nn as nn

from models.pvt import PVTBackbone
from models.gcadsn import GCADSNBackbone


class BasePVTGCADSN(nn.Module):
    """PVT v2 + GCADSN dual-track network (paper's BeanLeafNet).

    `mode` selects which track(s) feed the classifier, so this same class
    can reproduce the paper's ablation study (Table 4):
      - "fused":  PVT + GCADSN, depthwise-concatenated (the proposed network)
      - "pvt":    PVT track only
      - "gcadsn": GCADSN track only
    """

    def __init__(
        self,
        num_classes=3,
        pretrained=True,
        mode="fused",
        pvt_proj_channels=48
    ):
        super().__init__()

        assert mode in ("fused", "pvt", "gcadsn")

        self.mode = mode

        # =============================================
        # PVT v2 branch
        # =============================================
        self.pvt = PVTBackbone(
            pretrained=pretrained
        ) if mode in ("fused", "pvt") else None

        # =============================================
        # GCADSN branch
        # =============================================
        self.gcadsn = GCADSNBackbone() if mode in ("fused", "gcadsn") else None

        # =============================================
        # Final feature channels
        #
        # PVT final    = 512 (real pvt_v2_b2 stage-4 width; the paper's
        #                      Figure 8 states 48, which does not match
        #                      the actual PVTv2-B2 architecture it cites)
        # GCADSN final = 48  (GCN block, 4 branches x 12 channels)
        #
        # In fused mode the PVT features are projected 512 -> 48 (1x1 conv
        # + BN) before concatenation, so both tracks contribute equally as
        # in the paper's Figure 8 (48 + 48 = 96). Without it PVT outnumbers
        # GCADSN 512:48 and drowns it out.
        # =============================================
        self.pvt_proj = None

        if mode == "fused":
            if pvt_proj_channels:
                self.pvt_proj = nn.Sequential(
                    nn.Conv2d(512, pvt_proj_channels, kernel_size=1, bias=False),
                    nn.BatchNorm2d(pvt_proj_channels)
                )
                in_channels = pvt_proj_channels + 48
            else:
                in_channels = 512 + 48
        elif mode == "pvt":
            in_channels = 512
        else:
            in_channels = 48

        # =============================================
        # Global Average Pooling
        # =============================================
        self.global_pool = nn.AdaptiveAvgPool2d(1)

        # =============================================
        # Fusion hook point (identity op; gives GradCAM a
        # concrete layer to attach a forward/backward hook to,
        # since there is no conv layer after concatenation)
        # =============================================
        self.fusion_identity = nn.Identity()

        # =============================================
        # Classification head
        #
        # Paper: GAP -> Softmax. A single linear layer maps
        # directly to class logits (CrossEntropyLoss applies
        # softmax internally).
        # =============================================
        self.classifier = nn.Linear(
            in_channels,
            num_classes
        )

    def forward(
        self,
        x,
        return_features=False
    ):

        pvt_features = None
        gcadsn_features = None

        if self.mode == "fused":

            pvt_features = self.pvt(x)
            gcadsn_features = self.gcadsn(x)

            pvt_last = pvt_features[-1]

            if self.pvt_proj is not None:
                pvt_last = self.pvt_proj(pvt_last)

            fused = torch.cat(
                [pvt_last, gcadsn_features[-1]],
                dim=1
            )

        elif self.mode == "pvt":

            pvt_features = self.pvt(x)
            fused = pvt_features[-1]

        else:

            gcadsn_features = self.gcadsn(x)
            fused = gcadsn_features[-1]

        # =============================================
        # Hook point for GradCAM
        # =============================================
        fused = self.fusion_identity(fused)

        # =============================================
        # Global Average Pooling
        # =============================================
        pooled = self.global_pool(fused)

        # =============================================
        # Flatten
        # =============================================
        pooled = torch.flatten(
            pooled,
            start_dim=1
        )

        # =============================================
        # Classification
        # =============================================
        logits = self.classifier(pooled)

        if return_features:

            return {
                "logits": logits,
                "pvt_features": pvt_features,
                "gcadsn_features": gcadsn_features,
                "fused": fused
            }

        return logits