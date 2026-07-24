@echo off
for /f "tokens=1 delims=." %%v in ('node -p "process.versions.node.split('.')[0]"') do set NODE_MAJOR=%%v
if %NODE_MAJOR% LSS 22 (
  echo Compose AI requires Node.js 22 or newer. Current runtime:
  node -v
  exit /b 1
)
cd /d "%~dp0"
npm run dev
