"""
Naukri source — spawns a subprocess to run Playwright scraping.
sync_playwright() can't run inside FastAPI's asyncio event loop on Windows,
so we isolate it in naukri_worker.py which gets its own clean event loop.

Run naukri_auth.py once to save the session (~30 days valid).
"""
import sys, json, subprocess
from pathlib import Path

SESSION_FILE = Path(__file__).parent.parent.parent / "naukri_session.json"
WORKER       = Path(__file__).parent / "naukri_worker.py"


def fetch_all(queries: list, days: int = 30) -> list[dict]:
    if not SESSION_FILE.exists():
        print("  [Naukri] No session file — run: python naukri_auth.py")
        return []

    try:
        payload = json.dumps({"queries": queries, "days": days})
        result  = subprocess.run(
            [sys.executable, str(WORKER)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=70,
        )
        # stderr has progress messages
        for line in result.stderr.strip().splitlines():
            if line:
                print(f"  {line}")

        if result.returncode != 0:
            print(f"  [Naukri] worker exited {result.returncode}")
            return []

        stdout = result.stdout.strip()
        if not stdout:
            return []

        jobs = json.loads(stdout)
        return jobs

    except subprocess.TimeoutExpired:
        print("  [Naukri] worker timed out (180s)")
        return []
    except Exception as e:
        print(f"  [Naukri] fetch_all error: {e}")
        return []


# Shim so per-query calls in any legacy code return empty gracefully
def fetch(query: str, location: str, days: int = 30) -> list[dict]:  # noqa: ARG001
    return []
