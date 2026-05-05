from __future__ import annotations

from pathlib import Path


ALLOWED_RUNTIMES = {"python", "node", "shell"}
ALLOWED_PARAM_TYPES = {"text", "textarea", "password", "select", "boolean", "path", "filelist"}


def normalize_param(param: dict) -> dict:
    key = str(param.get("key", "")).strip()
    if not key:
        raise ValueError("params[].key 不能为空")
    param_type = str(param.get("type", "text")).strip().lower()
    if param_type not in ALLOWED_PARAM_TYPES:
        raise ValueError(f"params[{key}] type 不支持: {param_type}")
    normalized = {
        "key": key,
        "label": str(param.get("label", key)).strip(),
        "type": param_type,
        "required": bool(param.get("required", False)),
        "default": param.get("default", ""),
        "options": param.get("options", []),
        "cli_arg": str(param.get("cli_arg", key.replace("_", "-"))).strip(),
    }
    if param_type == "select" and not isinstance(normalized["options"], list):
        raise ValueError(f"params[{key}] options 必须是数组")
    return normalized


def normalize_manifest(raw: dict, plugin_root: Path) -> dict:
    required = ["schema_version", "id", "name", "version", "group", "desc", "runtime", "entry"]
    for key in required:
        if not str(raw.get(key, "")).strip():
            raise ValueError(f"manifest 缺少必填字段: {key}")

    runtime = str(raw["runtime"]).strip().lower()
    if runtime not in ALLOWED_RUNTIMES:
        raise ValueError(f"runtime 不支持: {runtime}")

    entry = str(raw["entry"]).strip()
    entry_path = (plugin_root / entry).resolve()
    if not entry_path.exists():
        raise ValueError(f"entry 文件不存在: {entry}")

    params = raw.get("params", [])
    if not isinstance(params, list):
        raise ValueError("params 必须是数组")

    normalized_params = [normalize_param(item or {}) for item in params]
    return {
        "schema_version": str(raw["schema_version"]).strip(),
        "id": str(raw["id"]).strip(),
        "name": str(raw["name"]).strip(),
        "version": str(raw["version"]).strip(),
        "group": str(raw["group"]).strip(),
        "desc": str(raw["desc"]).strip(),
        "runtime": runtime,
        "entry": entry,
        "params": normalized_params,
        "status": str(raw.get("status", "ready")).strip(),
        "tags": raw.get("tags", []),
        "usage": str(raw.get("usage", "")).strip(),
        "timeout_sec": int(raw.get("timeout_sec", 1200)),
        "install": raw.get("install", {}),
        "updatedAt": str(raw.get("updatedAt", "")).strip(),
        "pluginRoot": str(plugin_root),
    }
