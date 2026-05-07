import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any

import yaml


def safe_filename_part(value: Any) -> str:
    text = str(value)
    text = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text)
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("._-") or "unknown"


def resolve_output_json(project_dir: Path, config: dict[str, Any]) -> Path:
    configured = config["paths"].get("output_json")
    if configured:
        return (project_dir / configured).resolve()

    task_id = safe_filename_part(config.get("labelu", {}).get("task_id", "task"))
    model_name = safe_filename_part(config.get("model", {}).get("model", "model"))
    return (project_dir / "output" / f"labelu_{task_id}_{model_name}.json").resolve()


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def enrich_item(item: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    labelu_cfg = config.get("labelu", {})
    task_id = labelu_cfg.get("task_id")
    upload_subdir = labelu_cfg.get("upload_subdir", "images_only")
    media_folder = labelu_cfg.get("media_folder", "/root/.local/share/labelu/media")

    if not item.get("fileName"):
        raise ValueError(f"缺少 fileName，无法补 url: {item}")

    file_name = item["fileName"]
    fixed = dict(item)
    fixed["folder"] = fixed.get("folder") or media_folder
    if not fixed.get("url"):
        if task_id is None:
            raise ValueError("config.yaml 的 labelu.task_id 为空，无法补 url")
        fixed["url"] = f"/api/v1/tasks/attachment/upload/{task_id}/{upload_subdir}/{file_name}"
    return fixed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--input", default=None, help="默认使用 config.paths.output_json")
    parser.add_argument("--output", default=None, help="默认原地覆盖 input")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parent
    config = load_config((project_dir / args.config).resolve())
    input_path = Path(args.input) if args.input else resolve_output_json(project_dir, config)
    output_path = Path(args.output) if args.output else input_path

    data = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("预标注 JSON 顶层必须是数组")

    fixed = [enrich_item(item, config) for item in data]

    if output_path == input_path and not args.no_backup:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = input_path.with_suffix(input_path.suffix + f".bak_{timestamp}")
        shutil.copy2(input_path, backup_path)
        print(f"已备份: {backup_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(fixed, ensure_ascii=False, indent=2), encoding="utf-8")

    missing_url = sum(1 for item in fixed if not item.get("url"))
    missing_folder = sum(1 for item in fixed if not item.get("folder"))
    print(f"已修复: {output_path}")
    print(f"记录数: {len(fixed)}")
    print(f"缺少 url: {missing_url}")
    print(f"缺少 folder: {missing_folder}")


if __name__ == "__main__":
    main()
