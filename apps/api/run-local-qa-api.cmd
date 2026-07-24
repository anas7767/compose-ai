@echo off
cd /d "%~dp0"
..\..\.venv\Scripts\python.exe -m uvicorn compose_ai_api.main:app --host 0.0.0.0 --port 8000
