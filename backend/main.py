from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import mimetypes
from pathlib import Path
from urllib.parse import quote
from urllib.parse import parse_qs, urlparse

from plugin_loader import list_plugins, get_plugin_by_id
from plugin_installer import register_local_plugin, register_zip_plugin, register_git_plugin
from plugin_runner import PluginRunner
from storage import ensure_data_dirs, load_environments, read_execution_log


runner = PluginRunner(max_workers=3)


class Handler(BaseHTTPRequestHandler):
    def _set_common_headers(self, status=200, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._set_common_headers(status=status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path: Path, force_download: bool = False):
        if not file_path.exists() or not file_path.is_file():
            self._send_json({"ok": False, "message": "File Not Found"}, status=404)
            return
        content = file_path.read_bytes()
        content_type, _ = mimetypes.guess_type(str(file_path))
        if not content_type:
            content_type = "application/octet-stream"
        disposition = "attachment" if force_download else "inline"
        filename_ascii = "download.bin"
        filename_utf8 = quote(file_path.name)
        self._set_common_headers(status=200, content_type=content_type)
        self.send_header(
            "Content-Disposition",
            f"{disposition}; filename=\"{filename_ascii}\"; filename*=UTF-8''{filename_utf8}",
        )
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_json_body(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}
        raw = self.rfile.read(content_length)
        return json.loads(raw.decode("utf-8"))

    def _parse_tool_id(self):
        parts = self.path.strip("/").split("/")
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "tools":
            return parts[2]
        return None

    def _parse_task_id(self):
        parts = self.path.strip("/").split("/")
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "tasks":
            return parts[2]
        return None

    def do_OPTIONS(self):
        self._set_common_headers(status=204)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/api/health":
            self._send_json({"ok": True, "service": "7g-tool-platform-backend"})
            return
        if path == "/api/environments":
            self._send_json({"ok": True, "data": load_environments()})
            return
        if path == "/api/tools":
            self._send_json({"ok": True, "data": {"tools": list_plugins()}})
            return
        if path.startswith("/api/tools/"):
            tool_id = self._parse_tool_id()
            tool = get_plugin_by_id(tool_id) if tool_id else None
            if not tool:
                self._send_json({"ok": False, "message": "Tool Not Found"}, status=404)
                return
            self._send_json({"ok": True, "data": tool})
            return
        if path.startswith("/api/tasks/") and path.endswith("/log"):
            task_id = self._parse_task_id()
            task = runner.get_task(task_id) if task_id else None
            if not task:
                self._send_json({"ok": False, "message": "Task Not Found"}, status=404)
                return
            log_file = task.get("logFile", "")
            if not log_file:
                self._send_json({"ok": False, "message": "Log Not Ready"}, status=404)
                return
            content = read_execution_log(log_file)
            if content is None:
                self._send_json({"ok": False, "message": "Log Not Found"}, status=404)
                return
            self._send_json({"ok": True, "data": {"fileName": log_file, "content": content}})
            return
        if path.startswith("/api/tasks/") and "/artifacts/" in path:
            parts = path.strip("/").split("/")
            if len(parts) < 5:
                self._send_json({"ok": False, "message": "Invalid artifact path"}, status=400)
                return
            task_id = parts[2]
            index_text = parts[4]
            task = runner.get_task(task_id) if task_id else None
            if not task:
                self._send_json({"ok": False, "message": "Task Not Found"}, status=404)
                return
            artifacts = task.get("artifacts", [])
            if not isinstance(artifacts, list):
                artifacts = []
            try:
                index = int(index_text)
            except ValueError:
                self._send_json({"ok": False, "message": "Invalid artifact index"}, status=400)
                return
            if index < 0 or index >= len(artifacts):
                self._send_json({"ok": False, "message": "Artifact Not Found"}, status=404)
                return
            item = artifacts[index] or {}
            file_path = Path(str(item.get("path", ""))).resolve()
            mode = (query.get("mode", ["inline"])[0] or "inline").lower()
            self._send_file(file_path, force_download=(mode == "download"))
            return
        if path.startswith("/api/tasks/") and path.endswith("/artifacts"):
            parts = path.strip("/").split("/")
            if len(parts) < 4:
                self._send_json({"ok": False, "message": "Invalid artifacts path"}, status=400)
                return
            task_id = parts[2]
            task = runner.get_task(task_id) if task_id else None
            if not task:
                self._send_json({"ok": False, "message": "Task Not Found"}, status=404)
                return
            artifacts = task.get("artifacts", [])
            if not isinstance(artifacts, list):
                artifacts = []
            clean_items = []
            for idx, item in enumerate(artifacts):
                clean_items.append(
                    {
                        "index": idx,
                        "name": item.get("name", f"artifact-{idx}"),
                        "size": int(item.get("size", 0) or 0),
                        "ext": item.get("ext", ""),
                        "viewUrl": f"/api/tasks/{task_id}/artifacts/{idx}?mode=inline",
                        "downloadUrl": f"/api/tasks/{task_id}/artifacts/{idx}?mode=download",
                    }
                )
            self._send_json({"ok": True, "data": {"items": clean_items}})
            return
        if path.startswith("/api/tasks/"):
            task_id = self._parse_task_id()
            task = runner.get_task(task_id) if task_id else None
            if not task:
                self._send_json({"ok": False, "message": "Task Not Found"}, status=404)
                return
            self._send_json({"ok": True, "data": task})
            return
        if path.startswith("/api/logs/"):
            file_name = path.split("/api/logs/", 1)[1]
            content = read_execution_log(file_name)
            if content is None:
                self._send_json({"ok": False, "message": "Log Not Found"}, status=404)
                return
            self._send_json({"ok": True, "data": {"fileName": file_name, "content": content}})
            return
        self._send_json({"ok": False, "message": "Not Found"}, status=404)

    def do_POST(self):
        if self.path == "/api/plugins/register-local":
            try:
                payload = self._read_json_body()
                data = register_local_plugin(
                    payload.get("path", ""),
                    bool(payload.get("overwrite", False)),
                    bool(payload.get("run_install", True)),
                )
                self._send_json({"ok": True, "data": data})
            except Exception as exc:
                self._send_json({"ok": False, "message": str(exc)}, status=400)
            return

        if self.path == "/api/plugins/upload":
            try:
                payload = self._read_json_body()
                data = register_zip_plugin(
                    payload.get("zip_path", ""),
                    bool(payload.get("overwrite", False)),
                    bool(payload.get("run_install", True)),
                )
                self._send_json({"ok": True, "data": data})
            except Exception as exc:
                self._send_json({"ok": False, "message": str(exc)}, status=400)
            return

        if self.path == "/api/plugins/import-git":
            try:
                payload = self._read_json_body()
                data = register_git_plugin(
                    payload.get("repo_url", ""),
                    payload.get("ref", ""),
                    bool(payload.get("overwrite", False)),
                    bool(payload.get("run_install", True)),
                )
                self._send_json({"ok": True, "data": data})
            except Exception as exc:
                self._send_json({"ok": False, "message": str(exc)}, status=400)
            return

        if self.path.startswith("/api/tools/") and self.path.endswith("/run"):
            parts = self.path.strip("/").split("/")
            if len(parts) != 4:
                self._send_json({"ok": False, "message": "Invalid path"}, status=400)
                return
            tool_id = parts[2]
            plugin = get_plugin_by_id(tool_id)
            if not plugin:
                self._send_json({"ok": False, "message": "Tool Not Found"}, status=404)
                return
            try:
                payload = self._read_json_body()
            except json.JSONDecodeError:
                self._send_json({"ok": False, "message": "Invalid JSON body"}, status=400)
                return
            try:
                data = runner.submit(plugin, payload.get("params", {}))
            except ValueError as exc:
                self._send_json({"ok": False, "message": str(exc)}, status=400)
                return
            self._send_json({"ok": True, "data": data})
            return

        self._send_json({"ok": False, "message": "Not Found"}, status=404)


def run():
    ensure_data_dirs()
    server = HTTPServer(("0.0.0.0", 8787), Handler)
    print("Backend started at http://192.168.54.120:8787")
    server.serve_forever()


if __name__ == "__main__":
    run()
