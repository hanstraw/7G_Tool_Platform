import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests
import yaml


DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yaml")
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
SUCCESS_STATUS_CODES = {200, 204}


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
















    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    if not isinstance(config, dict):
        raise ValueError("配置文件格式错误，根节点必须是对象。")

    return config


def normalize_state(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.upper()


def build_state_aliases(sample_states: list[str]) -> set[str]:
    aliases: set[str] = set()
    for state in sample_states:
        normalized = normalize_state(state)
        if not normalized:
            continue
        aliases.add(normalized)
        if normalized in {"SKIPPED", "SKIP"}:
            aliases.update({"SKIPPED", "SKIP"})
    return aliases


def extract_sample_state(sample: dict[str, Any]) -> tuple[str | None, str | None]:
    candidate_keys = (
        "state",
        "status",
        "sample_state",
        "sampleStatus",
        "annotation_state",
        "annotationStatus",
    )

    for key in candidate_keys:
        normalized = normalize_state(sample.get(key))
        if normalized:
            return normalized, key

    for parent_key, parent_value in sample.items():
        if not isinstance(parent_value, dict):
            continue
        for key in candidate_keys:
            normalized = normalize_state(parent_value.get(key))
            if normalized:
                return normalized, f"{parent_key}.{key}"

    return None, None


def build_runtime_config(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    request_config = config.get("request", {})
    delete_config = config.get("delete", {})
    target_config = config.get("target", {})

    runtime = {
        "base_url": args.base_url or config.get("base_url"),
        "task_id": args.task_id if args.task_id is not None else target_config.get("task_id"),
        "token": args.token or config.get("token"),
        "sample_states": args.states or target_config.get("sample_states", ["SKIPPED"]),
        "start_page": request_config.get("start_page", 0),
        "page_size": args.page_size or request_config.get("page_size", 100),
        "delete_batch_size": args.batch_size or delete_config.get("batch_size", 100),
        "request_interval_seconds": (
            args.interval if args.interval is not None else request_config.get("interval_seconds", 0.5)
        ),
        "request_timeout_seconds": (
            args.timeout if args.timeout is not None else request_config.get("timeout_seconds", 15)
        ),
        "delete_timeout_seconds": (
            args.delete_timeout if args.delete_timeout is not None else delete_config.get("timeout_seconds", 30)
        ),
        "max_retries": args.retries if args.retries is not None else request_config.get("max_retries", 2),
        "verify_ssl": args.verify_ssl if args.verify_ssl is not None else request_config.get("verify_ssl", True),
        "auto_confirm": args.yes or bool(delete_config.get("auto_confirm", False)),
        "dry_run": args.dry_run or bool(delete_config.get("dry_run", False)),
        "fail_report_path": args.fail_report or delete_config.get("fail_report_path", "failed_batches.json"),
    }

    required_fields = ["base_url", "task_id", "token"]
    missing = [field for field in required_fields if runtime.get(field) in (None, "", [])]
    if missing:
        raise ValueError(f"缺少必要配置: {', '.join(missing)}")

    if not isinstance(runtime["sample_states"], list) or not runtime["sample_states"]:
        raise ValueError("sample_states 必须是非空列表。")

    runtime["sample_states"] = [state for state in (normalize_state(item) for item in runtime["sample_states"]) if state]
    if not runtime["sample_states"]:
        raise ValueError("sample_states 必须至少包含一个有效状态。")

    if runtime["page_size"] < 1:
        raise ValueError("page_size 必须 >= 1")
    if runtime["start_page"] < 0:
        raise ValueError("start_page 必须 >= 0")
    if runtime["delete_batch_size"] < 1:
        raise ValueError("delete_batch_size 必须 >= 1")
    if runtime["request_timeout_seconds"] <= 0 or runtime["delete_timeout_seconds"] <= 0:
        raise ValueError("timeout 必须 > 0")
    if runtime["max_retries"] < 0:
        raise ValueError("max_retries 必须 >= 0")

    runtime["sample_state_aliases"] = build_state_aliases(runtime["sample_states"])
    runtime["headers"] = {
        "Authorization": f"Bearer {runtime['token']}",
        "Content-Type": "application/json",
    }
    runtime["samples_url"] = f"{runtime['base_url'].rstrip('/')}/api/v1/tasks/{runtime['task_id']}/samples"
    return runtime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量删除 LabelU 中指定状态的样本。")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="配置文件路径，默认使用当前目录下的 config.yaml")
    parser.add_argument("--base-url", help="LabelU 服务地址，例如 http://127.0.0.1:38000")
    parser.add_argument("--task-id", type=int, help="任务 ID")
    parser.add_argument("--token", help="访问 token，不传时从配置文件读取")
    parser.add_argument("--states", nargs="+", help="需要筛选并删除的样本状态，可传多个，例如 SKIPPED REJECTED")
    parser.add_argument("--page-size", type=int, help="分页拉取大小")
    parser.add_argument("--batch-size", type=int, help="单次删除的样本数量")
    parser.add_argument("--interval", type=float, help="请求之间的间隔秒数")
    parser.add_argument("--timeout", type=float, help="查询请求超时秒数")
    parser.add_argument("--delete-timeout", type=float, help="删除请求超时秒数")
    parser.add_argument("--retries", type=int, help="请求失败后的最大重试次数")
    parser.add_argument("--verify-ssl", dest="verify_ssl", action="store_true", help="启用 SSL 证书校验")
    parser.add_argument("--no-verify-ssl", dest="verify_ssl", action="store_false", help="关闭 SSL 证书校验")
    parser.add_argument("--dry-run", action="store_true", help="只扫描不删除")
    parser.add_argument("--yes", action="store_true", help="跳过确认直接执行删除")
    parser.add_argument("--fail-report", help="失败批次报告输出路径")
    parser.set_defaults(verify_ssl=None)
    return parser.parse_args()


def request_with_retry(method: str, url: str, *, retries: int, interval: float, **kwargs: Any) -> requests.Response:
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = requests.request(method, url, **kwargs)
            if response.status_code not in RETRY_STATUS_CODES or attempt >= retries:
                return response

            wait_seconds = interval * (attempt + 1)
            print(f"请求返回 {response.status_code}，第 {attempt + 1} 次重试前等待 {wait_seconds:.1f} 秒。")
            time.sleep(wait_seconds)
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= retries:
                break
            wait_seconds = interval * (attempt + 1)
            print(f"请求失败，第 {attempt + 1} 次重试前等待 {wait_seconds:.1f} 秒: {exc}")
            time.sleep(wait_seconds)

    raise RuntimeError(f"请求最终失败: {last_error}") from last_error


def get_target_sample_ids(runtime: dict[str, Any]) -> list[int]:
    target_ids: list[int] = []
    seen_ids: set[int] = set()
    page = runtime["start_page"]
    page_size = runtime["page_size"]
    target_states = runtime["sample_state_aliases"]
    state_counts: dict[str, int] = {}
    missing_state_examples: list[int] = []
    total_count: int | None = None
    scanned_count = 0

    while True:
        print(f"正在拉取第 {page} 页样本...")
        params = {"page": page, "size": page_size}
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

        payload = response.json()
        data = payload.get("data", [])
        meta_data = payload.get("meta_data") or {}
        if isinstance(meta_data.get("total"), int):
            total_count = meta_data["total"]

        if not data:
            print("所有页面已扫描完成。")
            break

        scanned_count += len(data)

        current_ids: list[int] = []
        for sample in data:
            sample_id = sample.get("id")
            state, _ = extract_sample_state(sample)

            if state is None:
                if isinstance(sample_id, int) and len(missing_state_examples) < 10:
                    missing_state_examples.append(sample_id)
                continue

            state_counts[state] = state_counts.get(state, 0) + 1
            if state in target_states and isinstance(sample_id, int) and sample_id not in seen_ids:
                current_ids.append(sample_id)
                seen_ids.add(sample_id)

        target_ids.extend(current_ids)
        print(f"第 {page} 页处理完成，命中 {len(current_ids)} 条，累计 {len(target_ids)} 条。")

        if len(data) < page_size:
            break

        if total_count is not None and scanned_count >= total_count:
            break

        page += 1
        time.sleep(runtime["request_interval_seconds"])

    if state_counts:
        top_states = sorted(state_counts.items(), key=lambda item: item[1], reverse=True)[:10]
        print("扫描到的状态分布（前 10 项）：")
        for state, count in top_states:
            print(f"- {state}: {count}")

    if missing_state_examples:
        print(f"以下样本没有识别到状态字段，示例 ID: {missing_state_examples}")

    return target_ids


def write_fail_report(report_path: Path, failed_batches: list[dict[str, Any]]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as file:
        json.dump(failed_batches, file, ensure_ascii=False, indent=2)
    print(f"失败报告已写入: {report_path}")


def delete_samples(ids: list[int], runtime: dict[str, Any]) -> None:
    if not ids:
        print("没有需要删除的样本。")
        return

    total = len(ids)
    batch_size = runtime["delete_batch_size"]
    batches = (total + batch_size - 1) // batch_size
    print(f"准备处理 {total} 条样本，共 {batches} 批，每批最多 {batch_size} 条。")

    if runtime["dry_run"]:
        preview_ids = ids[: min(10, len(ids))]
        print(f"当前为预演模式，不会执行删除。前 {len(preview_ids)} 个样本 ID: {preview_ids}")
        return

    ok_count = 0
    failed_batches: list[dict[str, Any]] = []

    for i in range(0, total, batch_size):
        chunk = ids[i : i + batch_size]
        batch_index = i // batch_size + 1
        print(f"正在删除第 {batch_index}/{batches} 批 ({len(chunk)} 条)...", end=" ")

        response = None
        error_text = None
        try:
            response = request_with_retry(
                "DELETE",
                runtime["samples_url"],
                retries=runtime["max_retries"],
                interval=runtime["request_interval_seconds"],
                headers=runtime["headers"],
                json={"sample_ids": chunk},
                timeout=runtime["delete_timeout_seconds"],
                verify=runtime["verify_ssl"],
            )
        except Exception as exc:
            error_text = str(exc)

        if response is not None and response.status_code in SUCCESS_STATUS_CODES:
            print("成功")
            ok_count += len(chunk)
        else:
            if response is not None:
                error_text = f"状态码: {response.status_code}, 响应: {response.text}"
            print(f"失败 ({error_text})")
            failed_batches.append(
                {
                    "batch_index": batch_index,
                    "sample_ids": chunk,
                    "error": error_text,
                }
            )

        if batch_index < batches:
            time.sleep(runtime["request_interval_seconds"])

    print("\n--- 批量删除结束 ---")
    print(f"成功删除: {ok_count} / {total}")

    if failed_batches:
        report_path = Path(runtime["fail_report_path"])
        write_fail_report(report_path, failed_batches)
        print(f"失败批次数量: {len(failed_batches)}")


def confirm_delete(count: int, runtime: dict[str, Any]) -> bool:
    if runtime["auto_confirm"]:
        return True

    answer = input(
        f"确认删除状态为 {runtime['sample_states']} 的 {count} 条样本吗？输入 y 继续，其它任意键取消: "
    ).strip()
    return answer.lower() == "y"


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
    print(f"- 目标状态: {runtime['sample_states']}")
    print(f"- 实际匹配状态: {sorted(runtime['sample_state_aliases'])}")
    print(f"- 预演模式: {runtime['dry_run']}")
    print(f"- 删除批次大小: {runtime['delete_batch_size']}")

    try:
        target_ids = get_target_sample_ids(runtime)
    except Exception as exc:
        print(f"扫描样本失败: {exc}")
        return 1

    print(f"扫描结束，共找到 {len(target_ids)} 条匹配样本。")
    if not target_ids:
        return 0

    if not runtime["dry_run"] and not confirm_delete(len(target_ids), runtime):
        print("操作已取消。")
        return 0

    try:
        delete_samples(target_ids, runtime)
    except Exception as exc:
        print(f"执行删除失败: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
