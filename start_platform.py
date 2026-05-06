import subprocess
import sys
import time
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

HOST = "192.168.54.120"
BACKEND_URL = f"http://{HOST}:8787/api/health"
FRONTEND_URL = f"http://{HOST}:5500"


def main():
    backend_cmd = [sys.executable, "main.py"]
    frontend_cmd = [sys.executable, "-m", "http.server", "5500", "--bind", "0.0.0.0"]

    backend_proc = subprocess.Popen(backend_cmd, cwd=str(BACKEND_DIR))
    frontend_proc = subprocess.Popen(frontend_cmd, cwd=str(FRONTEND_DIR))

    print("平台启动中...")
    print(f"- 后端健康检查: {BACKEND_URL}")
    print(f"- 前端地址: {FRONTEND_URL}")

    time.sleep(1.2)
    webbrowser.open(FRONTEND_URL)

    try:
        while True:
            if backend_proc.poll() is not None:
                print("后端进程已退出，平台停止。")
                break
            if frontend_proc.poll() is not None:
                print("前端进程已退出，平台停止。")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n收到退出指令，正在关闭平台...")
    finally:
        for proc in [backend_proc, frontend_proc]:
            if proc.poll() is None:
                proc.terminate()
        print("平台已关闭。")


if __name__ == "__main__":
    main()
