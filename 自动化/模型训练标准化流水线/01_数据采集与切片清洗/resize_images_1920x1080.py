from pathlib import Path

from PIL import Image, ImageOps


ROOT_DIR = Path(__file__).resolve().parent
TARGET_FOLDERS = ["cc2", "lxl2", "sy2", "wly2", "ymt2", "yyj2", "zx2", "zzx2"]
TARGET_SIZE = (1920, 1080)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def iter_images(root: Path):
    for folder_name in TARGET_FOLDERS:
        folder_path = root / folder_name
        if not folder_path.exists():
            continue
        for path in folder_path.rglob("*"):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                yield path


def resize_image(path: Path) -> bool:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image)
        if image.size != TARGET_SIZE:
            image = image.resize(TARGET_SIZE, Image.Resampling.LANCZOS)

        if path.suffix.lower() in {".jpg", ".jpeg"}:
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            image.save(path, quality=95, subsampling=0, optimize=True)
        else:
            image.save(path, optimize=True)

    return True


def main() -> None:
    total = 0
    resized = 0
    failed = 0

    for image_path in iter_images(ROOT_DIR):
        total += 1
        try:
            with Image.open(image_path) as image:
                original_size = image.size
            resize_image(image_path)
            if original_size != TARGET_SIZE:
                resized += 1
            print(f"OK {image_path} {original_size[0]}x{original_size[1]} -> {TARGET_SIZE[0]}x{TARGET_SIZE[1]}")
        except Exception as exc:
            failed += 1
            print(f"FAILED {image_path}: {exc}")

    print(f"\n完成: 共 {total} 张，调整 {resized} 张，失败 {failed} 张")


if __name__ == "__main__":
    main()
