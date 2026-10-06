from pathlib import Path
from PIL import Image
from collections import Counter


DATASET_DIR = Path("data/beans")

SPLITS = ["train", "validation", "test"]

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png"
}


def get_images(folder):
    """Return all image files inside a folder."""
    return [
        path
        for path in folder.rglob("*")
        if path.suffix.lower() in IMAGE_EXTENSIONS
    ]


def check_split(split_name):

    split_dir = DATASET_DIR / split_name

    print(f"\n========== {split_name.upper()} ==========")

    if not split_dir.exists():
        print(f"ERROR: {split_dir} does not exist.")
        return

    total = 0

    class_counts = Counter()

    corrupted = []

    image_sizes = Counter()

    color_modes = Counter()

    for class_dir in sorted(split_dir.iterdir()):

        if not class_dir.is_dir():
            continue

        images = get_images(class_dir)

        class_name = class_dir.name

        class_counts[class_name] = len(images)

        total += len(images)

        for image_path in images:

            try:

                with Image.open(image_path) as image:

                    image.verify()

                with Image.open(image_path) as image:

                    image_sizes[image.size] += 1
                    color_modes[image.mode] += 1

            except Exception:

                corrupted.append(
                    str(image_path)
                )

    print("Class distribution:")

    for class_name, count in class_counts.items():

        print(
            f"  {class_name}: {count}"
        )

    print(f"\nTotal images: {total}")

    print("\nImage sizes:")

    for size, count in image_sizes.items():

        print(
            f"  {size}: {count}"
        )

    print("\nColor modes:")

    for mode, count in color_modes.items():

        print(
            f"  {mode}: {count}"
        )

    print(
        f"\nCorrupted images: {len(corrupted)}"
    )

    if corrupted:

        print("\nCorrupted files:")

        for path in corrupted:

            print(
                f"  {path}"
            )


def main():

    print("===================================")
    print("       iBean Dataset Checker")
    print("===================================")

    if not DATASET_DIR.exists():

        print(
            f"\nERROR: Dataset folder not found:"
            f"\n{DATASET_DIR}"
        )

        return

    for split in SPLITS:

        check_split(split)

    print("\n===================================")
    print("             DONE")
    print("===================================")


if __name__ == "__main__":

    main()