@echo off
rem Daily live forecast (run after 17:15). See docs/LIVE_FORECAST.md
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo ===== %date% %time% >> outputs\live_log.txt
python src\forecast_tomorrow.py >> outputs\live_log.txt 2>&1
python src\build_demo.py >> outputs\live_log.txt 2>&1
