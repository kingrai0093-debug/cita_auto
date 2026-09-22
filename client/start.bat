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
    echo [INFO] cita_auto.exe not found in this folder.
    echo [INFO] Attempting to run via Python...
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        python cita_auto.py
    ) else (
        where py >nul 2>nul
        if %ERRORLEVEL% equ 0 (
            py cita_auto.py
        ) else (
            echo.
            echo [ERROR] Neither cita_auto.exe nor Python was found on your system!
            echo To create cita_auto.exe, install Python from https://python.org
            echo and double-click build_exe.bat!
            echo.
        )
    )
)

echo.
echo ======================================================================
echo Program finished or paused. Press any key to exit.
echo ======================================================================
pause >nul
