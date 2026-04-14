"""
Air Cooler Main - Standalone Windows launcher.
"""
import multiprocessing
import os
import signal
import socket
import sys
import threading
import time
import webbrowser


APP_SCRIPT = "air_cooler_main_app.py"


if __name__ == "__main__":
    multiprocessing.freeze_support()


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_server(port, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False


def start_streamlit(script_path, port):
    original_signal = signal.signal

    def noop_signal(signum, handler):
        try:
            original_signal(signum, handler)
        except (ValueError, OSError):
            pass

    signal.signal = noop_signal
    try:
        import streamlit.web.cli as stcli

        sys.argv = [
            "streamlit",
            "run",
            script_path,
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--global.developmentMode",
            "false",
            "--browser.gatherUsageStats",
            "false",
            "--browser.serverAddress",
            "localhost",
        ]
        stcli.main()
    except SystemExit:
        pass
    finally:
        signal.signal = original_signal


def show_error(title, message):
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(title, message)


def main():
    base_dir = sys._MEIPASS if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(base_dir, APP_SCRIPT)

    if not os.path.exists(script_path):
        show_error("Dosya Hatası", f"Uygulama dosyası bulunamadı:\n{script_path}")
        return

    port = get_free_port()
    worker = threading.Thread(target=start_streamlit, args=(script_path, port), daemon=True)
    worker.start()

    url = f"http://localhost:{port}"
    if wait_for_server(port, timeout=30):
        webbrowser.open(url)
    else:
        show_error("Başlatma Hatası", "Uygulama sunucusu 30 saniye içinde başlatılamadı.")
        return

    try:
        while worker.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
