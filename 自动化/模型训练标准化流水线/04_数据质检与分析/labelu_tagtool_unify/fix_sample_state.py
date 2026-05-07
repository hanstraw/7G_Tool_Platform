import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests
import yaml


DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yaml")


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按 inner_id 范围修复 LabelU 样本状态。")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--base-url")
    parser.add_argument("--task-id", type=int)
    parser.add_argument("--token")
    parser.add_argument("--start-inner-id", type=int, required=True)
    parser.add_argument("--end-inner-id", type=int, required=True)
    parser.add_argument("--from-state", action="append", help="只修复这些原状态，可重复传；不传则不限制")
    parser.add_argument("--to-state", default="DONE", help="目标状态，默认 DONE")
    parser.add_argument("--page-start", type=int, default=0)
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--interval", type=float, default=0.05)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def to_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def request_json(method: str, url: str, **kwargs: Any) -> dict[str, Any]:
    response = requests.request(method, url, **kwargs)
    if response.status_code not in (200, 201):
        raise RuntimeError(f"{method} {url} failed: {response.status_code} {response.text}")
    return response.json()


def find_samples(runtime: dict[str, Any]) -> list[dict[str, Any]]:
    needed = set(range(runtime["start_inner_id"], runtime["end_inner_id"] + 1))
    found: dict[int, dict[str, Any]] = {}
    page = runtime["page_start"]
    while needed - set(found):
        samples = request_json(
            "GET",
            runtime["samples_url"],
            headers=runtime["headers"],
            params={"page": page, "size": runtime["page_size"]},
            timeout=runtime["timeout"],
            verify=False,
        ).get("data") or []
        if not samples:
            break
        for sample in samples:
            inner_id = to_int(sample.get("inner_id"))
            if inner_id in needed:
                found[inner_id] = sample
        if len(samples) < runtime["page_size"]:
            break
        page += 1
    missing = sorted(needed - set(found))
    if missing:
        raise RuntimeError(f"没有找到这些 inner_id: {missing}")
    return [found[i] for i in sorted(found)]


def append_backup(task_id: int, sample: dict[str, Any]) -> Path:
    timestamp = append_backup.__dict__.setdefault("timestamp", time.strftime("%Y%m%d_%H%M%S"))
    output_dir = Path(__file__).with_name("outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    backup_path = output_dir / f"task_{task_id}_state_fix_before_{timestamp}.jsonl"
    with backup_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(sample, ensure_ascii=False, separators=(",", ":")) + "\n")
    return backup_path


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config))
    base_url = (args.base_url or config.get("base_url") or "").rstrip("/")
    token = args.token or os.getenv("LABELU_TOKEN") or config.get("token")
    task_id = args.task_id or (config.get("target") or {}).get("task_id")
    if not base_url or not token or not task_id:
        print("缺少 base_url/token/task_id")
        return 1
    if args.start_inner_id > args.end_inner_id:
        print("start-inner-id 不能大于 end-inner-id")
        return 1

    runtime = {
        "start_inner_id": args.start_inner_id,
        "end_inner_id": args.end_inner_id,
        "page_start": args.page_start,
        "page_size": args.page_size,
        "timeout": args.timeout,
        "samples_url": f"{base_url}/api/v1/tasks/{task_id}/samples",
        "headers": {
            "Accept": "application/json, text/plain, */*",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Origin": base_url,
            "Referer": f"{base_url}/tasks/{task_id}",
        },
    }
    allowed_states = set(args.from_state or [])
    samples = find_samples(runtime)
    backup_path: Path | None = None
    mode = "DRY-RUN" if args.dry_run else "APPLY"
    print(f"模式: {mode}，样本数: {len(samples)}，目标状态: {args.to_state}")

    for index_sample in samples:
        sample_id = index_sample["id"]
        sample = request_json(
            "GET",
            f"{runtime['samples_url']}/{sample_id}",
            headers=runtime["headers"],
            timeout=args.timeout,
            verify=False,
        ).get("data")
        state = sample.get("state")
        inner_id = sample.get("inner_id")
        if allowed_states and state not in allowed_states:
            print(f"SKIP inner_id={inner_id} sample_id={sample_id} state={state}")
            continue

        print(f"FIX inner_id={inner_id} sample_id={sample_id} {state} -> {args.to_state}")
        if args.dry_run:
            continue

        payload = {
            "data": sample.get("data") or {},
            "annotated_count": sample.get("annotated_count") or 0,
            "state": args.to_state,
        }
        backup_path = append_backup(task_id, sample)
        request_json(
            "PATCH",
            f"{runtime['samples_url']}/{sample_id}",
            headers=runtime["headers"],
            params={"sample_id": sample_id},
            json=payload,
            timeout=args.timeout,
            verify=False,
        )
        time.sleep(args.interval)

    if backup_path:
        print(f"修复前备份: {backup_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
