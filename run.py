import os
import subprocess
import uvicorn


def free_port_8000():
    """Frees port 8000 if a stale server instance is still listening."""
    import signal
    import time
    try:
        output = subprocess.check_output(
            ["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL
        )
        my_pid = os.getpid()
        killed = False
        for line in output.splitlines():
            if ":8000 " in line and ("LISTENING" in line or "TCP" in line):
                parts = line.split()
                if parts:
                    try:
                        pid = int(parts[-1])
                        if pid != my_pid and pid > 0:
                            subprocess.run(
                                ["taskkill", "/F", "/PID", str(pid)],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                            )
                            try:
                                os.kill(pid, signal.SIGTERM)
                            except Exception:
                                pass
                            killed = True
                    except ValueError:
                        pass
        if killed:
            time.sleep(1.5)
    except Exception:
        pass


if __name__ == "__main__":
    free_port_8000()
    print("=" * 60)
    print("  CIVICFIX AI — SMART PUBLIC GRIEVANCE GUIDANCE SYSTEM")
    print("=" * 60)
    print("  • Starting local web app: http://127.0.0.1:8000")
    print("  • 1. AI Guidance:         http://127.0.0.1:8000/#guidance")
    print("  • 2. Report Problem:      http://127.0.0.1:8000/#report")
    print("  • 3. My Complaints:       http://127.0.0.1:8000/#my-complaints")
    print("  • 4. Complaint Letter:    http://127.0.0.1:8000/#letter")
    print("  • API Documentation:      http://127.0.0.1:8000/docs")
    print("=" * 60)

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False
    )
