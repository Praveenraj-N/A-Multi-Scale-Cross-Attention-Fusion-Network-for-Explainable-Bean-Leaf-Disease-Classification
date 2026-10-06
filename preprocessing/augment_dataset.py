"""Offline data augmentation matching the base paper's Section III-A.2.

The paper expands the dataset by generating fixed-parameter augmented
copies (not random per-epoch augmentation): rotation by 30 and 60 degrees
in both directions, horizontal/vertical flipping, and horizontal/vertical
translation, applied to the train and validation sets. The test set is
left untouched.

This produces 9 versions per source image (the original + 8 named
augmentations) under data/beans_augmented/{train,validation}/<class>/.
"""

import os
import cv2
import numpy as np

SOURCE_DIR = "data/beans"
OUTPUT_DIR = "data/beans_augmented"

SPLITS = ["train", "validation"]

IMAGE_SIZE = 224

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _warp(image, matrix):
    height, width = image.shape[:2]
    return cv2.warpAffine(
        image,
        matrix,
        (width, height),
        borderMode=cv2.BORDER_REFLECT
    )


def rotate(image, angle_degrees):
    height, width = image.shape[:2]
    center = (width / 2, height / 2)
    matrix = cv2.getRotationMatrix2D(center, angle_degrees, 1.0)
    return _warp(image, matrix)


def translate(image, dx, dy):
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    return _warp(image, matrix)


def generate_augmentations(image):
    height, width = image.shape[:2]
    shift = 0.15 * min(height, width)

    return {
        "orig": image,
        "rot30cw": rotate(image, -30),
        "rot30ccw": rotate(image, 30),
        "rot60cw": rotate(image, -60),
        "rot60ccw": rotate(image, 60),
        "hflip": cv2.flip(image, 1),
        "vflip": cv2.flip(image, 0),
        "htrans": translate(image, shift, 0),
        "vtrans": translate(image, 0, shift),
    }


def main():

    for split in SPLITS:

        source_split_dir = os.path.join(SOURCE_DIR, split)
        output_split_dir = os.path.join(OUTPUT_DIR, split)

        class_names = sorted(
            d for d in os.listdir(source_split_dir)
            if os.path.isdir(os.path.join(source_split_dir, d))
        )

        total_written = 0

        for class_name in class_names:

            source_class_dir = os.path.join(source_split_dir, class_name)
            output_class_dir = os.path.join(output_split_dir, class_name)

            os.makedirs(output_class_dir, exist_ok=True)

            image_files = [
                f for f in os.listdir(source_class_dir)
                if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
            ]

            for filename in image_files:

                stem = os.path.splitext(filename)[0]

                image = cv2.imread(os.path.join(source_class_dir, filename))
                image = cv2.resize(image, (IMAGE_SIZE, IMAGE_SIZE))

                for tag, augmented in generate_augmentations(image).items():

                    out_path = os.path.join(
                        output_class_dir,
                        f"{stem}_{tag}.jpg"
                    )

                    cv2.imwrite(out_path, augmented)

                    total_written += 1

        print(f"{split}: wrote {total_written} images "
              f"({len(class_names)} classes) -> {output_split_dir}")


if __name__ == "__main__":
    main()
