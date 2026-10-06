from preprocessing.dataset import create_dataloaders


def main():

    print("===================================")
    print("     Preprocessing Pipeline Test")
    print("===================================")

    (
        train_loader,
        validation_loader,
        test_loader,
        train_dataset,
        validation_dataset,
        test_dataset
    ) = create_dataloaders(
        data_dir="data/beans",
        image_size=224,
        batch_size=8,
        num_workers=0
    )

    print("\nDataset sizes:")
    print("Train:", len(train_dataset))
    print("Validation:", len(validation_dataset))
    print("Test:", len(test_dataset))

    # Get one batch from training data
    images, labels = next(iter(train_loader))

    print("\nBatch information:")
    print("Image shape:", images.shape)
    print("Label shape:", labels.shape)

    print("\nImage information:")
    print("Data type:", images.dtype)
    print("Minimum value:", images.min().item())
    print("Maximum value:", images.max().item())

    print("\nLabels in batch:", labels.tolist())

    print("\n===================================")
    print("       Preprocessing Test Done")
    print("===================================")


if __name__ == "__main__":
    main()