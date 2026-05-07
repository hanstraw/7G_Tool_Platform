import json
import re
from pathlib import Path
from urllib.parse import urlparse

import requests


ROOT_DIR = Path(__file__).resolve().parent
TOKEN_FILE = Path(r"C:\Users\Xiao\Desktop\zx.txt")
REFERENCE_JSON = Path(r"C:\Users\Xiao\Downloads\占道经营 (3).json")


def read_token_and_target_task():
    text = TOKEN_FILE.read_text(encoding="utf-8-sig")

    token_match = re.search(r"^Bearer\s+\S+", text, re.MULTILINE)
    if not token_match:
        raise RuntimeError(f"未在 {TOKEN_FILE} 中找到 Bearer token")

    task_url_match = re.search(r"https?://[^\s]+/tasks/(\d+)", text)
    if not task_url_match:
        raise RuntimeError(f"未在 {TOKEN_FILE} 中找到目标任务 URL")

    task_url = task_url_match.group(0)
    parsed = urlparse(task_url)
    api_base = f"{parsed.scheme}://{parsed.netloc}/api"
    target_task_id = int(task_url_match.group(1))

    return token_match.group(0), api_base, target_task_id


def read_reference_task_id() -> int:
    data = json.loads(REFERENCE_JSON.read_text(encoding="utf-8-sig"))
    if not data:
        raise RuntimeError(f"{REFERENCE_JSON} 中没有样本数据")

    for item in data:
        url = item.get("url", "")
        match = re.search(r"/tasks/attachment/upload/(\d+)/", url)
        if match:
            return int(match.group(1))

    raise RuntimeError("无法从 JSON 的 url 字段中识别参考任务 ID")


def get_task(session: requests.Session, api_base: str, task_id: int) -> dict:
    response = session.get(f"{api_base}/v1/tasks/{task_id}", params={"task_id": task_id}, timeout=30)
    response.raise_for_status()
    return response.json()["data"]


def update_task_config(session: requests.Session, api_base: str, target_task: dict, config: str) -> dict:
    payload = {
        "id": target_task["id"],
        "name": target_task["name"],
        "description": target_task.get("description"),
        "tips": target_task.get("tips"),
        "media_type": target_task["media_type"],
        "config": config,
    }
    response = session.patch(f"{api_base}/v1/tasks/{target_task['id']}", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["data"]


def main() -> None:
    token, api_base, target_task_id = read_token_and_target_task()
    reference_task_id = read_reference_task_id()

    session = requests.Session()
    session.headers.update({"Authorization": token})

    reference_task = get_task(session, api_base, reference_task_id)
    target_task = get_task(session, api_base, target_task_id)

    updated_task = update_task_config(session, api_base, target_task, reference_task["config"])
    verified_task = get_task(session, api_base, target_task_id)

    if verified_task["config"] != reference_task["config"]:
        raise RuntimeError("配置写入后校验失败: 目标任务 config 与参考任务 config 不一致")

    config = json.loads(verified_task["config"])
    tools = [tool["tool"] for tool in config.get("tools", [])]

    print(f"参考任务: {reference_task_id}")
    print(f"目标任务: {target_task_id}")
    print(f"目标任务状态: {updated_task.get('status')}")
    print(f"工具结构: {', '.join(tools)}")
    print("配置已写入并校验一致")


if __name__ == "__main__":
    main()
