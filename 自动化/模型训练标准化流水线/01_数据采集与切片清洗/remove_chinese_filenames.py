import re
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
IMAGE_DIR = ROOT_DIR / "images"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
CHINESE_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def clean_stem(stem: str) -> str:
    stem = CHINESE_RE.sub("", stem)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip("._-")
    return stem or "image"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    index = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def iter_images(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def main() -> None:
    renamed = 0
    skipped = 0

    for image_path in sorted(iter_images(IMAGE_DIR)):
        new_name = f"{clean_stem(image_path.stem)}{image_path.suffix.lower()}"
        if new_name == image_path.name:
            skipped += 1
            continue

        new_path = unique_path(image_path.with_name(new_name))
        image_path.rename(new_path)
        renamed += 1
        print(f"{image_path.name} -> {new_path.name}")

    print(f"\n完成: 重命名 {renamed} 个，跳过 {skipped} 个")


if __name__ == "__main__":
    main()
