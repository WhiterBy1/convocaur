@echo off
cd /d "%~dp0\.."
echo ConvocaUR Matching UI
echo Abre http://127.0.0.1:8765
python web\api.py
