import torch
import torch.nn as nn
import timm


class PVTBackbone(nn.Module):

    def __init__(
        self,
        model_name="pvt_v2_b2.in1k",
        pretrained=True
    ):
        super().__init__()

        self.model = timm.create_model(
            model_name,
            pretrained=pretrained,
            features_only=True,
            out_indices=(0, 1, 2, 3)
        )

    def forward(self, x):

        features = self.model(x)

        return features