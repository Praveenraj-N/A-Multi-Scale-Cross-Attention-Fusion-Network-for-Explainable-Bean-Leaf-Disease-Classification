import torch

from models.gcadsn import GCADSNBackbone


def main():

    print("===================================")
    print("         GCADSN Test")
    print("===================================")

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    print("\nDevice:", device)

    model = GCADSNBackbone()

    model = model.to(device)

    # Dummy input
    x = torch.randn(
        1,
        3,
        224,
        224
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
    print("         GCADSN Test Done")
    print("===================================")


if __name__ == "__main__":
    main()