import argparse
import copy
import csv
import json
import os
import random
import string
import sys
import time
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
    parser = argparse.ArgumentParser(description="把 LabelU 某个 inner_id 样本的 tagTool 复制到一个 inner_id 范围。")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="配置文件路径，默认使用当前目录下的 config.yaml")
    parser.add_argument("--base-url", help="LabelU 服务地址，例如 http://113.141.72.253:38000")
    parser.add_argument("--task-id", type=int, help="任务 ID")
    parser.add_argument("--source-inner-id", type=int, help="复制 tagTool 的来源 inner_id")
    parser.add_argument("--start-inner-id", type=int, help="目标 inner_id 起始值，包含")
    parser.add_argument("--end-inner-id", type=int, help="目标 inner_id 结束值，包含")
    parser.add_argument("--token", help="访问 token，不传时读取环境变量 LABELU_TOKEN，再读取配置文件")
    parser.add_argument("--tag-tool-name", help="全局标签工具名，默认 tagtool")
    parser.add_argument("--state", help="显式设置 PATCH 后状态；不传则不提交 state")
    parser.add_argument("--keep-tag-ids", action="store_true", help="保留来源 tagTool.result 里的 id")
    parser.add_argument("--page-size", type=int, help="分页拉取大小，默认 10")
    parser.add_argument("--page-start", type=int, help="分页起始页，LabelU 通常是 0")
    parser.add_argument("--interval", type=float, help="请求之间的间隔秒数")
    parser.add_argument("--timeout", type=float, help="请求超时秒数")
    parser.add_argument("--retries", type=int, help="请求失败后的最大重试次数")
    parser.add_argument("--output-dir", help="报告输出目录")
    parser.add_argument("--verify-ssl", dest="verify_ssl", action="store_true", help="启用 SSL 证书校验")
    parser.add_argument("--no-verify-ssl", dest="verify_ssl", action="store_false", help="关闭 SSL 证书校验")
    parser.add_argument("--dry-run", action="store_true", help="只预览不提交 PATCH")
    parser.set_defaults(verify_ssl=None)
    return parser.parse_args()


def build_runtime_config(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    target_config = config.get("target", {})
    request_config = config.get("request", {})
    output_config = config.get("output", {})
    env_token = os.getenv("LABELU_TOKEN")

    state = args.state if args.state is not None else target_config.get("state")
    runtime = {
        "base_url": args.base_url or config.get("base_url"),
        "task_id": args.task_id if args.task_id is not None else target_config.get("task_id"),
        "source_inner_id": (
            args.source_inner_id if args.source_inner_id is not None else target_config.get("source_inner_id")
        ),
        "target_inner_id_start": (
            args.start_inner_id if args.start_inner_id is not None else target_config.get("target_inner_id_start")
        ),
        "target_inner_id_end": (
            args.end_inner_id if args.end_inner_id is not None else target_config.get("target_inner_id_end")
        ),
        "token": args.token or env_token or config.get("token"),
        "tag_tool_name": args.tag_tool_name or target_config.get("tag_tool_name", "tagtool"),
        "state": state if state != "" else None,
        "regenerate_tag_ids": (
            False if args.keep_tag_ids else bool(target_config.get("regenerate_tag_ids", True))
        ),
        "page_size": args.page_size or request_config.get("page_size", 10),
        "page_start": args.page_start if args.page_start is not None else request_config.get("page_start", 0),
        "request_interval_seconds": (
            args.interval if args.interval is not None else request_config.get("interval_seconds", 0.2)
        ),
        "request_timeout_seconds": (
            args.timeout if args.timeout is not None else request_config.get("timeout_seconds", 15)
        ),
        "max_retries": args.retries if args.retries is not None else request_config.get("max_retries", 2),
        "verify_ssl": args.verify_ssl if args.verify_ssl is not None else request_config.get("verify_ssl", True),
        "output_dir": args.output_dir or output_config.get("dir", "outputs"),
        "apply": not args.dry_run,
    }

    required_fields = [
        "base_url",
        "task_id",
        "source_inner_id",
        "target_inner_id_start",
        "target_inner_id_end",
        "token",
    ]
    missing = [field for field in required_fields if runtime.get(field) in (None, "", [])]
    if missing:
        raise ValueError(f"缺少必要配置: {', '.join(missing)}")
    if runtime["target_inner_id_start"] > runtime["target_inner_id_end"]:
        raise ValueError("target_inner_id_start 不能大于 target_inner_id_end。")
    if runtime["page_size"] < 1:
        raise ValueError("page_size 必须 >= 1")
    if runtime["page_start"] < 0:
        raise ValueError("page_start 必须 >= 0")
    if runtime["request_timeout_seconds"] <= 0:
        raise ValueError("timeout 必须 > 0")
    if runtime["max_retries"] < 0:
        raise ValueError("max_retries 必须 >= 0")

    base_url = runtime["base_url"].rstrip("/")
    runtime["samples_url"] = f"{base_url}/api/v1/tasks/{runtime['task_id']}/samples"
    runtime["headers"] = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {runtime['token']}",
        "Content-Type": "application/json",
        "Origin": base_url,
        "Referer": f"{base_url}/tasks/{runtime['task_id']}",
        "User-Agent": "Mozilla/5.0 LabelU tagTool unify script",
    }
    runtime["tag_tool_name_normalized"] = runtime["tag_tool_name"].lower()
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


def api_request(runtime: dict[str, Any], method: str, url: str, **kwargs: Any) -> requests.Response:
    return request_with_retry(
        method,
        url,
        retries=runtime["max_retries"],
        interval=runtime["request_interval_seconds"],
        timeout=runtime["request_timeout_seconds"],
        verify=runtime["verify_ssl"],
        **kwargs,
    )


def parse_annotation_result(sample: dict[str, Any]) -> tuple[dict[str, Any], str]:
    result = sample.get("data", {}).get("result")
    if result in (None, ""):
        return {}, "data.result 为空，已按空对象处理"
    if isinstance(result, dict):
        return copy.deepcopy(result), ""
    if isinstance(result, str):
        parsed = json.loads(result)
        if not isinstance(parsed, dict):
            raise ValueError("data.result JSON 根节点不是对象")
        return parsed, ""
    raise ValueError(f"data.result 类型不支持: {type(result).__name__}")


def find_tool_key(annotation: dict[str, Any], tool_name: str) -> str | None:
    for key, value in annotation.items():
        if key.lower() == tool_name and isinstance(value, dict):
            return key
    return None


def random_id(length: int = 11) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def clone_tag_tool(source_tag_tool: dict[str, Any], regenerate_ids: bool) -> dict[str, Any]:
    tag_tool = copy.deepcopy(source_tag_tool)
    result = tag_tool.get("result")
    if regenerate_ids and isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                item["id"] = random_id()
    return tag_tool


def get_result_count(annotation: dict[str, Any], tool_name: str) -> int:
    key = find_tool_key(annotation, tool_name)
    if key is None:
        return 0
    result = annotation.get(key, {}).get("result")
    return len(result) if isinstance(result, list) else 0


def to_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        value = value.strip()
        if value.isdigit():
            return int(value)
    return None


def fetch_sample_by_id(runtime: dict[str, Any], sample_id: int) -> dict[str, Any]:
    url = f"{runtime['samples_url']}/{sample_id}"
    response = api_request(runtime, "GET", url, headers=runtime["headers"])
    if response.status_code != 200:
        raise RuntimeError(f"获取样本 {sample_id} 失败，状态码: {response.status_code}，响应: {response.text}")
    data = response.json().get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"获取样本 {sample_id} 的响应结构异常: {response.text}")
    return data


def find_samples_by_inner_id(runtime: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_inner_id = runtime["source_inner_id"]
    target_start = runtime["target_inner_id_start"]
    target_end = runtime["target_inner_id_end"]
    needed = {source_inner_id, *range(target_start, target_end + 1)}
    found: dict[int, dict[str, Any]] = {}
    page = runtime["page_start"]

    while needed - set(found):
        print(f"正在拉取第 {page} 页样本索引...")
        response = api_request(
            runtime,
            "GET",
            runtime["samples_url"],
            headers=runtime["headers"],
            params={"page": page, "size": runtime["page_size"]},
        )
        if response.status_code != 200:
            raise RuntimeError(f"获取第 {page} 页失败，状态码: {response.status_code}，响应: {response.text}")

        samples = response.json().get("data", [])
        if not samples:
            break

        page_inner_ids: list[int] = []
        for sample in samples:
            inner_id = to_int(sample.get("inner_id"))
            if inner_id is not None:
                page_inner_ids.append(inner_id)
            if inner_id in needed:
                found[inner_id] = sample

        if page_inner_ids:
            print(f"第 {page} 页 inner_id 范围: {min(page_inner_ids)} - {max(page_inner_ids)}")

        if len(samples) < runtime["page_size"]:
            break
        page += 1
        time.sleep(runtime["request_interval_seconds"])

    missing = sorted(needed - set(found))
    if missing:
        raise RuntimeError(f"没有找到这些 inner_id: {missing}")

    targets = [found[inner_id] for inner_id in range(target_start, target_end + 1) if inner_id != source_inner_id]
    return found[source_inner_id], targets


def build_patch_payload(
    runtime: dict[str, Any],
    target_sample: dict[str, Any],
    source_tag_tool: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    annotation, parse_note = parse_annotation_result(target_sample)
    existing_key = find_tool_key(annotation, runtime["tag_tool_name_normalized"])
    output_key = existing_key or "tagTool"
    annotation[output_key] = clone_tag_tool(source_tag_tool, runtime["regenerate_tag_ids"])

    annotated_count = get_result_count(annotation, "recttool")
    if annotated_count == 0:
        annotated_count = int(target_sample.get("annotated_count") or 0)

    patched_data = copy.deepcopy(target_sample.get("data") or {})
    if not isinstance(patched_data, dict):
        patched_data = {}
    patched_data["result"] = json.dumps(annotation, ensure_ascii=False, separators=(",", ":"))

    payload: dict[str, Any] = {
        "data": patched_data,
        "annotated_count": annotated_count,
    }
    if runtime["state"] is not None:
        payload["state"] = runtime["state"]
    return payload, annotation, parse_note


def patch_sample(runtime: dict[str, Any], sample_id: int, payload: dict[str, Any]) -> requests.Response:
    url = f"{runtime['samples_url']}/{sample_id}"
    params = {"sample_id": sample_id}
    return api_request(runtime, "PATCH", url, headers=runtime["headers"], params=params, json=payload)


def write_report(runtime: dict[str, Any], rows: list[dict[str, Any]]) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(runtime["output_dir"])
    if not output_dir.is_absolute():
        output_dir = Path(__file__).parent / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"task_{runtime['task_id']}_tagtool_unify_{timestamp}.csv"

    fieldnames = [
        "mode",
        "task_id",
        "source_inner_id",
        "target_inner_id",
        "target_sample_id",
        "old_state",
        "state_payload",
        "rect_count",
        "tag_count",
        "status",
        "detail",
    ]
    with report_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return report_path


def write_sample_backup(runtime: dict[str, Any], sample: dict[str, Any]) -> Path:
    timestamp = runtime.setdefault("backup_timestamp", datetime.now().strftime("%Y%m%d_%H%M%S"))
    output_dir = Path(runtime["output_dir"])
    if not output_dir.is_absolute():
        output_dir = Path(__file__).parent / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    backup_path = output_dir / f"task_{runtime['task_id']}_tagtool_unify_backup_{timestamp}.jsonl"
    with backup_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(sample, ensure_ascii=False, separators=(",", ":")) + "\n")
    return backup_path


def main() -> int:
    args = parse_args()
    try:
        config = load_config(Path(args.config))
        runtime = build_runtime_config(args, config)
    except Exception as exc:
        print(f"加载配置失败: {exc}")
        return 1

    mode = "APPLY" if runtime["apply"] else "DRY-RUN"
    print("当前运行配置:")
    print(f"- 模式: {mode}")
    print(f"- 服务地址: {runtime['base_url']}")
    print(f"- 任务 ID: {runtime['task_id']}")
    print(f"- 来源 inner_id: {runtime['source_inner_id']}")
    print(f"- 目标 inner_id 范围: {runtime['target_inner_id_start']} - {runtime['target_inner_id_end']}")
    print(f"- 分页起始页: {runtime['page_start']}")
    print(f"- 标签工具名: {runtime['tag_tool_name']}")
    print(f"- 重新生成标签 id: {runtime['regenerate_tag_ids']}")
    print(f"- 标记状态: {'显式提交 ' + runtime['state'] if runtime['state'] is not None else '不改动'}")

    rows: list[dict[str, Any]] = []
    backup_path: Path | None = None
    try:
        source_index_sample, target_index_samples = find_samples_by_inner_id(runtime)
        source_sample = fetch_sample_by_id(runtime, source_index_sample["id"])
        source_annotation, _ = parse_annotation_result(source_sample)
        source_tag_key = find_tool_key(source_annotation, runtime["tag_tool_name_normalized"])
        if source_tag_key is None:
            raise RuntimeError(f"来源 inner_id={runtime['source_inner_id']} 样本没有 tagTool")
        source_tag_tool = source_annotation[source_tag_key]
        source_tag_count = len(source_tag_tool.get("result", [])) if isinstance(source_tag_tool.get("result"), list) else 0
        print(f"已读取来源样本 sample_id={source_sample.get('id')}，tagTool 标签数={source_tag_count}")

        for index_sample in target_index_samples:
            target_sample = fetch_sample_by_id(runtime, index_sample["id"])
            payload, patched_annotation, parse_note = build_patch_payload(runtime, target_sample, source_tag_tool)
            rect_count = get_result_count(patched_annotation, "recttool")
            tag_count = get_result_count(patched_annotation, runtime["tag_tool_name_normalized"])
            state_payload = payload.get("state", "")
            row = {
                "mode": mode,
                "task_id": runtime["task_id"],
                "source_inner_id": runtime["source_inner_id"],
                "target_inner_id": target_sample.get("inner_id", ""),
                "target_sample_id": target_sample.get("id", ""),
                "old_state": target_sample.get("state", ""),
                "state_payload": state_payload,
                "rect_count": rect_count,
                "tag_count": tag_count,
                "status": "DRY_RUN",
                "detail": parse_note,
            }

            if runtime["apply"]:
                backup_path = write_sample_backup(runtime, target_sample)
                response = patch_sample(runtime, target_sample["id"], payload)
                if response.status_code not in (200, 201):
                    row["status"] = "FAILED"
                    row["detail"] = f"状态码 {response.status_code}: {response.text}"
                    print(f"提交失败 inner_id={target_sample.get('inner_id')}: {row['detail']}")
                else:
                    row["status"] = "UPDATED"
                    print(f"已提交 inner_id={target_sample.get('inner_id')} sample_id={target_sample.get('id')}")
                time.sleep(runtime["request_interval_seconds"])
            else:
                print(
                    f"预览 inner_id={target_sample.get('inner_id')} sample_id={target_sample.get('id')} "
                    f"rect_count={rect_count} tag_count={tag_count}"
                )

            rows.append(row)

        report_path = write_report(runtime, rows)
    except Exception as exc:
        print(f"执行失败: {exc}")
        if rows:
            report_path = write_report(runtime, rows)
            print(f"已写入部分报告: {report_path}")
        return 1

    print("\n--- 汇总 ---")
    print(f"来源 inner_id: {runtime['source_inner_id']}")
    print(f"目标数量: {len(rows)}")
    print(f"成功提交: {sum(1 for row in rows if row['status'] == 'UPDATED')}")
    print(f"失败: {sum(1 for row in rows if row['status'] == 'FAILED')}")
    print(f"报告已生成: {report_path}")
    if backup_path:
        print(f"提交前备份: {backup_path}")
    if not runtime["apply"]:
        print("当前是 dry-run 预览，没有修改 LabelU。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
