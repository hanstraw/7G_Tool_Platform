import argparse
import json
import shutil
import time
from pathlib import Path


def fix_result(result_text: str, from_width: float, from_height: float) -> str:
    result = json.loads(result_text)
    width = float(result["width"])
    height = float(result["height"])
    scale_x = width / from_width
    scale_y = height / from_height

    for annotation in result.get("annotations", []):
        if annotation.get("toolName") != "rectTool":
            continue
        for box in annotation.get("result", []):
            box["x"] = max(0.0, min(float(box["x"]) * scale_x, width - 1))
            box["y"] = max(0.0, min(float(box["y"]) * scale_y, height - 1))
            box["width"] = max(1.0, min(float(box["width"]) * scale_x, width - box["x"]))
            box["height"] = max(1.0, min(float(box["height"]) * scale_y, height - box["y"]))

    return json.dumps(result, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_path")
    parser.add_argument("--from-width", type=float, default=1000.0)
    parser.add_argument("--from-height", type=float, default=1000.0)
    parser.add_argument("--output", default=None)
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.json_path)
    output_path = Path(args.output) if args.output else input_path
    data = json.loads(input_path.read_text(encoding="utf-8"))

    fixed = []
    for item in data:
        fixed_item = dict(item)
        fixed_item["result"] = fix_result(item["result"], args.from_width, args.from_height)
        fixed.append(fixed_item)

    if output_path == input_path and not args.no_backup:
        backup_path = input_path.with_suffix(input_path.suffix + f".bak_coords_{time.strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(input_path, backup_path)
        print(f"已备份: {backup_path}")

    output_path.write_text(json.dumps(fixed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已修复坐标: {output_path}")
    print(f"记录数: {len(fixed)}")


if __name__ == "__main__":
    main()
