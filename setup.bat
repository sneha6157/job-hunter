@echo off
echo ============================================================
echo   JOB HUNTER V2 — SETUP
echo ============================================================

echo.
echo [1/3] Creating virtual environment...
python -m venv venv
if errorlevel 1 ( echo [!] Python not found. Install Python 3.11+ and retry. & pause & exit /b 1 )

echo [2/3] Installing dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
if errorlevel 1 ( echo [!] pip install failed. & pause & exit /b 1 )
echo [2b] Installing Playwright browser (for Naukri)...
playwright install chromium --with-deps 2>nul || echo     [skipped — run manually: playwright install chromium]

echo [3/3] Setting up .env...
if not exist .env (
    copy .env.example .env
    echo.
    echo [!] .env created from template.
    echo     Open .env and fill in your MONGO_URI and NAUKRI credentials.
) else (
    echo     .env already exists — skipped.
)

echo.
echo ============================================================
echo   Setup complete! Next:
echo   1. Edit .env with your MongoDB URI
echo   2. Run: run.bat
echo ============================================================
pause
