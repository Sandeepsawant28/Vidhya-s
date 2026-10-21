@echo off
REM Vidya’s Liquor Loft - Automated Nightly Database Backup Script
REM Can be scheduled in Windows Task Scheduler (Daily at 11:45 PM)

setlocal
cd /d "%~dp0"

echo ========================================================
echo   VIDYA'S LIQUOR LOFT - DATABASE BACKUP IN PROGRESS
echo   Date: %date% Time: %time%
echo ========================================================

REM Check if running inside installed directory or development folder
if exist "LiquorShop.exe" (
    REM Packaged mode
    "LiquorShop.exe" backup_db
) else if exist "venv\Scripts\python.exe" (
    REM Local development virtualenv mode
    "venv\Scripts\python.exe" manage.py backup_db
) else (
    REM Global python fallback
    python manage.py backup_db
)

echo.
echo Backup process complete.
echo ========================================================
