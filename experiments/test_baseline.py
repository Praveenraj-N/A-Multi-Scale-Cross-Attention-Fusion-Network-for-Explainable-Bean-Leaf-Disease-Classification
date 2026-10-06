import torch

from models.baseline import BasePVTGCADSN


def main():

    print("===================================")
    print("       Baseline Model Test")
    print("===================================")

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )

    print("\nDevice:", device)

    # Create model
    model = BasePVTGCADSN(
        num_classes=3,
        pretrained=True
    )

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

        output = model(
            x,
            return_features=True
        )

    print("\nPVT feature shapes:")

    for i, feature in enumerate(
        output["pvt_features"]
    ):

        print(
            f"Stage {i + 1}: {feature.shape}"
        )

    print("\nGCADSN feature shapes:")

    for i, feature in enumerate(
        output["gcadsn_features"]
    ):

        print(
            f"Stage {i + 1}: {feature.shape}"
        )

    print("\nFused feature shape:")

    print(
        output["fused"].shape
    )

    print("\nLogits shape:")

    print(
        output["logits"].shape
    )

    print("\nLogits:")

    print(
        output["logits"]
    )

    print("\n===================================")
    print("       Baseline Test Done")
    print("===================================")


if __name__ == "__main__":
    main()