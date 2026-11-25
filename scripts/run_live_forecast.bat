@echo off
rem Planties - daily "tomorrow forecast" (run by Windows Task Scheduler at 17:20)
rem Copy of the team laptop script. Copy it to the repo root (or schedule this file as is).
rem Log: outputs\live_log.txt   Result: outputs\live_days.csv
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
set LOG=outputs\live_log.txt
echo ===== %date% %time% ===== >> "%LOG%"
rem build_demo.py rewrites demo\index.html every day; drop that copy so the pull is not blocked
git checkout -- demo/index.html >> "%LOG%" 2>&1
git pull --ff-only >> "%LOG%" 2>&1 || echo [warn] git pull failed, using current code >> "%LOG%"
python src\forecast_tomorrow.py >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [error] forecast_tomorrow.py failed >> "%LOG%"
  exit /b 1
)
python src\build_demo.py >> "%LOG%" 2>&1 || echo [warn] build_demo.py failed >> "%LOG%"
echo [ok] done %time% >> "%LOG%"
