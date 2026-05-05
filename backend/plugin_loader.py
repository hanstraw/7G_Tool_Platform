from __future__ import annotations

from pathlib import Path
import json

from manifest_schema import normalize_manifest
from storage import PLUGIN_DIR, load_tools


def _read_manifest(manifest_path: Path) -> dict:
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"manifest JSON 无效: {exc}") from exc
    return normalize_manifest(raw, manifest_path.parent)


def list_plugins() -> list[dict]:
    plugins: list[dict] = []
    if PLUGIN_DIR.exists():
        for manifest_path in sorted(PLUGIN_DIR.glob("*/manifest.json")):
            try:
                plugins.append(_read_manifest(manifest_path))
            except Exception:
                continue
    if plugins:
        return plugins

    # fallback for old config tools.json
    tools_data = load_tools()
    for tool in tools_data.get("tools", []):
        plugins.append(
            {
                "schema_version": "legacy",
                "id": tool.get("id", ""),
                "name": tool.get("name", ""),
                "version": "1.0.0",
                "group": tool.get("group", "未分组"),
                "desc": tool.get("desc", ""),
                "runtime": "python",
                "entry": tool.get("entry", ""),
                "params": tool.get("params", []),
                "status": tool.get("status", "ready"),
                "tags": tool.get("tags", []),
                "usage": tool.get("usage", ""),
                "timeout_sec": 1200,
                "install": {},
                "updatedAt": tool.get("updatedAt", ""),
                "pluginRoot": str(Path(__file__).resolve().parents[1]),
            }
        )
    return plugins


def get_plugin_by_id(plugin_id: str) -> dict | None:
    for plugin in list_plugins():
        if plugin.get("id") == plugin_id:
            return plugin
    return None


def load_plugin_from_dir(plugin_dir: Path) -> dict:
    manifest_path = plugin_dir / "manifest.json"
    if not manifest_path.exists():
        raise ValueError("缺少 manifest.json")
    return _read_manifest(manifest_path)
