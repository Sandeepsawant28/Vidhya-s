@echo off
REM ==============================================================================
REM   VIDYA'S LIQUOR LOFT - ONE-CLICK COMPLETE BUILD & PACKAGING SCRIPT
REM ==============================================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo [1/5] Checking Python Virtual Environment...
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo Virtual environment not found in .\venv. Using active python...
)

echo.
echo [2/5] Installing/Verifying Pinned Dependencies from requirements.txt...
python -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies. Check requirements.txt.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [3/5] Applying Database Migrations...
python manage.py makemigrations core
python manage.py migrate

echo.
echo [4/5] Building Standalone One-Folder Distribution with PyInstaller...
pyinstaller liquor_shop.spec --clean --noconfirm
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller build failed. Check the error log above.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [5/5] Compiling Windows Setup Installer with Inno Setup (ISCC)...
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    where iscc >nul 2>nul
    if %ERRORLEVEL% EQU 0 set ISCC=iscc
)

if exist %ISCC% (
    echo Found Inno Setup Compiler: %ISCC%
    %ISCC% installer.iss
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo ==============================================================================
        echo   BUILD SUCCESSFUL!
        echo   Installer Created: output\LiquorShop_Setup_v1.0.exe
        echo   Ready to test or install on any Windows 10/11 shop computer!
        echo ==============================================================================
    ) else (
        echo [ERROR] Inno Setup compilation failed.
    )
) else (
    echo.
    echo [NOTICE] Inno Setup compiler (ISCC.exe) was not found in Program Files.
    echo The PyInstaller folder was built successfully in:
    echo    dist\LiquorShop\LiquorShop.exe
    echo.
    echo To build the final Setup.exe installer:
    echo 1. Download and install free Inno Setup 6 from: https://jrsoftware.org/isdl.php
    echo 2. Right-click 'installer.iss' and select 'Compile'.
)

echo.
pause
