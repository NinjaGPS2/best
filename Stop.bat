@echo off
chcp 65001 >nul
title Stop EDC Electricity Billing System
cd /d "%~dp0"

echo កំពុងបិទប្រព័ន្ធ EDC Electricity Billing System...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo បានបិទប្រព័ន្ធជោគជ័យ!
timeout /t 2 /nobreak >nul
exit
