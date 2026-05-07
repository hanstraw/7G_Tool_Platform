import argparse
import csv
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
import yaml


DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yaml")


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(config, dict):
        raise ValueError("配置文件格式错误，根节点必须是对象。")
    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="下载 LabelU 指定任务里的所有图片。")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="配置文件路径")
    parser.add_argument("--base-url", help="LabelU 服务地址，例如 http://113.141.72.253:38000")
    parser.add_argument("--task-id", type=int, help="任务 ID")
    parser.add_argument("--output-dir", help="图片下载目录")
    parser.add_argument("--token", help="访问 token，不传时读取环境变量 LABELU_TOKEN，再读取配置文件")
    parser.add_argument("--page-start", type=int, help="样本列表起始页，LabelU 通常是 0")
    parser.add_argument("--page-end", type=int, help="样本列表结束页，包含；不传表示全部")
    parser.add_argument("--page-size", type=int, help="分页大小")
    parser.add_argument("--interval", type=float, help="请求间隔秒数")
    parser.add_argument("--timeout", type=float, help="请求超时秒数")
    parser.add_argument("--retries", type=int, help="请求失败后的最大重试次数")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在文件；默认跳过")
    parser.add_argument("--no-prefix-duplicate", action="store_true", help="文件名冲突时不加 sample_id 前缀")
    parser.add_argument("--verify-ssl", dest="verify_ssl", action="store_true", help="启用 SSL 证书校验")
    parser.add_argument("--no-verify-ssl", dest="verify_ssl", action="store_false", help="关闭 SSL 证书校验")
    parser.set_defaults(verify_ssl=None)
    return parser.parse_args()


def build_runtime_config(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    target_config = config.get("target", {})
    request_config = config.get("request", {})
    download_config = config.get("download", {})
    runtime = {
        "base_url": args.base_url or config.get("base_url"),
        "task_id": args.task_id if args.task_id is not None else target_config.get("task_id"),
        "output_dir": args.output_dir or target_config.get("output_dir"),
        "token": args.token or os.getenv("LABELU_TOKEN") or config.get("token"),
        "page_start": args.page_start if args.page_start is not None else request_config.get("page_start", 0),
        "page_end": args.page_end if args.page_end is not None else request_config.get("page_end"),
        "page_size": args.page_size or request_config.get("page_size", 10),
        "request_interval_seconds": args.interval if args.interval is not None else request_config.get("interval_seconds", 0.03),
        "request_timeout_seconds": args.timeout if args.timeout is not None else request_config.get("timeout_seconds", 30),
        "max_retries": args.retries if args.retries is not None else request_config.get("max_retries", 2),
        "verify_ssl": args.verify_ssl if args.verify_ssl is not None else request_config.get("verify_ssl", True),
        "skip_existing": not args.overwrite if args.overwrite else bool(download_config.get("skip_existing", True)),
        "prefix_sample_id_on_duplicate": (
            False if args.no_prefix_duplicate else bool(download_config.get("prefix_sample_id_on_duplicate", True))
        ),
    }
    required = ["base_url", "task_id", "output_dir", "token"]
    missing = [field for field in required if runtime.get(field) in (None, "", [])]
    if missing:
        raise ValueError(f"缺少必要配置: {', '.join(missing)}")
    if runtime["page_start"] in (None, ""):
        runtime["page_start"] = 0
    if runtime["page_end"] == "":
        runtime["page_end"] = None
    if runtime["page_start"] < 0:
        raise ValueError("page_start 必须 >= 0")
    if runtime["page_end"] is not None and runtime["page_end"] < runtime["page_start"]:
        raise ValueError("page_end 不能小于 page_start")
    if runtime["page_size"] < 1:
        raise ValueError("page_size 必须 >= 1")
    if runtime["request_timeout_seconds"] <= 0:
        raise ValueError("timeout 必须 > 0")
    if runtime["max_retries"] < 0:
        raise ValueError("retries 必须 >= 0")

    base_url = runtime["base_url"].rstrip("/")
    runtime["base_url"] = base_url
    runtime["samples_url"] = f"{base_url}/api/v1/tasks/{runtime['task_id']}/samples"
    runtime["headers"] = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {runtime['token']}",
        "User-Agent": "Mozilla/5.0 LabelU image downloader",
    }
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


def safe_filename(filename: str) -> str:
    filename = filename.strip().replace("\\", "_").replace("/", "_")
    filename = re.sub(r'[<>:"|?*]+', "_", filename)
    return filename or "unnamed"


def get_file_info(sample: dict[str, Any]) -> tuple[str | None, str | None]:
    file_info = sample.get("file") or {}
    filename = file_info.get("filename")
    file_url = file_info.get("url")
    if not filename and file_url:
        filename = Path(str(file_url).split("?")[0]).name
    return filename, file_url


def resolve_download_url(runtime: dict[str, Any], file_url: str) -> str:
    if file_url.startswith("http://") or file_url.startswith("https://"):
        return file_url
    return urljoin(runtime["base_url"] + "/", file_url.lstrip("/"))


def make_output_path(runtime: dict[str, Any], output_dir: Path, sample: dict[str, Any], filename: str) -> Path:
    safe_name = safe_filename(filename)
    path = output_dir / safe_name
    if runtime["prefix_sample_id_on_duplicate"] and path.exists():
        sample_id = sample.get("id", "sample")
        prefixed = output_dir / f"{sample_id}_{safe_name}"
        if prefixed != path:
            path = prefixed
    return path


def download_file(runtime: dict[str, Any], url: str, output_path: Path) -> int:
    tmp_path = output_path.with_suffix(output_path.suffix + ".part")
    response = api_request(runtime, "GET", url, headers=runtime["headers"], stream=True)
    if response.status_code != 200:
        raise RuntimeError(f"下载失败，状态码: {response.status_code}，响应: {response.text[:300]}")
    total = 0
    with tmp_path.open("wb") as file:
        for chunk in response.iter_content(chunk_size=1024 * 512):
            if not chunk:
                continue
            file.write(chunk)
            total += len(chunk)
    tmp_path.replace(output_path)
    return total


def write_manifest(output_dir: Path, rows: list[dict[str, Any]]) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    manifest_path = output_dir / f"download_manifest_{timestamp}.csv"
    fieldnames = [
        "task_id",
        "page",
        "sample_id",
        "inner_id",
        "state",
        "filename",
        "file_url",
        "saved_path",
        "bytes",
        "status",
        "detail",
    ]
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return manifest_path


def scan_and_download(runtime: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    output_dir = Path(runtime["output_dir"])
    if not output_dir.is_absolute():
        output_dir = Path(__file__).parent / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    stats = {"pages": 0, "samples": 0, "downloaded": 0, "skipped": 0, "failed": 0, "missing_file": 0}
    page = runtime["page_start"]
    while True:
        if runtime["page_end"] is not None and page > runtime["page_end"]:
            break
        print(f"正在拉取第 {page} 页样本...")
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
        stats["pages"] += 1
        stats["samples"] += len(samples)

        for sample in samples:
            filename, file_url = get_file_info(sample)
            row = {
                "task_id": runtime["task_id"],
                "page": page,
                "sample_id": sample.get("id", ""),
                "inner_id": sample.get("inner_id", ""),
                "state": sample.get("state", ""),
                "filename": filename or "",
                "file_url": file_url or "",
                "saved_path": "",
                "bytes": "",
                "status": "",
                "detail": "",
            }
            if not filename or not file_url:
                row["status"] = "MISSING_FILE"
                row["detail"] = "样本缺少 file.filename 或 file.url"
                stats["missing_file"] += 1
                rows.append(row)
                continue

            output_path = make_output_path(runtime, output_dir, sample, filename)
            row["saved_path"] = str(output_path)
            if runtime["skip_existing"] and output_path.exists():
                row["status"] = "SKIPPED"
                row["bytes"] = output_path.stat().st_size
                stats["skipped"] += 1
                rows.append(row)
                continue

            try:
                download_url = resolve_download_url(runtime, file_url)
                size = download_file(runtime, download_url, output_path)
                row["status"] = "DOWNLOADED"
                row["bytes"] = size
                stats["downloaded"] += 1
                print(f"已下载 inner_id={sample.get('inner_id')} -> {output_path.name}")
            except Exception as exc:
                row["status"] = "FAILED"
                row["detail"] = str(exc)
                stats["failed"] += 1
                print(f"下载失败 inner_id={sample.get('inner_id')} filename={filename}: {exc}")
            rows.append(row)
            time.sleep(runtime["request_interval_seconds"])

        if len(samples) < runtime["page_size"]:
            break
        page += 1
    manifest_path = write_manifest(output_dir, rows)
    stats["manifest_path"] = str(manifest_path)  # type: ignore[assignment]
    stats["output_dir"] = str(output_dir)  # type: ignore[assignment]
    return rows, stats


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
    print(f"- 输出目录: {runtime['output_dir']}")
    print(f"- 页码范围: {runtime['page_start']} - {runtime['page_end'] if runtime['page_end'] is not None else '全部'}")
    print(f"- 已存在文件: {'跳过' if runtime['skip_existing'] else '覆盖'}")

    try:
        _, stats = scan_and_download(runtime)
    except Exception as exc:
        print(f"执行失败: {exc}")
        return 1

    print("\n--- 汇总 ---")
    print(f"扫描页数: {stats['pages']}")
    print(f"样本数: {stats['samples']}")
    print(f"已下载: {stats['downloaded']}")
    print(f"已跳过: {stats['skipped']}")
    print(f"缺文件字段: {stats['missing_file']}")
    print(f"失败: {stats['failed']}")
    print(f"输出目录: {stats['output_dir']}")
    print(f"下载清单: {stats['manifest_path']}")
    return 0 if stats["failed"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
