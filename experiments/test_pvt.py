import torch

from models.pvt import PVTBackbone


def main():

    print("===================================")
    print("         PVT v2 Test")
    print("===================================")

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    print("\nDevice:", device)

    model = PVTBackbone(
        model_name="pvt_v2_b2.in1k",
        pretrained=True
    )

    model = model.to(device)

    # Create a dummy input
    x = torch.randn(
        1, 3, 224, 224
    ).to(device)

    print("\nInput shape:", x.shape)

    # Forward pass
    with torch.no_grad():

        features = model(x)

    print("\nNumber of feature maps:", len(features))

    print("\nFeature map shapes:")

    for i, feature in enumerate(features):

        print(
            f"Stage {i + 1}: {feature.shape}"
        )

    print("\n===================================")
    print("           PVT Test Done")
    print("===================================")


if __name__ == "__main__":
    main()