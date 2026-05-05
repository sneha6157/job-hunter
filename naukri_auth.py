#!/usr/bin/env python3
"""
Naukri one-time login — run this once to save your session.

    python naukri_auth.py

A real browser window opens. It tries to log in automatically.
If a CAPTCHA appears, complete it manually — then come back to this terminal.
Session is saved to naukri_session.json and reused for ~30 days.
"""
import json, os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SESSION_FILE = Path(__file__).parent / "naukri_session.json"


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\n[!] playwright not installed.")
        print("    Run: pip install playwright && playwright install chromium\n")
        sys.exit(1)

    email    = os.getenv("NAUKRI_EMAIL", "").strip()
    password = os.getenv("NAUKRI_PASSWORD", "").strip()

    if not email or not password:
        print("\n[!] Fill NAUKRI_EMAIL and NAUKRI_PASSWORD in your .env file first.\n")
        sys.exit(1)

    print(f"\n[*] Opening browser for {email} ...")
    print("[*] Complete any CAPTCHA that appears, then wait.\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=400)
        ctx     = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()

        # Warmup — collect tracking cookies
        print("[1/4] Warming up naukri.com ...")
        page.goto("https://www.naukri.com/", timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Navigate to login
        print("[2/4] Opening login page ...")
        page.goto("https://www.naukri.com/nlogin/login", timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Try auto-fill
        print("[3/4] Filling credentials ...")
        try:
            page.fill('input[placeholder*="Email"]', email, timeout=8000)
            page.wait_for_timeout(500)
            page.fill('input[type="password"]', password, timeout=8000)
            page.wait_for_timeout(500)
            page.click('button[type="submit"]', timeout=8000)
            print("    Credentials submitted. Waiting for login ...")
        except Exception as e:
            print(f"    Auto-fill failed ({e}).")
            print("    Please log in manually in the browser window.")

        # Wait for redirect away from login page (up to 90s for captcha)
        print("[4/4] Waiting for successful login (up to 90s) ...")
        try:
            page.wait_for_function(
                "() => !window.location.href.includes('nlogin')",
                timeout=90000,
            )
            print("    Logged in!")
        except Exception:
            input("\n[!] Still on login page. Complete it manually in the browser, then press Enter here: ")

        # Extra wait to let all cookies settle
        page.wait_for_timeout(2000)

        # Save all cookies
        cookies = ctx.cookies()
        SESSION_FILE.write_text(json.dumps(cookies, indent=2))

        print(f"\n[✓] Session saved → {SESSION_FILE.name}")
        print("[✓] Naukri is now active in job hunts for ~30 days.")
        print("[✓] Re-run this script when hunts start showing 0 Naukri jobs.\n")
        browser.close()


if __name__ == "__main__":
    main()
