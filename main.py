import subprocess
import sys
from pathlib import Path


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    cmd = [sys.executable, str(root / "src" / "run.py"), *sys.argv[1:]]
    proc = subprocess.Popen(cmd)
    try:
        raise SystemExit(proc.wait())
    except KeyboardInterrupt:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        raise SystemExit(130)
