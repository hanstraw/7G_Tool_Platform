"""
LabelU YOLOv11s 预标注脚本

使用本地 YOLOv11s 模型对图片进行目标检测，
生成 LabelU 可导入的预标注 JSON 文件。

用法:
    python preannotate.py
    python preannotate.py --config config.yaml
    python preannotate.py --limit 10
    python preannotate.py --restart
"""

import argparse
import json
import os
import random
import re
import string
import sys
import time
from pathlib import Path
from typing import Any

import yaml
from PIL import Image
from tqdm import tqdm
from ultralytics import YOLO


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def log(message: str) -> None:
    tqdm.write(message)


def load_config(config_path: Path) -> dict[str, Any]:
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def iter_images(image_dir: Path):
    for path in sorted(image_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def format_seconds(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{seconds:02d}s"
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def random_id(length: int = 11) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def safe_filename_part(value: Any) -> str:
    text = str(value)
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("._-")
    return text or "unknown"


def resolve_output_json(project_dir: Path, config: dict[str, Any]) -> Path:
    configured = config["paths"].get("output_json")
    if configured:
        return (project_dir / configured).resolve()

    task_id = safe_filename_part(config.get("labelu", {}).get("task_id", "task"))
    weights_name = safe_filename_part(
        Path(config.get("model", {}).get("weights", "yolo")).stem
    )
    return (project_dir / "output" / f"labelu_yolo_{task_id}_{weights_name}.json").resolve()


def unique_output_json(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 10000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Cannot find available output filename near: {path}")


def path_for_checkpoint(project_dir: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_dir.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def read_checkpoint_meta(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    meta = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("__type") == "meta":
            meta.update(item)
    return meta


def resolve_run_output_json(
    project_dir: Path, config: dict[str, Any], checkpoint_jsonl: Path, restart: bool
) -> Path:
    base_path = resolve_output_json(project_dir, config)
    if not restart:
        meta = read_checkpoint_meta(checkpoint_jsonl)
        recorded_output = meta.get("output_json")
        if recorded_output:
            return (project_dir / recorded_output).resolve()
    return unique_output_json(base_path)


def load_checkpoint(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            if item.get("__type") == "meta":
                continue
            records[item["fileName"]] = item
    return records


def ensure_checkpoint_meta(
    path: Path, project_dir: Path, output_json: Path
) -> None:
    meta = read_checkpoint_meta(path)
    if meta.get("output_json"):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    item = {
        "__type": "meta",
        "output_json": path_for_checkpoint(project_dir, output_json),
        "output_json_name": output_json.name,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(item, ensure_ascii=False) + "\n")
        file.flush()
        os.fsync(file.fileno())


def append_checkpoint(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(item, ensure_ascii=False) + "\n")
        file.flush()
        os.fsync(file.fileno())


def append_failed(path: Path, item: dict[str, Any]) -> None:
    failed_path = path.with_name("failed.jsonl")
    failed_path.parent.mkdir(parents=True, exist_ok=True)
    with failed_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(item, ensure_ascii=False) + "\n")
        file.flush()
        os.fsync(file.fileno())


def write_output(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temp_path.replace(path)


def enrich_labelu_item(
    item: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    labelu_cfg = config.get("labelu", {})
    file_name = item["fileName"]
    task_id = labelu_cfg.get("task_id")
    upload_subdir = labelu_cfg.get("upload_subdir", "images_only")
    media_folder = labelu_cfg.get("media_folder", "/root/.local/share/labelu/media")

    enriched = dict(item)
    enriched.setdefault("folder", media_folder)
    if task_id is not None:
        enriched.setdefault(
            "url",
            f"/api/v1/tasks/attachment/upload/{task_id}/{upload_subdir}/{file_name}",
        )
    return enriched


def to_labelu_result(
    rects: list[dict[str, Any]], width: int, height: int, rotate: int
) -> dict[str, Any]:
    """将检测框列表转换为 LabelU 格式的标注结果"""
    rect_results = []
    for order, rect in enumerate(rects, start=1):
        rect_results.append(
            {
                "id": random_id(),
                "x": rect["x"],
                "y": rect["y"],
                "label": rect["label"],
                "width": rect["width"],
                "height": rect["height"],
                "order": order,
                "attributes": {},
            }
        )

    return {
        "width": width,
        "height": height,
        "rotate": rotate,
        "annotations": [
            {"toolName": "rectTool", "result": rect_results},
        ],
    }


def run_yolo_inference(
    yolo_model: YOLO,
    image_path: Path,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """使用 YOLO 模型对单张图片进行推理，返回检测框列表"""
    model_cfg = config["model"]
    class_mapping = config.get("class_mapping", {})
    min_confidence = float(config["run"].get("min_confidence", 0.25))
    max_rects = int(config["run"].get("max_rects", 20))

    # 运行推理
    results = yolo_model.predict(
        source=str(image_path),
        conf=float(model_cfg.get("confidence", 0.25)),
        iou=float(model_cfg.get("iou", 0.45)),
        imgsz=int(model_cfg.get("imgsz", 1920)),
        device=model_cfg.get("device", "cpu"),
        verbose=False,
    )

    if not results or len(results) == 0:
        return []

    result = results[0]
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return []

    # 获取原始图片尺寸
    img_width = result.orig_shape[1]
    img_height = result.orig_shape[0]

    rects = []
    for i in range(len(boxes)):
        conf = float(boxes.conf[i])
        if conf < min_confidence:
            continue

        cls_id = int(boxes.cls[i])
        label = class_mapping.get(cls_id)
        if label is None:
            # 未映射的类别，跳过
            continue

        # xyxy 格式: [x1, y1, x2, y2] 像素坐标
        x1, y1, x2, y2 = boxes.xyxy[i].tolist()

        # 确保坐标在图片范围内
        x1 = max(0.0, min(x1, img_width))
        y1 = max(0.0, min(y1, img_height))
        x2 = max(0.0, min(x2, img_width))
        y2 = max(0.0, min(y2, img_height))

        w = x2 - x1
        h = y2 - y1
        if w < 1.0 or h < 1.0:
            continue

        rects.append(
            {
                "label": label,
                "x": round(x1, 2),
                "y": round(y1, 2),
                "width": round(w, 2),
                "height": round(h, 2),
                "confidence": round(conf, 4),
            }
        )

        if len(rects) >= max_rects:
            break

    # 按置信度降序排列
    rects.sort(key=lambda r: r["confidence"], reverse=True)
    return rects


def process_image(
    yolo_model: YOLO,
    image_path: Path,
    config: dict[str, Any],
) -> tuple[dict[str, Any], int, float]:
    """处理单张图片，返回 (LabelU item, 框数量, 耗时)"""
    started_at = time.time()

    with Image.open(image_path) as image:
        width, height = image.size

    rects = run_yolo_inference(yolo_model, image_path, config)
    labelu_result = to_labelu_result(
        rects, width, height, config["labelu"]["rotate"]
    )
    item = enrich_labelu_item(
        {
            "fileName": image_path.name,
            "result": json.dumps(labelu_result, ensure_ascii=False),
        },
        config,
    )
    return item, len(rects), time.time() - started_at


def main() -> None:
    parser = argparse.ArgumentParser(
        description="使用 YOLOv11s 模型生成 LabelU 预标注 JSON"
    )
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--limit", type=int, default=None, help="限制处理图片数量")
    parser.add_argument(
        "--restart",
        action="store_true",
        help="清空 checkpoint 从头开始",
    )
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parent
    config = load_config((project_dir / args.config).resolve())
    image_dir = (project_dir / config["paths"]["image_dir"]).resolve()
    checkpoint_jsonl = (project_dir / config["paths"]["checkpoint_jsonl"]).resolve()
    limit = args.limit if args.limit is not None else config["run"].get("limit")

    restart = args.restart or config["run"].get("overwrite_checkpoint", False)
    if restart:
        checkpoint_jsonl.unlink(missing_ok=True)

    output_json = resolve_run_output_json(
        project_dir, config, checkpoint_jsonl, restart
    )
    ensure_checkpoint_meta(checkpoint_jsonl, project_dir, output_json)

    # 加载 YOLO 模型
    weights_path = (project_dir / config["model"]["weights"]).resolve()
    log(f"加载模型: {weights_path}")
    if not weights_path.exists():
        log(f"错误: 模型权重文件不存在: {weights_path}")
        sys.exit(1)

    yolo_model = YOLO(str(weights_path))
    log(f"模型加载完成")

    # 打印类别映射
    class_mapping = config.get("class_mapping", {})
    log(f"类别映射 ({len(class_mapping)} 个类别):")
    for cls_id, label in sorted(class_mapping.items()):
        log(f"  {cls_id}: {label}")

    all_images = list(iter_images(image_dir))
    done = {
        file_name: enrich_labelu_item(item, config)
        for file_name, item in load_checkpoint(checkpoint_jsonl).items()
    }
    output = list(done.values())
    pending_images = [path for path in all_images if path.name not in done]
    processed = 0
    started_at = time.time()

    log("")
    log(f"图片目录: {image_dir}")
    log(f"输出文件: {output_json}")
    log(f"总图片数: {len(all_images)}")
    log(f"已完成: {len(done)}")
    log(f"待处理: {len(pending_images)}")
    if limit is not None:
        log(f"本次最多处理: {limit}")
    log(f"推理置信度: {config['model'].get('confidence', 0.25)}")
    log(f"推理图片尺寸: {config['model'].get('imgsz', 1920)}")
    log(f"设备: {config['model'].get('device', 'cpu')}")
    log("")

    batch_images = pending_images[:limit] if limit is not None else pending_images

    progress = tqdm(
        total=len(all_images),
        initial=len(done),
        unit="张",
        desc="预标注进度",
        dynamic_ncols=True,
        file=sys.stdout,
    )

    total_boxes = 0
    try:
        for offset, image_path in enumerate(batch_images, start=1):
            current_index = len(done) + offset
            try:
                item, box_count, image_elapsed = process_image(
                    yolo_model, image_path, config
                )
            except Exception as exc:
                elapsed_text = format_seconds(time.time() - started_at)
                log(
                    f"[{current_index}/{len(all_images)}] 失败: {image_path.name}，"
                    f"总耗时 {elapsed_text}，错误: {exc}"
                )
                append_failed(
                    checkpoint_jsonl,
                    {
                        "fileName": image_path.name,
                        "error": str(exc),
                        "elapsed": elapsed_text,
                        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    },
                )
                processed += 1
                progress.update(1)
                progress.set_postfix_str(f"失败跳过 {image_path.name}")
                continue

            append_checkpoint(checkpoint_jsonl, item)
            output.append(item)
            write_output(output_json, output)
            processed += 1
            total_boxes += box_count
            elapsed = time.time() - started_at
            avg = elapsed / processed
            remaining_in_batch = max(0, len(batch_images) - processed)
            eta = avg * remaining_in_batch
            log(
                f"[{current_index}/{len(all_images)}] 完成: {image_path.name}，"
                f"框 {box_count} 个，单张 {format_seconds(image_elapsed)}，"
                f"本次 {processed}/{len(batch_images)}，累计 {len(output)}，"
                f"预计剩余 {format_seconds(eta)}"
            )
            progress.update(1)
            progress.set_postfix_str(
                f"本次 {processed}/{len(batch_images)} | "
                f"累计 {len(output)} | ETA {format_seconds(eta)}"
            )

    except KeyboardInterrupt:
        log("\n收到 Ctrl+C，正在保存已完成结果并停止...")
        write_output(output_json, output)
        progress.close()
        log(f"已保存: {output_json}")
        log("下次直接运行 python .\\preannotate.py 会从 checkpoint 继续。")
        os._exit(130)
    finally:
        progress.close()

    write_output(output_json, output)
    elapsed_total = time.time() - started_at
    log("")
    log(f"完成! 输出文件: {output_json}")
    log(f"总记录数: {len(output)}")
    log(f"本次处理: {processed} 张")
    log(f"本次检测框总数: {total_boxes}")
    log(f"总耗时: {format_seconds(elapsed_total)}")
    if processed > 0:
        log(f"平均每张: {format_seconds(elapsed_total / processed)}")


if __name__ == "__main__":
    main()
