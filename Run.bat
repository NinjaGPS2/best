@echo off
chcp 65001 >nul
title EDC Electricity Billing System
cd /d "%~dp0"

:: Check if port 5000 is already running
netstat -ano | findstr :5000 | findstr LISTENING >nul
if %errorlevel% neq 0 (
    start "" pythonw run.py
    timeout /t 2 /nobreak >nul
)

:: Open default browser to EDC system URL
start http://127.0.0.1:5000

:: Close CMD window immediately
exit
