import argparse
import csv
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import imagehash
import yaml
from PIL import Image, UnidentifiedImageError


SCRIPT_DIR = Path(__file__).resolve().parent
MODE_OUTPUT = "output"
MODE_DELETE = "delete"


@dataclass
class Config:
    source_folder: Path = SCRIPT_DIR
    mode: str = MODE_OUTPUT
    output_folder: str = "dedup_output"
    threshold: int = 2
    recursive: bool = True
    dry_run: bool = False
    hash_size: int = 8
    image_extensions: tuple[str, ...] = (
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".webp",
        ".gif",
        ".tif",
        ".tiff",
    )
    report_file: str = "dedup_report.csv"


def resolve_source_folder(raw_source: str | None) -> Path:
    if not raw_source:
        return SCRIPT_DIR

    source_path = Path(raw_source).expanduser()
    if source_path.is_absolute():
        return source_path
    return (SCRIPT_DIR / source_path).resolve()


def load_config(config_path: Path) -> Config:
    if not config_path.exists():
        raise FileNotFoundError(f"找不到配置文件: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    mode = str(raw.get("mode", MODE_OUTPUT)).lower()
    if mode not in {MODE_OUTPUT, MODE_DELETE}:
        raise ValueError("mode 只能是 output 或 delete")

    return Config(
        source_folder=resolve_source_folder(raw.get("source_folder")),
        mode=mode,
        output_folder=raw.get("output_folder", Config.output_folder),
        threshold=int(raw.get("threshold", Config.threshold)),
        recursive=bool(raw.get("recursive", Config.recursive)),
        dry_run=bool(raw.get("dry_run", Config.dry_run)),
        hash_size=int(raw.get("hash_size", 8)),
        image_extensions=tuple(ext.lower() for ext in raw.get("image_extensions", Config.image_extensions)),
        report_file=raw.get("report_file", "dedup_report.csv"),
    )


def iter_image_files(config: Config, output_dir: Path) -> Iterable[Path]:
    pattern = "**/*" if config.recursive else "*"
    output_dir = output_dir.resolve()

    for path in config.source_folder.glob(pattern):
        if not path.is_file():
            continue
        if path.suffix.lower() not in config.image_extensions:
            continue
        try:
            resolved_path = path.resolve()
            if resolved_path == output_dir or output_dir in resolved_path.parents:
                continue
        except OSError:
            pass
        yield path


def count_file_extensions(source_folder: Path, output_dir: Path, recursive: bool) -> dict[str, int]:
    pattern = "**/*" if recursive else "*"
    counts: dict[str, int] = {}
    output_dir = output_dir.resolve()

    for path in source_folder.glob(pattern):
        if not path.is_file():
            continue
        try:
            resolved_path = path.resolve()
            if resolved_path == output_dir or output_dir in resolved_path.parents:
                continue
        except OSError:
            pass

        extension = path.suffix.lower() or "<无后缀>"
        counts[extension] = counts.get(extension, 0) + 1

    return counts


def unique_target_path(target_dir: Path, original_path: Path, source_folder: Path) -> Path:
    try:
        relative_path = original_path.relative_to(source_folder)
    except ValueError:
        relative_path = Path(original_path.name)

    target_path = target_dir / relative_path
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if not target_path.exists():
        return target_path

    stem = target_path.stem
    suffix = target_path.suffix
    parent = target_path.parent
    index = 1
    while True:
        candidate = parent / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def calculate_phash(image_path: Path, hash_size: int):
    with Image.open(image_path) as img:
        return imagehash.phash(img, hash_size=hash_size)


def write_report(report_path: Path, rows: list[dict]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "file",
        "status",
        "matched_file",
        "distance",
        "output_file",
        "error",
    ]
    with report_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def deduplicate_images(config: Config) -> None:
    source_folder = config.source_folder.resolve()
    if not source_folder.exists() or not source_folder.is_dir():
        raise NotADirectoryError(f"源文件夹不存在或不是文件夹: {source_folder}")

    config.source_folder = source_folder
    output_dir = (source_folder / config.output_folder).resolve()
    report_path = output_dir / config.report_file

    if not config.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    unique_images = []
    report_rows = []
    scanned_count = 0
    duplicate_count = 0
    deleted_count = 0
    error_count = 0

    mode_name = "输出去重后的文件夹" if config.mode == MODE_OUTPUT else "删除原目录中的重复图片"
    print(f"启动扫描: {source_folder}")
    print(f"模式: {config.mode} ({mode_name})")
    print(f"输出/报告目录: {output_dir}")
    print(f"执行方式: {'预演，不复制或删除文件' if config.dry_run else '实际执行'}")
    print(f"递归扫描: {'是' if config.recursive else '否'}")
    print(f"阈值 threshold: {config.threshold}")

    for image_path in iter_image_files(config, output_dir):
        scanned_count += 1
        try:
            current_hash = calculate_phash(image_path, config.hash_size)
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            error_count += 1
            report_rows.append(
                {
                    "file": str(image_path),
                    "status": "error",
                    "matched_file": "",
                    "distance": "",
                    "output_file": "",
                    "error": str(exc),
                }
            )
            print(f"跳过异常图片: {image_path} ({exc})")
            continue

        matched_path = None
        matched_distance = None
        for saved_hash, saved_path, _saved_output in unique_images:
            distance = current_hash - saved_hash
            if distance <= config.threshold:
                matched_path = saved_path
                matched_distance = distance
                break

        if matched_path is not None:
            duplicate_count += 1
            status = "duplicate_skipped"
            if config.mode == MODE_DELETE:
                status = "duplicate_delete_dry_run" if config.dry_run else "duplicate_deleted"
                if not config.dry_run:
                    image_path.unlink()
                    deleted_count += 1

            report_rows.append(
                {
                    "file": str(image_path),
                    "status": status,
                    "matched_file": str(matched_path),
                    "distance": matched_distance,
                    "output_file": "",
                    "error": "",
                }
            )
            action_text = "预演删除" if config.mode == MODE_DELETE and config.dry_run else "删除" if config.mode == MODE_DELETE else "跳过"
            print(f"{action_text}重复: {image_path.name} -> {matched_path.name}，距离 {matched_distance}")
            continue

        output_path = unique_target_path(output_dir, image_path, source_folder)
        unique_images.append((current_hash, image_path, output_path))
        report_rows.append(
            {
                "file": str(image_path),
                "status": "kept",
                "matched_file": "",
                "distance": "",
                "output_file": str(output_path) if config.mode == MODE_OUTPUT else "",
                "error": "",
            }
        )

    if config.mode == MODE_OUTPUT and not config.dry_run:
        for _saved_hash, image_path, output_path in unique_images:
            shutil.copy2(str(image_path), str(output_path))

    if report_rows:
        write_report(report_path, report_rows)

    print("")
    print("去重完成")
    print(f"扫描图片: {scanned_count}")
    print(f"保留图片: {len(unique_images)}")
    print(f"重复图片: {duplicate_count}")
    if config.mode == MODE_DELETE:
        print(f"已删除重复图片: {deleted_count}")
    print(f"异常文件: {error_count}")
    if scanned_count == 0:
        extension_counts = count_file_extensions(source_folder, output_dir, config.recursive)
        if extension_counts:
            print("")
            print("未找到可处理的图片文件。当前目录中的文件后缀统计:")
            for extension, count in sorted(extension_counts.items(), key=lambda item: item[1], reverse=True):
                print(f"  {extension}: {count}")
            print(f"当前配置允许的图片后缀: {', '.join(config.image_extensions)}")
        else:
            print("")
            print("未找到任何可扫描的文件。")
    if report_rows:
        print(f"报告文件: {report_path}")
    if config.mode == MODE_OUTPUT and not config.dry_run:
        print(f"去重后的图片已输出到: {output_dir}")
        print("原目录中的图片没有被移动、删除或修改。")
    if config.mode == MODE_DELETE and not config.dry_run:
        print("删除模式已执行：原目录中的重复图片已删除，保留图片未修改。")


def parse_args() -> argparse.Namespace:
    default_config = SCRIPT_DIR / "config.yaml"
    parser = argparse.ArgumentParser(description="使用 pHash 对本地图片文件夹去重，支持输出去重文件夹或删除重复图片。")
    parser.add_argument("-c", "--config", default=str(default_config), help="配置文件路径，默认使用脚本同目录下的 config.yaml")
    parser.add_argument("--source", help="覆盖配置中的 source_folder")
    parser.add_argument("--mode", choices=[MODE_OUTPUT, MODE_DELETE], help="运行模式：output 输出去重文件夹；delete 删除重复图片")
    parser.add_argument("--threshold", type=int, help="覆盖配置中的 threshold")
    parser.add_argument("--dry-run", action="store_true", help="只预演，不复制或删除文件")
    parser.add_argument("--copy", action="store_true", help="兼容旧参数，等同于 --mode output")
    parser.add_argument("--delete", action="store_true", help="等同于 --mode delete，删除原目录中的重复图片")
    parser.add_argument("--recursive", action="store_true", help="递归扫描子文件夹")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(Path(args.config))

    if args.source:
        config.source_folder = Path(args.source).expanduser()
    if args.mode:
        config.mode = args.mode
    if args.copy:
        config.mode = MODE_OUTPUT
    if args.delete:
        config.mode = MODE_DELETE
    if args.threshold is not None:
        config.threshold = args.threshold
    if args.dry_run:
        config.dry_run = True
    if args.recursive:
        config.recursive = True

    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"启动时间: {started_at}")
    deduplicate_images(config)


if __name__ == "__main__":
    main()
