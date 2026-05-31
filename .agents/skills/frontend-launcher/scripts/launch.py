#!/usr/bin/env python3
import sys
import os
import argparse
import socket
import subprocess
import time
import webbrowser

# Define service configurations
SERVICES = {
    "calc": {
        "port": 5173,
        "dir": "rufus-calculator",
        "command": ["npm", "run", "dev"],
        "name": "React/Vite Calculator"
    },
    "dashboard": {
        "port": 3000,
        "dir": "rufus-dashboard",
        "command": ["npm", "run", "dev"],
        "name": "Next.js Admin Dashboard"
    },
    "backend": {
        "port": 8000,
        "dir": "backend",
        "command": ["python", "main.py"],
        "name": "FastAPI Backend API"
    }
}

def is_port_in_use(port: int) -> bool:
    """Check if the local port is already open and responding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        return s.connect_ex(('127.0.0.1', port)) == 0

def main():
    # Force UTF-8 encoding for standard output
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="Optimus Rufus Service Launcher and Browser Redirector")
    parser.add_argument(
        "--service", 
        required=True, 
        choices=["calc", "dashboard", "backend"], 
        help="The local workspace service to launch"
    )
    parser.add_argument(
        "--path", 
        default="", 
        type=str, 
        help="Optional deep link path (e.g. '/profile/uuid' or '/docs')"
    )
    args = parser.parse_args()

    config = SERVICES[args.service]
    port = config["port"]
    service_name = config["name"]
    target_path = args.path if args.path.startswith("/") or not args.path else f"/{args.path}"
    target_url = f"http://localhost:{port}{target_path}"

    print(f"[*] Auditing connection status for {service_name} on port {port}...")

    if is_port_in_use(port):
        print(f"[✓] {service_name} is already running on port {port}.")
    else:
        print(f"[!] Port {port} is closed. Starting {service_name} in background...")
        
        # Absolute path calculation to target directory
        workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
        target_dir = os.path.join(workspace_root, config["dir"])
        
        if not os.path.exists(target_dir):
            print(f"[ERROR] Service directory not found: {target_dir}")
            sys.exit(1)

        # Launch background process
        # On Windows, we can use CREATE_NEW_CONSOLE so the server logs stay visible to the user
        creation_flags = 0
        if sys.platform == 'win32':
            # 0x00000010 is CREATE_NEW_CONSOLE
            creation_flags = 0x00000010

        # Resolve python executable if virtualenv is present
        cmd = list(config["command"])
        if cmd[0] == "python":
            venv_py = os.path.join(workspace_root, "backend-venv", "Scripts", "python.exe" if sys.platform == 'win32' else "bin/python")
            if os.path.exists(venv_py):
                cmd[0] = venv_py

        try:
            subprocess.Popen(
                cmd,
                cwd=target_dir,
                creationflags=creation_flags,
                shell=True if sys.platform == 'win32' else False
            )
            print(f"[✓] Spawned {service_name} background subprocess. Waiting for port bind...")
            
            # Brief delay to let the port bind
            for _ in range(5):
                time.sleep(1.0)
                if is_port_in_use(port):
                    break
        except Exception as e:
            print(f"[ERROR] Failed to start {service_name}: {e}")
            sys.exit(1)

    print(f"[🚀] Launching default web browser to: {target_url}")
    try:
        webbrowser.open(target_url)
        print("[✓] Browser triggered successfully!")
    except Exception as e:
        print(f"[ERROR] Failed to trigger browser: {e}")

if __name__ == "__main__":
    main()
