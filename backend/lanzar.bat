@echo off
cd /d "%~dp0\.."
set PYTHONPATH=src;backend
py -3.12 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
