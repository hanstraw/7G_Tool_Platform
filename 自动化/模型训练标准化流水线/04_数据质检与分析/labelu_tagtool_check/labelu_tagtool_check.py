import argparse
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import yaml


DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yaml")


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    if not isinstance(config, dict):
        raise ValueError("配置文件格式错误，根节点必须是对象。")

    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查 LabelU 已标记样本是否缺少 tagTool、tagTool 标签数量不全或标框数量为 0。")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="配置文件路径，默认使用当前目录下的 config.yaml")
    parser.add_argument("--base-url", help="LabelU 服务地址，例如 http://127.0.0.1:38000")
    parser.add_argument("--task-id", type=int, help="任务 ID")
    parser.add_argument("--token", help="访问 token，不传时从配置文件读取")
    parser.add_argument("--states", nargs="+", help="需要检查的样本状态，默认 DONE")
    parser.add_argument("--tag-tool-name", help="全局标签工具名，默认 tagtool")
    parser.add_argument("--expected-tag-count", type=int, help="期望的 tagTool.result 标签数量")
    parser.add_argument("--box-tool-name", help="标框工具名，默认 recttool")
    parser.add_argument("--min-box-count", type=int, help="最少需要的 rectTool.result 标框数量，默认 1")
    parser.add_argument("--page-size", type=int, help="分页拉取大小，默认 10")
    parser.add_argument("--interval", type=float, help="请求之间的间隔秒数")
    parser.add_argument("--timeout", type=float, help="查询请求超时秒数")
    parser.add_argument("--retries", type=int, help="请求失败后的最大重试次数")
    parser.add_argument("--output-dir", help="CSV 输出目录")
    parser.add_argument("--verify-ssl", dest="verify_ssl", action="store_true", help="启用 SSL 证书校验")
    parser.add_argument("--no-verify-ssl", dest="verify_ssl", action="store_false", help="关闭 SSL 证书校验")
    parser.set_defaults(verify_ssl=None)
    return parser.parse_args()


def build_runtime_config(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    request_config = config.get("request", {})
    target_config = config.get("target", {})
    output_config = config.get("output", {})

    runtime = {
        "base_url": args.base_url or config.get("base_url"),
        "task_id": args.task_id if args.task_id is not None else target_config.get("task_id"),
        "token": args.token or config.get("token"),
        "sample_states": args.states or target_config.get("sample_states", ["DONE"]),
        "tag_tool_name": args.tag_tool_name or target_config.get("tag_tool_name", "tagtool"),
        "expected_tag_count": (
            args.expected_tag_count
            if args.expected_tag_count is not None
            else target_config.get("expected_tag_count", 6)
        ),
        "box_tool_name": args.box_tool_name or target_config.get("box_tool_name", "recttool"),
        "min_box_count": (
            args.min_box_count
            if args.min_box_count is not None
            else target_config.get("min_box_count", 1)
        ),
        "check_non_positive_result_size": bool(target_config.get("check_non_positive_result_size", True)),
        "page_size": args.page_size or request_config.get("page_size", 10),
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
        "output_dir": args.output_dir or output_config.get("dir", "outputs"),
    }

    required_fields = ["base_url", "task_id", "token"]
    missing = [field for field in required_fields if runtime.get(field) in (None, "", [])]
    if missing:
        raise ValueError(f"缺少必要配置: {', '.join(missing)}")

    if not isinstance(runtime["sample_states"], list) or not runtime["sample_states"]:
        raise ValueError("sample_states 必须是非空列表。")
    if runtime["expected_tag_count"] < 1:
        raise ValueError("expected_tag_count 必须 >= 1")
    if runtime["min_box_count"] < 1:
        raise ValueError("min_box_count 必须 >= 1")
    if runtime["page_size"] != 10:
        raise ValueError("page_size 必须为 10，当前需求按每页 10 个页码筛选。")
    if runtime["request_timeout_seconds"] <= 0:
        raise ValueError("timeout 必须 > 0")
    if runtime["max_retries"] < 0:
        raise ValueError("max_retries 必须 >= 0")

    runtime["headers"] = {
        "Authorization": f"Bearer {runtime['token']}",
        "Content-Type": "application/json",
    }
    runtime["samples_url"] = f"{runtime['base_url'].rstrip('/')}/api/v1/tasks/{runtime['task_id']}/samples"
    runtime["sample_states_set"] = set(runtime["sample_states"])
    runtime["tag_tool_name_normalized"] = runtime["tag_tool_name"].lower()
    runtime["box_tool_name_normalized"] = runtime["box_tool_name"].lower()
    return runtime


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


def parse_annotation_result(sample: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    result = sample.get("data", {}).get("result")
    if result in (None, ""):
        return None, "data.result 为空"

    if isinstance(result, dict):
        return result, None

    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except json.JSONDecodeError as exc:
            return None, f"data.result 不是合法 JSON: {exc}"
        if isinstance(parsed, dict):
            return parsed, None
        return None, "data.result JSON 根节点不是对象"

    return None, f"data.result 类型不支持: {type(result).__name__}"


def find_tool(annotation: dict[str, Any], tool_name: str) -> tuple[str | None, dict[str, Any] | None]:
    for key, value in annotation.items():
        if key.lower() == tool_name and isinstance(value, dict):
            return key, value
    return None, None


def get_result_count(tool: dict[str, Any] | None) -> int | None:
    if not tool:
        return None
    result = tool.get("result")
    if isinstance(result, list):
        return len(result)
    return None


def get_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def build_issue_row(
    sample: dict[str, Any],
    page: int,
    issue_categories: list[str],
    issue_types: list[str],
    expected_tag_count: int,
    actual_tag_count: int | None,
    expected_box_count: int,
    actual_box_count: int | None,
    details: list[str],
    found_tag_tool_name: str | None = None,
    found_box_tool_name: str | None = None,
    result_width: float | int | None = None,
    result_height: float | int | None = None,
) -> dict[str, Any]:
    file_info = sample.get("file") or {}
    return {
        "task_id": "",
        "page": page,
        "sample_id": sample.get("id", ""),
        "inner_id": sample.get("inner_id", ""),
        "state": sample.get("state", ""),
        "filename": file_info.get("filename", ""),
        "file_url": file_info.get("url", ""),
        "issue_category": ";".join(issue_categories),
        "issue_type": ";".join(issue_types),
        "expected_tag_count": expected_tag_count,
        "actual_tag_count": "" if actual_tag_count is None else actual_tag_count,
        "expected_box_count": expected_box_count,
        "actual_box_count": "" if actual_box_count is None else actual_box_count,
        "result_width": "" if result_width is None else result_width,
        "result_height": "" if result_height is None else result_height,
        "found_tag_tool_name": found_tag_tool_name or "",
        "found_box_tool_name": found_box_tool_name or "",
        "detail": "；".join(details),
    }


def scan_task(runtime: dict[str, Any]) -> tuple[list[dict[str, Any]], Counter[str], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    state_counter: Counter[str] = Counter()
    page = 1
    checked_count = 0

    while True:
        print(f"正在拉取第 {page} 页样本...")
        params = {"page": page, "size": runtime["page_size"]}
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
            raise RuntimeError(f"获取第 {page} 页失败，状态码: {response.status_code}，响应: {response.text}")

        samples = response.json().get("data", [])
        if not samples:
            print("所有页面已扫描完成。")
            break

        page_hit_count = 0
        for sample in samples:
            output_page = page + 1
            state = sample.get("state") or "UNKNOWN"
            state_counter[state] += 1
            if state not in runtime["sample_states_set"]:
                continue

            checked_count += 1
            annotation, parse_error = parse_annotation_result(sample)
            if parse_error:
                rows.append(
                    build_issue_row(
                        sample,
                        output_page,
                        ["tagtool_content_issue"],
                        ["invalid_result"],
                        runtime["expected_tag_count"],
                        None,
                        runtime["min_box_count"],
                        None,
                        [parse_error],
                    )
                )
                page_hit_count += 1
                continue

            issue_types: list[str] = []
            issue_categories: list[str] = []
            details: list[str] = []
            result_width = get_number(annotation.get("width")) if annotation else None
            result_height = get_number(annotation.get("height")) if annotation else None

            if runtime["check_non_positive_result_size"]:
                if result_width is None or result_height is None or result_width <= 0 or result_height <= 0:
                    issue_categories.append("image_size_issue")
                    issue_types.append("non_positive_result_size")
                    details.append(f"data.result 宽高异常，width={result_width}，height={result_height}")

            found_tag_tool_name, tag_tool = find_tool(annotation or {}, runtime["tag_tool_name_normalized"])
            tag_count = None
            if tag_tool is None:
                issue_categories.append("tagtool_content_issue")
                issue_types.append("missing_tagtool")
                details.append("响应结构里没有全局工具 tagTool/tagtool")
            else:
                tag_count = get_result_count(tag_tool)
                if tag_count is None:
                    issue_categories.append("tagtool_content_issue")
                    issue_types.append("invalid_tagtool_result")
                    details.append("tagTool.result 不是列表或不存在")
                elif tag_count < runtime["expected_tag_count"]:
                    issue_categories.append("tagtool_content_issue")
                    issue_types.append("incomplete_tagtool_result")
                    details.append(f"tagTool.result 标签数量不足，期望 {runtime['expected_tag_count']}，实际 {tag_count}")

            found_box_tool_name, box_tool = find_tool(annotation or {}, runtime["box_tool_name_normalized"])
            box_count = None
            if box_tool is None:
                box_count = 0
                issue_categories.append("box_issue")
                issue_types.append("missing_box_tool")
                details.append("响应结构里没有标框工具 rectTool/recttool，按标框数量 0 处理")
            else:
                box_count = get_result_count(box_tool)
                if box_count is None:
                    box_count = 0
                    issue_categories.append("box_issue")
                    issue_types.append("invalid_box_tool_result")
                    details.append("rectTool.result 不是列表或不存在，按标框数量 0 处理")
                elif box_count < runtime["min_box_count"]:
                    issue_categories.append("box_issue")
                    issue_types.append("zero_box_result")
                    details.append(f"rectTool.result 标框数量为 {box_count}")

            if issue_types:
                issue_categories = list(dict.fromkeys(issue_categories))
                rows.append(
                    build_issue_row(
                        sample,
                        output_page,
                        issue_categories,
                        issue_types,
                        runtime["expected_tag_count"],
                        tag_count,
                        runtime["min_box_count"],
                        box_count,
                        details,
                        found_tag_tool_name,
                        found_box_tool_name,
                        result_width,
                        result_height,
                    )
                )
                page_hit_count += 1

        print(f"第 {page} 页处理完成，本页命中 {page_hit_count} 条，累计命中 {len(rows)} 条。")

        if len(samples) < runtime["page_size"]:
            break

        page += 1
        time.sleep(runtime["request_interval_seconds"])

    for row in rows:
        row["task_id"] = runtime["task_id"]

    summary = {
        "scanned_pages": page,
        "checked_count": checked_count,
        "issue_count": len(rows),
    }
    return rows, state_counter, summary


def write_csv(runtime: dict[str, Any], rows: list[dict[str, Any]]) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(runtime["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"task_{runtime['task_id']}_tagtool_check_{timestamp}.csv"

    fieldnames = [
        "task_id",
        "page",
        "sample_id",
        "inner_id",
        "state",
        "filename",
        "file_url",
        "issue_category",
        "issue_type",
        "expected_tag_count",
        "actual_tag_count",
        "expected_box_count",
        "actual_box_count",
        "result_width",
        "result_height",
        "found_tag_tool_name",
        "found_box_tool_name",
        "detail",
    ]
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
    print(f"- 检查状态: {runtime['sample_states']}")
    print(f"- 每页数量: {runtime['page_size']}")
    print(f"- 标签工具名: {runtime['tag_tool_name']}")
    print(f"- 期望标签数量: {runtime['expected_tag_count']}")
    print(f"- 标框工具名: {runtime['box_tool_name']}")
    print(f"- 最少标框数量: {runtime['min_box_count']}")
    print(f"- 检查 data.result 宽高: {runtime['check_non_positive_result_size']}")
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
    print(f"扫描页数: {summary['scanned_pages']}")
    print(f"已检查样本数: {summary['checked_count']}")
    print(f"问题样本数: {len(rows)}")
    print(f"CSV 已生成: {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
