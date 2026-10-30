@echo off
cd /d "%~dp0"
if exist .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
) else (
  echo No .venv found. Create one with: python -m venv .venv
  pause
  exit /b 1
)
echo Starting Talent Graph backend on http://127.0.0.1:8000
echo First start may load scraped JDs into Chroma — wait until "Uvicorn running".
echo Keep this window open while using the app.
echo.
uvicorn app.api:app --host 127.0.0.1 --port 8000
echo.
echo Backend stopped.
pause
