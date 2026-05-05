from __future__ import annotations

from pathlib import Path
import json
from datetime import datetime
import uuid


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
CONFIG_DIR = DATA_DIR / "configs"
TASK_DIR = DATA_DIR / "tasks"
LOG_DIR = DATA_DIR / "logs"
ARTIFACT_DIR = DATA_DIR / "artifacts"
DB_DIR = DATA_DIR / "db"
PLUGIN_DIR = DATA_DIR / "plugins"


def ensure_data_dirs() -> None:
    for path in [CONFIG_DIR, TASK_DIR, LOG_DIR, ARTIFACT_DIR, DB_DIR, PLUGIN_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path, default_value):
    if not path.exists():
        return default_value
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_value


def load_environments():
    return _load_json(CONFIG_DIR / "environments.json", {"current": "DEV", "items": []})


def load_tools():
    return _load_json(CONFIG_DIR / "tools.json", {"tools": []})


def get_tool_by_id(tool_id: str):
    tools_data = load_tools()
    for tool in tools_data.get("tools", []):
        if tool.get("id") == tool_id:
            return tool
    return None


def create_execution_log(tool_id: str, content: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_id = uuid.uuid4().hex[:8]
    file_name = f"{timestamp}_{tool_id}_{short_id}.log"
    log_path = LOG_DIR / file_name
    log_path.write_text(content, encoding="utf-8")
    return str(log_path)


def read_execution_log(file_name: str) -> str | None:
    safe_name = Path(file_name).name
    log_path = LOG_DIR / safe_name
    if not log_path.exists():
        return None
    return log_path.read_text(encoding="utf-8")


def create_task(task: dict) -> str:
    task_id = task.get("taskId") or uuid.uuid4().hex
    task["taskId"] = task_id
    task_path = TASK_DIR / f"{task_id}.json"
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    return task_id


def update_task(task_id: str, patch: dict) -> dict | None:
    current = read_task(task_id)
    if current is None:
        return None
    current.update(patch)
    current["updatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    task_path = TASK_DIR / f"{task_id}.json"
    task_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return current


def read_task(task_id: str) -> dict | None:
    task_path = TASK_DIR / f"{task_id}.json"
    return _load_json(task_path, None)
