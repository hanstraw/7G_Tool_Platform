from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import zipfile
import subprocess
import sys
import shlex

from plugin_loader import load_plugin_from_dir
from storage import PLUGIN_DIR


def _run_install_steps(plugin: dict) -> dict:
    plugin_root = Path(plugin["pluginRoot"]).resolve()
    steps: list[list[str]] = []
    install = plugin.get("install") or {}
    if isinstance(install, dict):
        commands = install.get("commands", [])
        if isinstance(commands, list):
            for cmd in commands:
                if isinstance(cmd, str) and cmd.strip():
                    parts = shlex.split(cmd.strip(), posix=False)
                    if parts:
                        # Ensure install runs in same interpreter as backend/runner.
                        if parts[0].lower() in {"python", "python3", "py"}:
                            parts[0] = sys.executable
                        steps.append(parts)

    if not steps:
        requirements = plugin_root / "requirements.txt"
        package_json = plugin_root / "package.json"
        if requirements.exists():
            steps.append([sys.executable, "-m", "pip", "install", "-r", str(requirements)])
        if package_json.exists():
            steps.append(["npm", "install"])

    outputs = []
    for command in steps:
        result = subprocess.run(
            command,
            cwd=str(plugin_root),
            capture_output=True,
            text=True,
            check=False,
        )
        outputs.append(
            {
                "command": " ".join(command),
                "returnCode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        if result.returncode != 0:
            return {"ok": False, "steps": outputs}
    return {"ok": True, "steps": outputs}


def _copy_plugin(source_dir: Path, overwrite: bool = False, run_install: bool = True) -> dict:
    plugin = load_plugin_from_dir(source_dir)
    target_dir = PLUGIN_DIR / plugin["id"]
    if target_dir.exists():
        if not overwrite:
            raise ValueError(f"插件已存在: {plugin['id']}")
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)
    saved = load_plugin_from_dir(target_dir)
    install_result = {"ok": True, "steps": []}
    if run_install:
        install_result = _run_install_steps(saved)
        if not install_result["ok"]:
            raise ValueError(f"依赖安装失败: {install_result['steps'][-1]['command']}")
    return {"plugin": saved, "install": install_result}


def register_local_plugin(source_path: str, overwrite: bool = False, run_install: bool = True) -> dict:
    source_dir = Path(source_path).expanduser().resolve()
    if not source_dir.exists() or not source_dir.is_dir():
        raise ValueError("本地目录不存在")
    return _copy_plugin(source_dir, overwrite=overwrite, run_install=run_install)


def register_zip_plugin(zip_path: str, overwrite: bool = False, run_install: bool = True) -> dict:
    archive_path = Path(zip_path).expanduser().resolve()
    if not archive_path.exists() or archive_path.suffix.lower() != ".zip":
        raise ValueError("ZIP 文件不存在或格式错误")
    with tempfile.TemporaryDirectory(prefix="plugin_zip_") as tmp:
        tmp_dir = Path(tmp)
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(tmp_dir)
        candidate = tmp_dir
        if not (candidate / "manifest.json").exists():
            dirs = [p for p in tmp_dir.iterdir() if p.is_dir() and (p / "manifest.json").exists()]
            if not dirs:
                raise ValueError("ZIP 内未找到 manifest.json")
            candidate = dirs[0]
        return _copy_plugin(candidate, overwrite=overwrite, run_install=run_install)


def register_git_plugin(repo_url: str, ref: str = "", overwrite: bool = False, run_install: bool = True) -> dict:
    with tempfile.TemporaryDirectory(prefix="plugin_git_") as tmp:
        tmp_dir = Path(tmp) / "repo"
        clone_cmd = ["git", "clone", repo_url, str(tmp_dir)]
        result = subprocess.run(clone_cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise ValueError(f"git clone 失败: {result.stderr.strip()}")
        if ref.strip():
            checkout = subprocess.run(
                ["git", "checkout", ref.strip()],
                cwd=str(tmp_dir),
                capture_output=True,
                text=True,
                check=False,
            )
            if checkout.returncode != 0:
                raise ValueError(f"git checkout 失败: {checkout.stderr.strip()}")
        return _copy_plugin(tmp_dir, overwrite=overwrite, run_install=run_install)
