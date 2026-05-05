from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import json
import subprocess
import sys
import traceback
import uuid

from storage import LOG_DIR, create_task, update_task, read_task


class PluginRunner:
    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    @staticmethod
    def _normalize(value):
        if value is None:
            return ""
        text = str(value).strip()
        if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
            text = text[1:-1].strip()
        return text

    def submit(self, plugin: dict, raw_params: dict) -> dict:
        params = {k: self._normalize(v) for k, v in (raw_params or {}).items()}
        missing = []
        for item in plugin.get("params", []):
            if item.get("required") and not params.get(item.get("key")):
                missing.append(item.get("key"))
        if missing:
            raise ValueError(f"缺少必填参数: {', '.join(missing)}")

        task = {
            "taskId": uuid.uuid4().hex,
            "toolId": plugin.get("id"),
            "toolName": plugin.get("name"),
            "status": "pending",
            "params": params,
            "createdAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "returnCode": None,
            "stdout": "",
            "stderr": "",
            "command": "",
            "logFile": "",
        }
        task_id = create_task(task)
        self._executor.submit(self._run_task, task_id, plugin, params)
        return {"taskId": task_id, "status": "pending"}

    def _build_command(self, plugin: dict, params: dict) -> tuple[list[str], Path]:
        plugin_root = Path(plugin["pluginRoot"]).resolve()
        entry_path = (plugin_root / plugin["entry"]).resolve()
        runtime = plugin.get("runtime")
        if runtime == "python":
            command = [sys.executable, str(entry_path)]
        elif runtime == "node":
            command = ["node", str(entry_path)]
        elif runtime == "shell":
            command = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(entry_path)]
        else:
            raise ValueError(f"不支持的 runtime: {runtime}")

        for item in plugin.get("params", []):
            key = item.get("key")
            value = self._normalize(params.get(key, item.get("default", "")))
            if value == "":
                continue
            cli_arg = item.get("cli_arg") or key.replace("_", "-")
            if item.get("type") == "boolean":
                if value.lower() in {"1", "true", "yes", "on"}:
                    command.append(f"--{cli_arg}")
                continue
            command.extend([f"--{cli_arg}", value])
        return command, plugin_root

    @staticmethod
    def _extract_artifacts(stdout: str, cwd: Path) -> list[dict]:
        artifacts: list[dict] = []
        seen: set[str] = set()
        # Plugin can explicitly print lines like: [ARTIFACT] C:\path\to\file.pdf
        for line in (stdout or "").splitlines():
            text = line.strip()
            if not text.startswith("[ARTIFACT]"):
                continue
            raw_path = text.replace("[ARTIFACT]", "", 1).strip().strip('"').strip("'")
            if not raw_path:
                continue
            path = Path(raw_path)
            if not path.is_absolute():
                path = (cwd / path).resolve()
            if not path.exists() or not path.is_file():
                continue
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            stat = path.stat()
            artifacts.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "size": int(stat.st_size),
                    "ext": path.suffix.lower(),
                }
            )
        return artifacts

    def _run_task(self, task_id: str, plugin: dict, params: dict) -> None:
        start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_task(task_id, {"status": "running", "startedAt": start})
        log_file = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{plugin.get('id')}_{task_id[:8]}.log"
        log_path = LOG_DIR / log_file
        try:
            command, cwd = self._build_command(plugin, params)
            timeout_sec = int(plugin.get("timeout_sec", 1200))
            result = subprocess.run(
                command,
                cwd=str(cwd),
                text=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_sec,
                check=False,
            )
            end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status = "success" if result.returncode == 0 else "failed"
            log_content = (
                f"[START] {start}\n[END] {end}\n[TOOL] {plugin.get('id')}\n"
                f"[RETURN_CODE] {result.returncode}\n[PARAMS] {json.dumps(params, ensure_ascii=False)}\n"
                f"[COMMAND] {' '.join(command)}\n[STDOUT]\n{result.stdout}\n[STDERR]\n{result.stderr}\n"
            )
            log_path.write_text(log_content, encoding="utf-8")
            artifacts = self._extract_artifacts(result.stdout, cwd)
            update_task(
                task_id,
                {
                    "status": status,
                    "endedAt": end,
                    "returnCode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "command": " ".join(command),
                    "logFile": log_file,
                    "artifacts": artifacts,
                },
            )
        except subprocess.TimeoutExpired as exc:
            end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            error_output = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
            log_path.write_text(
                f"[START] {start}\n[END] {end}\n[TOOL] {plugin.get('id')}\n[ERROR] timeout\n[STDOUT]\n{output}\n[STDERR]\n{error_output}\n",
                encoding="utf-8",
            )
            update_task(task_id, {"status": "timeout", "endedAt": end, "stderr": "执行超时", "logFile": log_file})
        except Exception as exc:
            end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            detail = traceback.format_exc()
            log_path.write_text(
                f"[START] {start}\n[END] {end}\n[TOOL] {plugin.get('id')}\n[ERROR] {exc}\n[TRACEBACK]\n{detail}\n",
                encoding="utf-8",
            )
            update_task(task_id, {"status": "failed", "endedAt": end, "stderr": str(exc), "logFile": log_file})

    @staticmethod
    def get_task(task_id: str) -> dict | None:
        return read_task(task_id)
