@echo off
cd /d "%~dp0"
echo Starting HopStop Live Analyst Console on http://127.0.0.1:8080 ...
start "" "http://127.0.0.1:8080"
python -m hopstop.server
pause
