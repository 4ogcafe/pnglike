import os
import subprocess
import sys
import time
import e2e_test


def free_port_7860():
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(
                ["netstat", "-ano", "-p", "TCP"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            pids = set()
            for line in out.splitlines():
                if ":7860" in line and "LISTENING" in line:
                    parts = line.split()
                    if parts:
                        pid = parts[-1]
                        if pid.isdigit() and int(pid) > 0:
                            pids.add(pid)
            for pid in pids:
                subprocess.run(
                    ["taskkill", "/F", "/PID", pid],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            if pids:
                time.sleep(1.0)
        else:
            out = subprocess.check_output(["lsof", "-ti", ":7860"], text=True, stderr=subprocess.DEVNULL)
            pids = [p.strip() for p in out.splitlines() if p.strip()]
            for pid in pids:
                subprocess.run(["kill", "-9", pid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if pids:
                time.sleep(1.0)
    except Exception:
        pass


if __name__ == "__main__":
    port = os.getenv("TEST_PORT", "7861")
    os.environ["TEST_SERVER_URL"] = f"http://127.0.0.1:{port}"
    print(f"Launching FastAPI Uvicorn server on http://127.0.0.1:{port}...")
    server_proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", port])
    try:
        e2e_test.run_e2e_tests()
    finally:
        print("Shutting down test server...")
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except Exception:
            server_proc.kill()
