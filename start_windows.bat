@echo off
title Cita Auto - Spanish Consular Appointment Bot
color 0A
cd /d "%~dp0"

echo ======================================================================
echo          CITA AUTO - Spanish Consular Appointment Bot
echo ======================================================================
echo.

if not exist config.json (
    if exist config.example.json (
        echo [INFO] config.json not found. Creating from config.example.json...
        copy config.example.json config.json >nul
        echo [NOTICE] Created config.json. Please edit your applicant logins if needed.
        echo.
    )
)

if exist cita_auto.exe (
    echo [LAUNCH] Starting standalone cita_auto.exe...
    echo.
    cita_auto.exe
) else (
    echo [ERROR] cita_auto.exe was not found in this directory!
    echo.
    echo Please ensure cita_auto.exe is placed in the same folder as start_windows.bat and config.json.
    echo If you downloaded the release zip, ensure all files were extracted into this folder.
    echo.
)

echo.
echo ======================================================================
echo Program finished or paused. Press any key to exit.
echo ======================================================================
pause >nul
