@echo off
cd /d "%~dp0"
..\..\.venv\Scripts\python.exe -m compose_ai_api.domains.ai_architect.worker
