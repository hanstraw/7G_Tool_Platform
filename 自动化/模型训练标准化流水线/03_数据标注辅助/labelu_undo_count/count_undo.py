import argparse
import csv
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import yaml


DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yaml")
FETCH_PAGE_SIZE = 100


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    if not isinstance(config, dict):
        raise ValueError("配置文件格式错误，根节点必须是对象。")

    return config


def build_runtime_config(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    request_config = config.get("request", {})
    target_config = config.get("target", {})
    output_config = config.get("output", {})

    runtime = {
        "base_url": args.base_url or config.get("base_url"),
        "task_id": args.task_id if args.task_id is not None else target_config.get("task_id"),
        "token": args.token or config.get("token"),
        "display_page_size": args.page_size or request_config.get("page_size", 10),
        "fetch_page_size": FETCH_PAGE_SIZE,
        "request_interval_seconds": (
            args.interval
            if args.interval is not None
            else request_config.get("interval_seconds", 0.2)
        ),
        "request_timeout_seconds": (
            args.timeout
            if args.timeout is not None
            else request_config.get("timeout_seconds", 15)
        ),
        "max_retries": args.retries if args.retries is not None else request_config.get("max_retries", 2),
        "verify_ssl": args.verify_ssl if args.verify_ssl is not None else request_config.get("verify_ssl", True),
        "finished_states": args.finished_states or target_config.get("finished_states", ["DONE", "SKIPPED", "SKIP"]),
        "zero_label_states": target_config.get("zero_label_states", ["DONE"]),
        "output_dir": args.output_dir or output_config.get("dir", "outputs"),
    }

    required_fields = ["base_url", "task_id", "token"]
    missing = [field for field in required_fields if runtime.get(field) in (None, "", [])]
    if missing:
        raise ValueError(f"缺少必要配置: {', '.join(missing)}")

    if runtime["display_page_size"] < 1:
        raise ValueError("page_size 必须 >= 1")
    if runtime["request_timeout_seconds"] <= 0:
        raise ValueError("timeout 必须 > 0")
    if runtime["max_retries"] < 0:
        raise ValueError("max_retries 必须 >= 0")
    if not isinstance(runtime["finished_states"], list) or not runtime["finished_states"]:
        raise ValueError("finished_states 必须是非空列表。")
    if not isinstance(runtime["zero_label_states"], list):
        raise ValueError("zero_label_states 必须是列表。")

    runtime["headers"] = {
        "Authorization": f"Bearer {runtime['token']}",
        "Content-Type": "application/json",
    }
    runtime["samples_url"] = f"{runtime['base_url'].rstrip('/')}/api/v1/tasks/{runtime['task_id']}/samples"
    runtime["finished_states_set"] = set(runtime["finished_states"])
    runtime["zero_label_states_set"] = set(runtime["zero_label_states"])
    return runtime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="统计 LabelU 任务中未完成样本数量，并导出 CSV。")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="配置文件路径，默认使用当前目录下的 config.yaml")
    parser.add_argument("--base-url", help="LabelU 服务地址，例如 http://127.0.0.1:38000")
    parser.add_argument("--task-id", type=int, help="任务 ID")
    parser.add_argument("--token", help="访问 token，不传时从配置文件读取")
    parser.add_argument("--page-size", type=int, help="展示页码使用的每页数量")
    parser.add_argument("--interval", type=float, help="请求之间的间隔秒数")
    parser.add_argument("--timeout", type=float, help="查询请求超时秒数")
    parser.add_argument("--retries", type=int, help="请求失败后的最大重试次数")
    parser.add_argument("--finished-states", nargs="+", help="视为已完成的状态列表，例如 DONE SKIPPED SKIP")
    parser.add_argument("--output-dir", help="CSV 输出目录")
    parser.add_argument("--verify-ssl", dest="verify_ssl", action="store_true", help="启用 SSL 证书校验")
    parser.add_argument("--no-verify-ssl", dest="verify_ssl", action="store_false", help="关闭 SSL 证书校验")
    parser.set_defaults(verify_ssl=None)
    return parser.parse_args()


def request_with_retry(method: str, url: str, *, retries: int, interval: float, **kwargs: Any) -> requests.Response:
    last_error = None
    for attempt in range(retries + 1):
        try:
            return requests.request(method, url, **kwargs)
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= retries:
                break
            wait_seconds = interval * (attempt + 1)
            print(f"请求失败，第 {attempt + 1} 次重试前等待 {wait_seconds:.1f} 秒: {exc}")
            time.sleep(wait_seconds)
    raise RuntimeError(f"请求最终失败: {last_error}") from last_error


def get_label_count(sample: dict[str, Any]) -> int | None:
    direct_fields = [
        "annotated_count",
        "annotatedCount",
        "label_count",
        "labelCount",
        "annotation_count",
        "annotationCount",
        "result_count",
        "resultCount",
        "object_count",
        "objectCount",
    ]
    for field in direct_fields:
        value = sample.get(field)
        if isinstance(value, int):
            return value

    list_fields = ["labels", "annotations", "results", "objects"]
    for field in list_fields:
        value = sample.get(field)
        if isinstance(value, list):
            return len(value)

    return None


def should_count_as_remaining(sample: dict[str, Any], runtime: dict[str, Any]) -> bool:
    state = sample.get("state") or "UNKNOWN"
    if state not in runtime["finished_states_set"]:
        return True

    if state in runtime["zero_label_states_set"]:
        label_count = get_label_count(sample)
        if label_count == 0:
            return True

    return False


def scan_task(runtime: dict[str, Any]) -> tuple[list[dict[str, Any]], Counter[str], dict[str, int]]:
    pending_by_page: dict[int, int] = {}
    state_counter: Counter[str] = Counter()
    total_pending = 0
    fetched_pages = 0
    zero_label_marked_count = 0
    page = 1
    sample_offset = 0

    while True:
        params = {"page": page, "size": runtime["fetch_page_size"]}
        response = request_with_retry(
            "GET",
            runtime["samples_url"],
            retries=runtime["max_retries"],
            interval=runtime["request_interval_seconds"],
            headers=runtime["headers"],
            params=params,
            timeout=runtime["request_timeout_seconds"],
            verify=runtime["verify_ssl"],
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"获取第 {page} 页失败，状态码: {response.status_code}，响应: {response.text}"
            )

        samples = response.json().get("data", [])
        if not samples:
            print("所有页面已扫描完成。")
            break

        fetched_pages += 1

        for index, sample in enumerate(samples):
            state = sample.get("state") or "UNKNOWN"
            state_counter[state] += 1

            if not should_count_as_remaining(sample, runtime):
                continue

            if state in runtime["zero_label_states_set"]:
                label_count = get_label_count(sample)
                if label_count == 0:
                    zero_label_marked_count += 1

            total_pending += 1
            display_page = (sample_offset + index) // runtime["display_page_size"] + 2
            pending_by_page[display_page] = pending_by_page.get(display_page, 0) + 1

        print(f"第 {page} 批次拉取完成，累计命中 {total_pending} 条。")

        sample_offset += len(samples)
        if len(samples) < runtime["fetch_page_size"]:
            break

        page += 1
        time.sleep(runtime["request_interval_seconds"])

    rows = [
        {
            "task_id": runtime["task_id"],
            "page": display_page,
            "remaining_count": pending_count,
        }
        for display_page, pending_count in sorted(pending_by_page.items())
        if pending_count > 0
    ]

    summary = {
        "scanned_pages": fetched_pages,
        "pages_with_pending_count": len(rows),
        "total_pending": total_pending,
        "zero_label_marked_count": zero_label_marked_count,
    }
    return rows, state_counter, summary


def write_csv(runtime: dict[str, Any], rows: list[dict[str, Any]]) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(runtime["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"task_{runtime['task_id']}_undo_count_{timestamp}.csv"

    fieldnames = ["task_id", "page", "remaining_count"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return csv_path


def main() -> int:
    args = parse_args()

    try:
        config = load_config(Path(args.config))
        runtime = build_runtime_config(args, config)
    except Exception as exc:
        print(f"加载配置失败: {exc}")
        return 1

    print("当前运行配置:")
    print(f"- 服务地址: {runtime['base_url']}")
    print(f"- 任务 ID: {runtime['task_id']}")
    print(f"- 展示页每页数量: {runtime['display_page_size']}")
    print(f"- 内部拉取每页数量: {runtime['fetch_page_size']}")
    print(f"- 已完成状态: {runtime['finished_states']}")
    print(f"- 零标签也纳入检索的状态: {runtime['zero_label_states']}")
    print(f"- 输出目录: {runtime['output_dir']}")

    try:
        rows, state_counter, summary = scan_task(runtime)
        csv_path = write_csv(runtime, rows)
    except Exception as exc:
        print(f"执行失败: {exc}")
        return 1

    print("\n--- 状态统计 ---")
    for state, count in state_counter.items():
        print(f"- {state}: {count}")

    print("\n--- 汇总 ---")
    print(f"内部扫描页数: {summary['scanned_pages']}")
    print(f"有剩余数量的页码数: {summary['pages_with_pending_count']}")
    print(f"总命中数量: {summary['total_pending']}")
    print(f"其中已标记但标签数为 0 的数量: {summary['zero_label_marked_count']}")
    print(f"CSV 已生成: {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
