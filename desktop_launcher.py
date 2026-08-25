from __future__ import annotations

import ctypes
import http.client
import logging
import os
import socket
# Only this executable's fixed local command is launched.
import subprocess  # nosec B404
import sys
import time
from pathlib import Path


APP_TITLE = "清流账单助手"
SERVER_ARG = "--qingliu-streamlit-server"
SMOKE_ARG = "--desktop-smoke-test"
MUTEX_NAME = "Local\\QingliuBillAnalyzer_7A3E80D2"


def runtime_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    return Path(frozen_root) if frozen_root else Path(__file__).resolve().parent


def configure_logging() -> Path:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    log_dir = local_app_data / "QingliuBillAnalyzer"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "desktop.log"
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    return log_path


def message_box(message: str, *, error: bool = True) -> None:
    if sys.platform == "win32":
        style = 0x10 if error else 0x40
        ctypes.windll.user32.MessageBoxW(None, message, APP_TITLE, style)


def acquire_single_instance(*, silent: bool = False) -> bool:
    if sys.platform != "win32":
        return True
    ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    already_exists = ctypes.windll.kernel32.GetLastError() == 183
    if already_exists:
        if not silent:
            message_box("清流账单助手已经在运行。请切换到现有窗口。", error=False)
        return False
    return True


def choose_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_streamlit_server(port: int) -> int:
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    root = runtime_root()
    app_path = root / "app.py"
    if not app_path.exists():
        logging.error("Bundled app.py is missing at %s", app_path)
        return 2
    os.chdir(root)
    from streamlit import config as streamlit_config
    from streamlit.web import bootstrap

    options = {
        "server.headless": True,
        "server.address": "127.0.0.1",
        "server.port": port,
        "server.fileWatcherType": "none",
        "browser.gatherUsageStats": False,
        "client.toolbarMode": "minimal",
        "global.developmentMode": False,
    }
    streamlit_config._main_script_path = str(app_path)
    bootstrap.load_config_options(flag_options=options)
    bootstrap.run(str(app_path), False, [], options)
    return 0


def server_command(port: int) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, SERVER_ARG, str(port)]
    return [sys.executable, str(Path(__file__).resolve()), SERVER_ARG, str(port)]


def start_server(port: int, log_path: Path) -> tuple[subprocess.Popen, object]:
    log_handle = open(log_path, "a", encoding="utf-8")
    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    # Arguments come only from trusted local constants.
    process = subprocess.Popen(  # nosec B603
        server_command(port),
        cwd=runtime_root(),
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=creation_flags,
    )
    return process, log_handle


def wait_for_server(process: subprocess.Popen, port: int, timeout: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            try:
                connection.request("GET", "/_stcore/health")
                response = connection.getresponse()
                if response.status == 200 and response.read().strip() == b"ok":
                    return True
            finally:
                connection.close()
        except (OSError, TimeoutError, http.client.HTTPException):
            pass
        time.sleep(0.25)
    return False


def stop_server(process: subprocess.Popen | None, log_handle: object | None) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
    if log_handle is not None:
        log_handle.close()


def run_desktop(smoke_test: bool = False) -> int:
    if not acquire_single_instance(silent=smoke_test):
        return 0
    log_path = configure_logging()
    port = choose_port()
    process: subprocess.Popen | None = None
    log_handle = None
    try:
        process, log_handle = start_server(port, log_path)
        if not wait_for_server(process, port):
            logging.error("Local server failed to start; exit code=%s", process.poll())
            message_box(
                "本地服务启动失败。请查看下面的日志文件。公开反馈前，"
                "请确认日志中没有个人信息：\n\n" + str(log_path)
            )
            return 1
        logging.info("Desktop server is healthy on a local dynamic port")
        if smoke_test:
            return 0

        import webview

        webview.create_window(
            APP_TITLE,
            f"http://127.0.0.1:{port}",
            width=1360,
            height=860,
            min_size=(980, 640),
            resizable=True,
            text_select=True,
            background_color="#F8FAFC",
        )
        webview.start(debug=False, private_mode=True)
        return 0
    except Exception:
        logging.exception("Desktop application failed")
        message_box(
            "桌面应用启动失败。请查看下面的日志文件。公开反馈前，"
            "请确认日志中没有个人信息：\n\n" + str(log_path)
        )
        return 1
    finally:
        stop_server(process, log_handle)


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == SERVER_ARG:
        return run_streamlit_server(int(sys.argv[2]))
    return run_desktop(smoke_test=SMOKE_ARG in sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
