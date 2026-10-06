from torchvision import datasets
from torch.utils.data import DataLoader

from preprocessing.transforms import (
    get_train_transforms,
    get_eval_transforms
)


def create_dataloaders(
    data_dir="data/beans",
    augmented_dir=None,
    image_size=224,
    batch_size=8,
    num_workers=0,
    original_validation=False
):
    """
    If `augmented_dir` is given, train/validation are loaded from the
    offline-augmented copies (see preprocessing/augment_dataset.py,
    which reproduces the paper's fixed-parameter augmentation pipeline)
    with no further online augmentation applied. The test set always
    comes from `data_dir`, unaugmented, as in the paper.

    If `original_validation` is True, validation is always read from the
    original (unaugmented) `data_dir` split even when training on the
    augmented copies. The augmented validation set is ~9 near-duplicate
    copies of the same 133 photos, so it scores near-perfect from epoch 1
    and is a poor signal for picking a checkpoint.
    """

    train_root = f"{augmented_dir}/train" if augmented_dir else f"{data_dir}/train"
    validation_root = (
        f"{augmented_dir}/validation"
        if augmented_dir and not original_validation
        else f"{data_dir}/validation"
    )

    train_transform = get_eval_transforms(image_size) if augmented_dir else get_train_transforms(image_size)

    # Training dataset
    train_dataset = datasets.ImageFolder(
        root=train_root,
        transform=train_transform
    )

    # Validation dataset
    validation_dataset = datasets.ImageFolder(
        root=validation_root,
        transform=get_eval_transforms(image_size)
    )

    # Test dataset
    test_dataset = datasets.ImageFolder(
        root=f"{data_dir}/test",
        transform=get_eval_transforms(image_size)
    )

    # DataLoaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True
    )

    validation_loader = DataLoader(
        validation_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True
    )

    return (
        train_loader,
        validation_loader,
        test_loader,
        train_dataset,
        validation_dataset,
        test_dataset
    )