"""Manually run a local reader session without importing GUI dependencies."""

import signal
import time
from pathlib import Path
from threading import Lock

from .controller import ReaderController, ReaderStatus


def run(
    root: Path, config_path: Path, program_path: Path, port: int = 8765,
    *, lan: bool = False, configure_firewall: bool = False,
) -> int:
    """Serve a checked LAN or loopback session until interrupted, then clean up."""
    if configure_firewall and not lan:
        raise ValueError("配置防火墙需要启用 --lan")
    stopping = False
    output_lock = Lock()
    controller = None
    previous_handlers = {}
    result = 1

    def print_status(status: ReaderStatus) -> None:
        with output_lock:
            text = f"[{status.state}] {status.message}"
            if status.url:
                text += f"\n访问地址：{status.url}"
            print(text, flush=True)

    def request_stop(signum, frame) -> None:
        # Never take controller locks in a signal handler: a signal may arrive
        # while the main thread owns one during startup or publication.
        nonlocal stopping
        stopping = True

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.signal(signum, request_stop)
        if configure_firewall:
            from .wsl import configure_lan, discover_lan

            try:
                scope = discover_lan()
                print(
                    f"正在配置 Windows 与 WSL 防火墙：专用网络 TCP {port}，"
                    f"本机 {scope.address}，来源 {scope.subnet}。", flush=True,
                )
                configure_lan(config_path.parent / "configure-wsl-firewall.ps1", port)
                print("局域网防火墙配置已通过检查。", flush=True)
            except Exception as error:  # noqa: BLE001 - failed setup retains the checked local preview
                lan = False
                print_status(ReaderStatus("local-only", f"防火墙配置未完成：{error}"))
            if stopping:
                return 0
        controller = ReaderController(
            root, config_path, program_path, port=port,
            on_status=print_status, local_only=not lan,
            **({"wsl_lan": True} if lan else {}),
        )
        print("正在启动阅读器；按 Ctrl+C 停止。", flush=True)
        if controller.start():
            while not stopping:
                time.sleep(0.2)
            result = 0
    except KeyboardInterrupt:
        result = 0
    except Exception as error:  # noqa: BLE001 - terminal boundary reports startup errors
        print_status(ReaderStatus("error", f"启动失败：{type(error).__name__}: {error}"))
    finally:
        try:
            if controller is not None:
                controller.stop()
        except Exception as error:  # noqa: BLE001 - cleanup failures must affect the exit code
            print_status(ReaderStatus("error", f"清理失败：{type(error).__name__}: {error}"))
            result = 1
        finally:
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)
    return result
