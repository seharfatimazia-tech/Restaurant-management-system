"""
Gusto POS - Restaurant Management Desktop Software
Desktop Software Entrypoint & Window Launcher
"""

import os
import sys
import time
import socket
import threading
import subprocess
from app import create_app
from models import db

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def run_flask(port):
    app = create_app()
    # Ensure database tables exist
    with app.app_context():
        db.create_all()
    # Run production-grade quiet local server
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)

def launch_native_window(url, title="Gusto POS - Restaurant Management Software"):
    """
    Launches a true standalone native desktop software window.
    Priority 1: pywebview (Native Windows WebView2 window)
    Priority 2: Windows Edge / Chrome native chromeless app-mode window
    """
    # Attempt 1: pywebview
    try:
        import webview
        print("[Desktop Software] Launching via PyWebView native desktop window...")
        webview.create_window(
            title=title,
            url=url,
            width=1320,
            height=860,
            min_size=(1024, 700),
            resizable=True,
            confirm_close=True
        )
        webview.start()
        return True
    except ImportError:
        pass
    except Exception as e:
        print(f"[Desktop Software] pywebview init notice: {e}")

    # Attempt 2: Native Windows Desktop App Window (Edge / Chrome standalone app frame)
    # This runs as a dedicated desktop software window with no URL bar, no tabs, no address bar
    edge_paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]
    chrome_paths = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]

    for exe in edge_paths + chrome_paths:
        if os.path.exists(exe):
            print(f"[Desktop Software] Launching native desktop window using {os.path.basename(exe)} standalone app mode...")
            cmd = [exe, f"--app={url}", f"--window-size=1320,860", "--window-name=GustoPOS"]
            proc = subprocess.Popen(cmd)
            proc.wait()
            return True

    # Fallback: Default system browser
    import webbrowser
    print("[Desktop Software] Opening desktop interface...")
    webbrowser.open(url)
    return True

def main():
    print("==================================================================")
    print(" Gusto Restaurant Management Desktop Software v2.0")
    print(" DBMS Architecture: SQLite + SQLAlchemy ORM (3NF/BCNF)")
    print("==================================================================")

    # Check if database file exists; if not, suggest or run seed
    base_dir = os.path.abspath(os.path.dirname(__file__))
    db_file = os.path.join(base_dir, 'restaurant.db')

    if not os.path.exists(db_file):
        print("[Desktop Software] First run detected: Initializing and seeding database...")
        try:
            from seed import run_seed
            run_seed()
            print("[Desktop Software] Database seeded successfully!")
        except Exception as e:
            print(f"[Desktop Software] Notice during seed: {e}")

    port = 5000
    if is_port_in_use(port):
        port = get_free_port()

    server_url = f"http://127.0.0.1:{port}"
    print(f"[Desktop Software] Starting core backend services on port {port}...")

    # Start Flask server in background daemon thread
    server_thread = threading.Thread(target=run_flask, args=(port,), daemon=True)
    server_thread.start()

    # Wait briefly for server socket to accept connections
    for _ in range(50):
        if is_port_in_use(port):
            break
        time.sleep(0.1)

    print("[Desktop Software] Starting Desktop Application GUI...")
    launch_native_window(server_url)

if __name__ == '__main__':
    main()
