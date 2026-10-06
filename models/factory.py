from models.baseline import BasePVTGCADSN
from models.mscaf_net import MSCAFNet

MODES = ("fused", "pvt", "gcadsn", "mscaf")


def build_model(mode, num_classes=3, pretrained=True, mscaf_kwargs=None):
    """Builds the network for a training/evaluation `mode`.

    fused / pvt / gcadsn  -> the base paper's network (and its ablations)
    mscaf                 -> MSCAF-Net; `mscaf_kwargs` are its constructor
                             options (scales, dim, num_heads,
                             use_cross_attention, fusion, dropout)
    """

    assert mode in MODES, f"unknown mode {mode}"

    if mode == "mscaf":
        return MSCAFNet(
            num_classes=num_classes,
            pretrained=pretrained,
            **(mscaf_kwargs or {})
        )

    return BasePVTGCADSN(
        num_classes=num_classes,
        pretrained=pretrained,
        mode=mode
    )
