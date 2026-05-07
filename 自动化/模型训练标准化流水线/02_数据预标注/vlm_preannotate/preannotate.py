import argparse
import base64
import io
import json
import os
import random
import re
import string
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

import requests
import yaml
from PIL import Image
from tqdm import tqdm


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
REQUIRED_TAGS = ["sceneType", "lighting", "weather", "quality", "angle", "source"]


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


def summarize_text(text: str, max_chars: int = 1000) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def random_id(length: int = 11) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def get_mode(config: dict[str, Any]) -> str:
    return config.get("mode") or config.get("run", {}).get("mode", "global_tags_only")


def image_to_data_url(path: Path, request_image_cfg: dict[str, Any]) -> tuple[str, int, int]:
    configured_width = request_image_cfg.get("width")
    configured_height = request_image_cfg.get("height")
    quality = int(request_image_cfg.get("quality", 85))

    with Image.open(path) as image:
        image = image.convert("RGB")
        original_width, original_height = image.size
        if configured_width and configured_height:
            target_width = int(configured_width)
            target_height = int(configured_height)
            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        else:
            target_width = original_width
            target_height = original_height
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True)

    data = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{data}", target_width, target_height


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    return json.loads(text)


def build_prompt(config: dict[str, Any], image_path: Path, request_width: int, request_height: int) -> str:
    rect_labels = "\n".join(f"- {item['value']}: {item['name']}" for item in config["rect_labels"])
    tag_options = json.dumps(config["tag_options"], ensure_ascii=False, indent=2)
    max_rects = config["run"].get("max_rects", 12)
    min_confidence = config["run"].get("min_confidence", 0.75)
    mode = get_mode(config)
    if mode == "global_tags_only":
        return f"""
You are a strict LabelU pre-annotation assistant.

Return only one compact JSON object. No markdown. No explanation.

Image file: {image_path.name}

Task:
- Only classify the whole image using the required global tags.
- Do not detect objects.
- Do not draw boxes.
- Use visible evidence from the image. Do not infer beyond the image.

Allowed tag values:
{tag_options}

Output schema:
{{
  "tags": {{
    "sceneType": "one allowed value",
    "lighting": "one allowed value",
    "weather": "one allowed value",
    "quality": "one allowed value",
    "angle": "one allowed value",
    "source": "cameraCapture"
  }}
}}

Tag decision hints:
- sceneType: choose the closest road/street scene type.
- lighting: judge daylight, dusk, night lighting, backlight, or heavy shadow.
- weather: choose visible weather only; use sunny/cloudy when no rain/fog/snow/dust is visible.
- quality: judge image clarity/exposure/occlusion/motion blur.
- angle: choose eyeLevel/topView/lowAngle/obliqueView/aerialView based on camera viewpoint.
- source: use cameraCapture unless the image is clearly synthetic, manually photographed, or web-collected.
""".strip()
    else:
        detection_instructions = f"""
Mode: boxes_and_tags
- Detect non-fixed street-vendor occupation in roadsides, sidewalks, alleys, plazas, village roads, school areas, and commercial streets.
- High precision is more important than recall. If a human annotator would need review, do not draw that box.
- First decide whether there is clear selling behavior or a clear temporary selling setup. If not, output no rectangles.

Allowed rectangle labels:
{rect_labels}
""".strip()
    return f"""
You are a strict LabelU pre-annotation assistant for street occupation / street-vendor scenes.

Return only one compact JSON object. No markdown. No explanation.

Image file: {image_path.name}

Task:
{detection_instructions}

Also classify the whole image using exactly one value for each required tag.
Allowed tag values:
{tag_options}

Output schema:
{{
  "rects": [
    {{
      "label": "one allowed rect label value",
      "x": 0.0,
      "y": 0.0,
      "width": 0.0,
      "height": 0.0,
      "confidence": 0.0
    }}
  ],
  "tags": {{
    "sceneType": "one allowed value",
    "lighting": "one allowed value",
    "weather": "one allowed value",
    "quality": "one allowed value",
    "angle": "one allowed value",
    "source": "cameraCapture"
  }}
}}

Strict output rules:
- Return compact valid JSON only.
- The JSON must be complete and closed.
- Return at most {max_rects} rectangles total.
- Only output boxes with confidence >= {min_confidence}.
- Prefer fewer accurate vendor boxes over many noisy boxes.
- Do not output dense repeated tiny boxes.
- Do not hallucinate baskets, chairs, tables, buckets, or cabinets just because a vendor may exist.
- If many similar crates/baskets/chairs are clustered, skip them unless they are large, clear, and important.
- If an object is very small, heavily occluded, blurry, overexposed, or ambiguous, skip it.

Vendor category decision:
- streetVendor_catering: snacks, cooked food, barbecue, drinks, night food, food cart, food selling window, food operation table.
- streetVendor_fruit: fruit stall, fruit cart, fruit display table.
- streetVendor_vegetablet: vegetable stall, vegetable baskets/crates, ground vegetable display.
- streetVendor_clother: clothing stall or clothing display for sale.
- streetVendor_other: clear selling behavior that is not food/fruit/vegetable/clothing.
- If the goods or selling content are unclear, do not force a vendor category.

What to annotate:
- Vendor subject boxes are the priority.
- One stall/business setup should usually have exactly one vendor box.
- The vendor box should cover the visible selling subject: goods display area, operation table, cart body used for selling, sales window, shelf, or inseparable stall structure.
- For tricycle/truck/trunk stalls: include the goods/selling area and the vehicle part that is used as the stall. Exclude unrelated vehicle head or empty body if it is not part of selling.
- For long continuous stalls: one business owner/one continuous setup = one box; separate business setups = separate boxes.
- Storefronts are not street vendors. Only annotate outdoor temporary tables, carts, or goods placed outside the shop as street occupation.

Bounding box rules:
- Draw one tight box around the visible extent of each target.
- Do not include large background regions, road, walls, shadows, or unrelated people.
- Do not box normal pedestrians, cyclists, vehicles, storefront signs, windows, lights, light boxes, reflections, or road surface.
- Do not mark strong night lights as catering vendors unless goods, operation table, cart, sales window, or selling behavior are visible.
- People are not annotation targets. If a person occludes a stall, box only the visible selling subject; do not include the whole person.
- Boxes must stay within image boundaries.

Accessory object policy:
- Accessory objects are secondary and optional.
- Usually skip accessory objects if a good vendor subject box already represents the setup.
- Only annotate object_table/object_chair/object_basket/object_plasticbasket/object_bucket/object_cabinet when the object is clearly visible, standalone, related to the vendor setup, and not already covered as part of the vendor subject.
- Never create many tiny accessory boxes.

Coordinate rules:
- Return all box coordinates as normalized ratios from 0.0 to 1.0.
- x and y are the top-left corner ratios relative to image width and height.
- width and height are box size ratios relative to image width and height.
- Example: a box starting at 25% width and 40% height with 10% width and 20% height is {{"x":0.25,"y":0.40,"width":0.10,"height":0.20}}.
- Do not invent objects. If uncertain, omit the rectangle.
- Use source=cameraCapture unless the image is clearly synthetic or web-collected.
""".strip()


def call_vlm(config: dict[str, Any], image_path: Path) -> dict[str, Any]:
    model_cfg = config["model"]
    api_key_value = model_cfg.get("api_key") or model_cfg.get("api_key_env")
    api_key = api_key_value
    if not api_key:
        raise RuntimeError("Missing model.api_key in config.yaml")

    request_image_cfg = model_cfg.get("request_image", {})
    image_data_url, request_width, request_height = image_to_data_url(image_path, request_image_cfg)

    payload: dict[str, Any] = {
        "model": model_cfg["model"],
        "temperature": model_cfg.get("temperature", 0.0),
        "stream": bool(model_cfg.get("stream", False)),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": build_prompt(config, image_path, request_width, request_height)},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ],
    }
    for optional_key in ("enable_thinking", "thinking", "thinking_budget", "top_p", "top_k"):
        if optional_key in model_cfg:
            payload[optional_key] = model_cfg[optional_key]
    if "reasoning" in model_cfg:
        payload["reasoning"] = model_cfg["reasoning"]
    if get_mode(config) == "global_tags_only" and "global_tags_max_tokens" in model_cfg:
        payload["max_tokens"] = model_cfg["global_tags_max_tokens"]
    elif "max_tokens" in model_cfg:
        payload["max_tokens"] = model_cfg["max_tokens"]
    if model_cfg.get("response_format_json", True):
        payload["response_format"] = {"type": "json_object"}

    url = f"{model_cfg['base_url'].rstrip('/')}/chat/completions"
    timeout = model_cfg.get("timeout_seconds", 120)
    retries = int(model_cfg.get("retries", 0))
    response = None
    request_started_at = time.time()
    for attempt in range(1, retries + 2):
        try:
            response = requests.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=timeout,
                stream=bool(model_cfg.get("stream", False)),
            )
            if response.status_code == 429 and attempt < retries + 1:
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    sleep_seconds = int(retry_after)
                else:
                    sleep_seconds = min(120, 15 * attempt)
                log(f"{image_path.name} 触发 429 限流: attempt={attempt}/{retries + 1}，等待 {sleep_seconds}s 后重试")
                response.close()
                time.sleep(sleep_seconds)
                continue
            break
        except requests.exceptions.Timeout:
            elapsed = format_seconds(time.time() - request_started_at)
            log(f"{image_path.name} 模型请求超时: attempt={attempt}/{retries + 1}，累计耗时 {elapsed}")
            if attempt >= retries + 1:
                raise
            time.sleep(2 * attempt)

    if response is None:
        raise RuntimeError("模型请求没有返回响应")

    response.raise_for_status()

    if model_cfg.get("stream", False):
        content = read_streaming_content(response)
    else:
        content = response.json()["choices"][0]["message"]["content"]

    if config["run"].get("show_model_output", True):
        log(f"  - 模型原始输出: {summarize_text(content)}")
    try:
        parsed = extract_json_object(content)
    except json.JSONDecodeError as exc:
        log(f"{image_path.name} JSON 解析失败: {exc}")
        log(f"{image_path.name} 输出末尾: {summarize_text(content[-500:], 500)}")
        raise
    parsed["_request_size"] = {"width": request_width, "height": request_height}
    return parsed


def read_streaming_content(response: requests.Response) -> str:
    chunks: list[str] = []
    reasoning_chars = 0
    printed_chars = 0

    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        line = raw_line.strip()
        if line.startswith("data:"):
            line = line[len("data:") :].strip()
        if line == "[DONE]":
            break

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        choices = event.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        reasoning_piece = delta.get("reasoning_content") or ""
        if reasoning_piece:
            reasoning_chars += len(reasoning_piece)
            if reasoning_chars == len(reasoning_piece):
                print("\n  - 检测到 reasoning_content，已忽略思考流内容", flush=True)

        piece = delta.get("content") or ""
        if not piece:
            continue

        chunks.append(piece)
        printed_chars += len(piece)
        print(piece, end="", flush=True)
        if printed_chars >= 2000:
            print("\n  - 流式输出较长，后续仍会接收但不继续逐字打印...", flush=True)
            for rest_line in response.iter_lines(decode_unicode=True):
                if not rest_line:
                    continue
                rest = rest_line.strip()
                if rest.startswith("data:"):
                    rest = rest[len("data:") :].strip()
                if rest == "[DONE]":
                    return "".join(chunks)
                try:
                    event = json.loads(rest)
                except json.JSONDecodeError:
                    continue
                choices = event.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    reasoning_piece = delta.get("reasoning_content") or ""
                    if reasoning_piece:
                        reasoning_chars += len(reasoning_piece)
                    chunks.append(delta.get("content") or "")
            break

    if reasoning_chars:
        log(f"  - 已忽略 reasoning_content: {reasoning_chars} 字符")
    return "".join(chunks)


def log_prediction_summary(prediction: dict[str, Any]) -> None:
    rects = prediction.get("rects", [])
    tags = prediction.get("tags", {})
    log(f"  - 解析框数量: {len(rects)}")
    for index, rect in enumerate(rects, start=1):
        label = rect.get("label")
        x = rect.get("x")
        y = rect.get("y")
        width = rect.get("width")
        height = rect.get("height")
        confidence = rect.get("confidence")
        confidence_text = f", conf={confidence}" if confidence is not None else ""
        log(f"    box {index}: {label} x={x}, y={y}, w={width}, h={height}{confidence_text}")
    if tags:
        tag_text = ", ".join(f"{key}={value}" for key, value in tags.items())
        log(f"  - 解析标签: {tag_text}")


def coerce_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        return float(match.group(0)) if match else None
    if isinstance(value, list):
        for item in value:
            number = coerce_number(item)
            if number is not None:
                return number
        return None
    if isinstance(value, dict):
        for key in ("value", "x", "y", "width", "height", "w", "h"):
            if key in value:
                number = coerce_number(value[key])
                if number is not None:
                    return number
    return None


def default_dry_result(image_path: Path) -> dict[str, Any]:
    lighting = "nightWithLight" if image_path.parent.name.lower() == "night" else "normalDaylight"
    return {
        "rects": [],
        "tags": {
            "sceneType": "commercialStreet",
            "lighting": lighting,
            "weather": "sunny",
            "quality": "clear",
            "angle": "topView",
            "source": "cameraCapture",
        },
    }


def normalize_prediction(prediction: dict[str, Any], config: dict[str, Any], width: int, height: int) -> dict[str, Any]:
    allowed_rects = {item["value"] for item in config["rect_labels"]}
    tag_options = config["tag_options"]
    request_size = prediction.get("_request_size") or {"width": width, "height": height}
    coordinate_mode = config.get("model", {}).get("coordinate_mode", "auto")
    raw_values = []
    for rect in prediction.get("rects", []):
        for key in ("x", "y", "width", "height", "w", "h"):
            value = coerce_number(rect.get(key))
            if value is not None:
                raw_values.append(value)

    if coordinate_mode == "auto":
        max_value = max(raw_values) if raw_values else 1.0
        if max_value <= 1.5:
            coordinate_mode = "relative_1"
        elif max_value <= 1000:
            coordinate_mode = "relative_1000"
        else:
            coordinate_mode = "pixel"

    if coordinate_mode == "relative_1000":
        scale_x = width / 1000.0
        scale_y = height / 1000.0
    elif coordinate_mode == "relative_1":
        scale_x = width
        scale_y = height
    else:
        scale_x = width / float(request_size.get("width", width))
        scale_y = height / float(request_size.get("height", height))
    min_confidence = float(config["run"].get("min_confidence", 0.0))

    rects = []
    if get_mode(config) == "global_tags_only":
        raw_rects = []
    else:
        raw_rects = prediction.get("rects", [])
    max_rects = int(config["run"].get("max_rects", 20))
    for rect in raw_rects:
        label = rect.get("label")
        if label not in allowed_rects:
            continue
        confidence = float(rect.get("confidence", 1.0))
        if confidence < min_confidence:
            continue

        x_value = coerce_number(rect.get("x"))
        y_value = coerce_number(rect.get("y"))
        width_value = coerce_number(rect.get("width", rect.get("w")))
        height_value = coerce_number(rect.get("height", rect.get("h")))
        if x_value is None or y_value is None or width_value is None or height_value is None:
            continue

        raw_x = x_value * scale_x
        raw_y = y_value * scale_y
        raw_w = width_value * scale_x
        raw_h = height_value * scale_y
        x = max(0.0, min(raw_x, width - 1))
        y = max(0.0, min(raw_y, height - 1))
        w = max(1.0, min(raw_w, width - x))
        h = max(1.0, min(raw_h, height - y))
        rects.append({"label": label, "x": x, "y": y, "width": w, "height": h})
        if len(rects) >= max_rects:
            break

    tags = prediction.get("tags", {})
    normalized_tags = {}
    for key in REQUIRED_TAGS:
        value = tags.get(key)
        options = tag_options[key]
        normalized_tags[key] = value if value in options else options[0]

    return {"rects": rects, "tags": normalized_tags}


def to_labelu_result(prediction: dict[str, Any], width: int, height: int, rotate: int) -> dict[str, Any]:
    rect_results = []
    for order, rect in enumerate(prediction["rects"], start=1):
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

    tag_results = []
    for key in REQUIRED_TAGS:
        tag_results.append({"id": random_id(), "type": "tag", "value": {key: [prediction["tags"][key]]}})

    return {
        "width": width,
        "height": height,
        "rotate": rotate,
        "annotations": [
            {"toolName": "rectTool", "result": rect_results},
            {"toolName": "tagTool", "result": tag_results},
        ],
    }


def enrich_labelu_item(item: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    labelu_cfg = config.get("labelu", {})
    file_name = item["fileName"]
    task_id = labelu_cfg.get("task_id")
    upload_subdir = labelu_cfg.get("upload_subdir", "images_only")
    media_folder = labelu_cfg.get("media_folder", "/root/.local/share/labelu/media")

    enriched = dict(item)
    enriched.setdefault("folder", media_folder)
    if task_id is not None:
        enriched.setdefault("url", f"/api/v1/tasks/attachment/upload/{task_id}/{upload_subdir}/{file_name}")
    return enriched


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
    model_name = safe_filename_part(config.get("model", {}).get("model", "model"))
    return (project_dir / "output" / f"labelu_{task_id}_{model_name}.json").resolve()


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


def resolve_run_output_json(project_dir: Path, config: dict[str, Any], checkpoint_jsonl: Path, restart: bool) -> Path:
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


def ensure_checkpoint_meta(path: Path, project_dir: Path, output_json: Path) -> None:
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
    temp_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def process_image(image_path: Path, config: dict[str, Any], dry_run: bool) -> tuple[dict[str, Any], int, float]:
    started_at = time.time()
    with Image.open(image_path) as image:
        width, height = image.size

    raw_prediction = default_dry_result(image_path) if dry_run else call_vlm(config, image_path)
    prediction = normalize_prediction(raw_prediction, config, width, height)
    labelu_result = to_labelu_result(prediction, width, height, config["labelu"]["rotate"])
    item = enrich_labelu_item(
        {"fileName": image_path.name, "result": json.dumps(labelu_result, ensure_ascii=False)},
        config,
    )
    return item, len(prediction["rects"]), time.time() - started_at


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--restart", action="store_true", help="delete checkpoint/output and start from the first image")
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parent
    config = load_config((project_dir / args.config).resolve())
    image_dir = (project_dir / config["paths"]["image_dir"]).resolve()
    checkpoint_jsonl = (project_dir / config["paths"]["checkpoint_jsonl"]).resolve()
    limit = args.limit if args.limit is not None else config["run"].get("limit")

    restart = args.restart or config["run"].get("overwrite_checkpoint", False)
    if restart:
        checkpoint_jsonl.unlink(missing_ok=True)

    output_json = resolve_run_output_json(project_dir, config, checkpoint_jsonl, restart)
    ensure_checkpoint_meta(checkpoint_jsonl, project_dir, output_json)

    all_images = list(iter_images(image_dir))
    done = {
        file_name: enrich_labelu_item(item, config)
        for file_name, item in load_checkpoint(checkpoint_jsonl).items()
    }
    output = list(done.values())
    pending_images = [path for path in all_images if path.name not in done]
    processed = 0
    started_at = time.time()

    log(f"图片目录: {image_dir}")
    log(f"输出文件: {output_json}")
    log(f"总图片数: {len(all_images)}")
    log(f"已完成: {len(done)}")
    log(f"待处理: {len(pending_images)}")
    if limit is not None:
        log(f"本次最多处理: {limit}")
    log(f"预标注模式: {get_mode(config)}")
    log(f"模型: {'dry-run' if args.dry_run else config['model']['model']}")
    parallel = max(1, int(config["run"].get("parallel", 1)))
    log(f"并发数: {parallel}")
    log("")

    progress = tqdm(
        total=len(all_images),
        initial=len(done),
        unit="张",
        desc="预标注进度",
        dynamic_ncols=True,
        file=sys.stdout,
    )

    batch_images = pending_images[:limit] if limit is not None else pending_images
    image_iter = iter(enumerate(batch_images, start=1))
    futures = {}
    executor = ThreadPoolExecutor(max_workers=parallel)

    def submit_next() -> bool:
        try:
            offset, image_path = next(image_iter)
        except StopIteration:
            return False
        current_index = len(done) + offset
        log(f"[{current_index}/{len(all_images)}] 提交: {image_path.name}")
        futures[executor.submit(process_image, image_path, config, args.dry_run)] = (image_path, current_index)
        return True

    def handle_finished(finished_future) -> None:
        nonlocal processed
        image_path, current_index = futures.pop(finished_future)
        try:
            item, box_count, image_elapsed = finished_future.result()
        except Exception as exc:
            elapsed_text = format_seconds(time.time() - started_at)
            log(f"[{current_index}/{len(all_images)}] 失败: {image_path.name}，总耗时 {elapsed_text}，错误: {exc}")
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
            if not config["run"].get("continue_on_error", True):
                raise exc
            return

        append_checkpoint(checkpoint_jsonl, item)
        output.append(item)
        write_output(output_json, output)
        processed += 1
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
        progress.set_postfix_str(f"本次 {processed}/{len(batch_images)} | 累计 {len(output)} | ETA {format_seconds(eta)}")

    try:
        for _ in range(min(parallel, len(batch_images))):
            submit_next()

        while futures:
            done_futures, _ = wait(futures, timeout=0.5, return_when=FIRST_COMPLETED)
            for future in done_futures:
                handle_finished(future)
                submit_next()
    except KeyboardInterrupt:
        log("\n收到 Ctrl+C，正在保存已完成结果并停止...")
        for future in futures:
            future.cancel()
        write_output(output_json, output)
        progress.close()
        executor.shutdown(wait=False, cancel_futures=True)
        log(f"已保存: {output_json}")
        log("下次直接运行 python .\\preannotate.py 会从 checkpoint 继续。")
        os._exit(130)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
        progress.close()

    write_output(output_json, output)
    log(f"\nOutput: {output_json}")
    log(f"Total records: {len(output)}")


if __name__ == "__main__":
    main()
