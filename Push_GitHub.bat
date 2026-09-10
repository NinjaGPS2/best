@echo off
title EDC Billing System - Push to GitHub and Deploy
cd /d "%~dp0"

echo ================================================================
echo       EDC Electricity Billing and Management System
echo              PUSH TO GITHUB AND DEPLOY TOOL
echo ================================================================
echo Target Repository: https://github.com/NinjaGPS2/best
echo.

:: Add known Git paths to session PATH
set "PATH=%LOCALAPPDATA%\Programs\Git\cmd;%ProgramFiles%\Git\cmd;%ProgramFiles(x86)%\Git\cmd;%PATH%"

where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Git is not installed or not found in PATH!
    echo Please install Git from: https://git-scm.com/downloads
    echo.
    pause
    exit /b 1
)

:: Set default user name and email if missing
git config user.name >nul 2>&1
if %errorlevel% neq 0 git config user.name "NinjaGPS2"

git config user.email >nul 2>&1
if %errorlevel% neq 0 git config user.email "ninjagps2@github.com"

:: Ensure git is initialized
if not exist ".git" (
    echo [*] Initializing Git repository...
    git init -b main
)

:: Ensure remote origin
git remote get-url origin >nul 2>&1
if %errorlevel% neq 0 (
    git remote add origin https://github.com/NinjaGPS2/best.git
) else (
    git remote set-url origin https://github.com/NinjaGPS2/best.git
)

:: Show changed files
echo [*] Changed Files:
echo ----------------------------------------------------------------
git status -s
echo ----------------------------------------------------------------
echo.

:: Commit message input
set "COMMIT_MSG="
set /p COMMIT_MSG="[?] Enter commit message (or press Enter for default): "

if "%COMMIT_MSG%"=="" set "COMMIT_MSG=Update EDC System: %date% %time%"

echo.
echo [*] Staging all changes (git add .)...
git add .

echo [*] Committing changes...
git commit -m "%COMMIT_MSG%"

echo [*] Pushing to GitHub (origin main)...
git branch -M main
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ================================================================
    echo  [SUCCESS] Pushed to GitHub successfully!
    echo  URL: https://github.com/NinjaGPS2/best
    echo  Auto-deploy services (Render / Railway) will update now.
    echo ================================================================
) else (
    echo.
    echo ================================================================
    echo  [FAILED] Push could not be completed.
    echo  1. If GitHub prompts for login, please sign in or use Token.
    echo  2. To sync with remote changes, run: git pull origin main --rebase
    echo ================================================================
)

echo.
pause
