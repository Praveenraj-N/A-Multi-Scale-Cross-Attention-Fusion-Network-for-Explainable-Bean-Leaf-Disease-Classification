import torch
import torch.nn as nn

from models.pvt import PVTBackbone
from models.gcadsn import GCADSNBackbone
from models.cross_attention import CrossAttention
from models.adaptive_fusion import AdaptiveFusion


# Feature-map resolution (for a 224x224 input) -> (PVT stage index,
# GCADSN stage index) whose output has that resolution.
#
#   PVT v2 stages   : 56x56 (64ch)  28x28 (128ch)  14x14 (320ch)  7x7 (512ch)
#   GCADSN outputs  : 28x28 (9ch)   14x14 (12ch)    7x7 (24ch)    7x7 GCN (48ch)
SCALE_MAP = {
    28: (1, 0),
    14: (2, 1),
    7: (3, 3),
}

GCADSN_CHANNELS = {0: 9, 1: 12, 2: 24, 3: 48}


class MSCAFNet(nn.Module):
    """Multi-Scale Cross-Attention Fusion Network.

    Extends the base paper's PVT + GCADSN network (which only concatenates
    the *last* feature map of each track) in three ways:

    1. Multi-scale: features of both tracks are fused at several
       resolutions (default 28x28, 14x14, 7x7), so small disease lesions
       (visible only at fine scales) and global leaf context are both used.
    2. Cross-attention: at every scale the PVT (global, transformer)
       features attend to the GCADSN (local, CNN) features and vice versa,
       instead of the two tracks being blindly concatenated.
    3. Adaptive fusion: learned, input-dependent gates decide how much of
       each track (per scale) and each scale (overall) enters the final
       classifier.

    Each piece can be switched off, which gives the ablation ladder:

        scales=(7,),          use_cross_attention=False, fusion="concat"
                                    ~ the base paper's network
        scales=(28, 14, 7),   use_cross_attention=False, fusion="concat"
                                    + multi-scale
        scales=(28, 14, 7),   use_cross_attention=True,  fusion="concat"
                                    + cross-attention
        scales=(28, 14, 7),   use_cross_attention=True,  fusion="adaptive"
                                    full MSCAF-Net
    """

    def __init__(
        self,
        num_classes: int = 3,
        pretrained: bool = True,
        scales=(28, 14, 7),
        dim: int = 128,
        num_heads: int = 4,
        use_cross_attention: bool = True,
        fusion: str = "adaptive",
        dropout: float = 0.1
    ):
        super().__init__()

        assert fusion in ("adaptive", "concat")

        scales = sorted({int(s) for s in scales}, reverse=True)

        for s in scales:
            assert s in SCALE_MAP, f"unsupported scale {s}; choose from {sorted(SCALE_MAP)}"

        self.scales = scales
        self.use_cross_attention = use_cross_attention
        self.fusion = fusion

        # Attribute names `pvt` / `gcadsn` match the base network, so the
        # training script can give the pretrained backbone its own lr.
        self.pvt = PVTBackbone(pretrained=pretrained)
        self.gcadsn = GCADSNBackbone()

        pvt_channels = self.pvt.model.feature_info.channels()

        def project(in_channels):
            return nn.Sequential(
                nn.Conv2d(in_channels, dim, kernel_size=1, bias=False),
                nn.BatchNorm2d(dim)
            )

        self.pvt_proj = nn.ModuleDict()
        self.gcadsn_proj = nn.ModuleDict()
        self.attn_pvt = nn.ModuleDict()
        self.attn_gcadsn = nn.ModuleDict()
        self.track_fusion = nn.ModuleDict()

        for s in scales:

            pvt_idx, gcadsn_idx = SCALE_MAP[s]
            key = f"s{s}"

            self.pvt_proj[key] = project(pvt_channels[pvt_idx])
            self.gcadsn_proj[key] = project(GCADSN_CHANNELS[gcadsn_idx])

            if use_cross_attention:
                # PVT queries GCADSN: global features gain local detail
                self.attn_pvt[key] = CrossAttention(dim, num_heads, pos_size=s, dropout=dropout)
                # GCADSN queries PVT: local features gain global context
                self.attn_gcadsn[key] = CrossAttention(dim, num_heads, pos_size=s, dropout=dropout)

            if fusion == "adaptive":
                self.track_fusion[key] = AdaptiveFusion(dim, num_inputs=2)

        if fusion == "adaptive":
            self.scale_fusion = AdaptiveFusion(dim, num_inputs=len(scales))
            feature_dim = dim
        else:
            self.scale_fusion = None
            feature_dim = 2 * dim * len(scales)

        self.global_pool = nn.AdaptiveAvgPool2d(1)

        # Hook point for Grad-CAM: the fused map of the coarsest scale
        self.fusion_identity = nn.Identity()

        self.dropout = nn.Dropout(dropout)

        self.classifier = nn.Linear(feature_dim, num_classes)

    def forward(self, x, return_features=False):

        pvt_features = self.pvt(x)
        gcadsn_features = self.gcadsn(x)

        vectors = []
        fused_maps = {}

        for s in self.scales:

            pvt_idx, gcadsn_idx = SCALE_MAP[s]
            key = f"s{s}"

            p = self.pvt_proj[key](pvt_features[pvt_idx])
            g = self.gcadsn_proj[key](gcadsn_features[gcadsn_idx])

            if self.use_cross_attention:
                # Both directions use the *original* p and g
                p, g = self.attn_pvt[key](p, g), self.attn_gcadsn[key](g, p)

            if self.fusion == "adaptive":
                fused = self.track_fusion[key](p, g)
            else:
                fused = torch.cat([p, g], dim=1)

            if s == self.scales[-1]:
                fused = self.fusion_identity(fused)

            fused_maps[s] = fused

            vectors.append(torch.flatten(self.global_pool(fused), start_dim=1))

        if self.fusion == "adaptive":
            features = self.scale_fusion(*vectors)
        else:
            features = torch.cat(vectors, dim=1)

        logits = self.classifier(self.dropout(features))

        if return_features:

            return {
                "logits": logits,
                "pvt_features": pvt_features,
                "gcadsn_features": gcadsn_features,
                "fused": fused_maps,
                "features": features
            }

        return logits
