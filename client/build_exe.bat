@echo off
title Build cita_auto.exe (Client Installer)
color 0B
cd /d "%~dp0"

echo ======================================================================
echo          CITA AUTO - 1-Click Windows Executable (.exe) Builder
echo ======================================================================
echo.

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    where py >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Python is not installed or not in your system PATH!
        echo Please install Python 3.10+ from https://www.python.org/downloads/
        echo (Make sure to check "Add python.exe to PATH" during installation)
        echo.
        pause
        exit /b 1
    )
    set PY_CMD=py
) else (
    set PY_CMD=python
)

echo [1/3] Upgrading pip and installing dependencies...
%PY_CMD% -m pip install --upgrade pip
%PY_CMD% -m pip install -r requirements.txt pyinstaller
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install required dependencies.
    pause
    exit /b 1
)

echo.
echo [2/3] Compiling standalone cita_auto.exe with PyInstaller...
%PY_CMD% -m PyInstaller --clean cita_auto.spec
if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller compilation failed!
    pause
    exit /b 1
)

echo.
echo [3/3] Deploying cita_auto.exe into client folder...
if exist dist\cita_auto.exe (
    copy /Y dist\cita_auto.exe .\cita_auto.exe >nul
    echo.
    echo ======================================================================
    echo [SUCCESS] cita_auto.exe was created and placed in this folder!
    echo You can now double-click cita_auto.exe or start.bat to use the bot.
    echo ======================================================================
) else (
    echo [WARNING] dist\cita_auto.exe was not found. Please check dist folder.
)

echo.
pause
