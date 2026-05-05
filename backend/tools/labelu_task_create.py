"""
LabelU 任务创建工具（平台内置版）

功能：
1) 登录 LabelU
2) 创建任务（基础配置）
"""

from __future__ import annotations

import argparse
import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import urllib3


@dataclass
class LabelUClient:
    base_url: str
    login_path: str = "/api/v1/users/login"
    create_task_path: str = "/api/v1/tasks"
    timeout: int = 30
    verify_ssl: bool = True

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.login_path = self.login_path if self.login_path.startswith("/") else f"/{self.login_path}"
        self.create_task_path = self.create_task_path if self.create_task_path.startswith("/") else f"/{self.create_task_path}"

        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Origin": self.base_url,
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/147.0.0.0 Safari/537.36"
                ),
            }
        )

    def login(self, username: str, password: str) -> Dict[str, Any]:
        self.session.headers["Referer"] = f"{self.base_url}/login"
        resp = self.session.post(
            f"{self.base_url}{self.login_path}",
            json={"username": username, "password": password},
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        self._raise_for_status(resp, "登录失败")
        data = resp.json() if resp.content else {}
        token = self._extract_token(data)
        if token:
            self.session.headers["Authorization"] = self._normalize_bearer_token(token)
        return data

    def create_task(self, task_name: str, media_type: str = "IMAGE", extra_json: Optional[Dict[str, Any]] = None):
        self.session.headers["Referer"] = f"{self.base_url}/tasks/0/edit?isNew=true"
        payload: Dict[str, Any] = {"name": task_name, "media_type": media_type}
        if extra_json:
            payload.update(extra_json)
        resp = self.session.post(
            f"{self.base_url}{self.create_task_path}",
            json=payload,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        self._raise_for_status(resp, "创建任务失败")
        return resp.json() if resp.content else {}

    def upload_attachment(self, task_id: int, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"文件不存在: {path}")
        mime, _ = mimetypes.guess_type(str(path))
        if not mime:
            mime = "application/octet-stream"

        self.session.headers["Referer"] = f"{self.base_url}/tasks/{task_id}/edit?isNew=true"
        with path.open("rb") as fp:
            resp = self.session.post(
                f"{self.base_url}{self.create_task_path}/{task_id}/attachments",
                files={"file": (path.name, fp, mime)},
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
        self._raise_for_status(resp, f"上传失败: {path.name}")
        return resp.json() if resp.content else {}

    @staticmethod
    def _extract_token(data: Dict[str, Any]) -> Optional[str]:
        for key in ("token", "access_token", "accessToken"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
        nested = data.get("data")
        if isinstance(nested, dict):
            for key in ("token", "access_token", "accessToken"):
                value = nested.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        return None

    @staticmethod
    def _normalize_bearer_token(token: str) -> str:
        token_text = str(token).strip()
        if token_text.lower().startswith("bearer "):
            return token_text
        return f"Bearer {token_text}"

    @staticmethod
    def _raise_for_status(resp: requests.Response, prefix: str) -> None:
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(f"{prefix}: {resp.text.strip() or exc}") from exc


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_upload_images(value: str) -> List[str]:
    text = str(value or "").strip()
    if not text:
        return []
    # 支持英文逗号、分号或换行分隔。
    normalized = text.replace(";", "\n").replace(",", "\n")
    return [item.strip() for item in normalized.splitlines() if item.strip()]


def extract_task_id(data: Dict[str, Any]) -> Optional[int]:
    for key in ("id", "task_id", "taskId"):
        value = data.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    nested = data.get("data")
    if isinstance(nested, dict):
        return extract_task_id(nested)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="登录 LabelU 并创建任务")
    parser.add_argument("--base-url", required=True, help="LabelU 地址，例如 http://127.0.0.1:8080")
    parser.add_argument("--username", required=True, help="登录账号")
    parser.add_argument("--password", required=True, help="登录密码")
    parser.add_argument("--task-name", required=True, help="任务名称")
    parser.add_argument("--media-type", default="IMAGE", help="媒体类型，默认 IMAGE")
    parser.add_argument("--login-path", default="/api/v1/users/login", help="登录接口路径")
    parser.add_argument("--create-task-path", default="/api/v1/tasks", help="创建任务接口路径")
    parser.add_argument("--insecure", default="true", help="是否跳过 HTTPS 证书校验(true/false)")
    parser.add_argument("--extra-json", default="", help="可选，额外任务字段 JSON 对象字符串")
    parser.add_argument("--upload-images", default="", help="可选，图片路径列表（逗号/分号/换行分隔）")
    args = parser.parse_args()

    extra_payload = None
    if args.extra_json.strip():
        extra_payload = json.loads(args.extra_json)
        if not isinstance(extra_payload, dict):
            raise SystemExit("extra-json 必须是 JSON 对象")

    client = LabelUClient(
        base_url=args.base_url,
        login_path=args.login_path,
        create_task_path=args.create_task_path,
        verify_ssl=not parse_bool(args.insecure),
    )
    login_resp = client.login(args.username, args.password)
    create_resp = client.create_task(args.task_name, args.media_type, extra_payload)
    task_id = extract_task_id(create_resp)
    upload_paths = parse_upload_images(args.upload_images)
    upload_results: List[Dict[str, Any]] = []
    if upload_paths:
        if task_id is None:
            raise SystemExit("创建任务成功但未解析到 task_id，无法上传图片。")
        for file_path in upload_paths:
            upload_results.append(client.upload_attachment(task_id, file_path))

    print("登录成功。")
    print("登录返回：")
    print(json.dumps(login_resp, ensure_ascii=False))
    print("任务创建成功：")
    print(json.dumps(create_resp, ensure_ascii=False))
    if upload_results:
        print(f"图片上传成功（{len(upload_results)}张）：")
        print(json.dumps(upload_results, ensure_ascii=False))


if __name__ == "__main__":
    main()
