@echo off
cd /d "%~dp0"
python converter.py riprendi
timeout /t 3 >nul
