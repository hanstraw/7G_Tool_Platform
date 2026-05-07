import json
import sys
from pathlib import Path


REQUIRED_TAGS = {"sceneType", "lighting", "weather", "quality", "angle", "source"}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python validate_labelu_json.py output/labelu_preannotations.json")

    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("Top-level JSON must be a list")

    for index, item in enumerate(data):
        for required_key in ("fileName", "result", "url", "folder"):
            if required_key not in item or not item[required_key]:
                raise SystemExit(f"Record {index} missing {required_key}")
        result = json.loads(item["result"])
        if result.get("width") != 1920 or result.get("height") != 1080:
            raise SystemExit(f"{item['fileName']} is not 1920x1080 in result")
        annotations = {ann.get("toolName"): ann.get("result", []) for ann in result.get("annotations", [])}
        if "rectTool" not in annotations or "tagTool" not in annotations:
            raise SystemExit(f"{item['fileName']} missing rectTool/tagTool")

        tags = set()
        for tag in annotations["tagTool"]:
            value = tag.get("value", {})
            tags.update(value.keys())
        missing = REQUIRED_TAGS - tags
        if missing:
            raise SystemExit(f"{item['fileName']} missing tags: {sorted(missing)}")

    print(f"OK: {len(data)} records")


if __name__ == "__main__":
    main()
