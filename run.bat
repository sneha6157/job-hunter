@echo off
if not exist venv (
    echo [!] Run setup.bat first.
    pause & exit /b 1
)
call venv\Scripts\activate.bat
echo Starting Job Hunter V2 at http://localhost:8000 ...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
