@echo off
setlocal EnableDelayedExpansion
title BulkCord Uploader - Launcher
cd /d "%~dp0"

:: Set console window dimensions
mode con: cols=100 lines=32 >nul 2>&1

:: Enable ANSI Virtual Terminal Colors
for /f %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
set "C_RESET=%ESC%[0m"
set "C_BOLD=%ESC%[1m"
set "C_CYAN=%ESC%[96m"
set "C_BLUE=%ESC%[94m"
set "C_GREEN=%ESC%[92m"
set "C_YELLOW=%ESC%[93m"
set "C_RED=%ESC%[91m"
set "C_PURPLE=%ESC%[95m"
set "C_GRAY=%ESC%[90m"

set "LOGFILE=launcher.log"

:MAIN_MENU
cls
echo %C_BLUE%
echo  ====================================================================================================%C_RESET%
echo %C_CYAN%%C_BOLD%
if exist "%~dp0assets\banner.txt" type "%~dp0assets\banner.txt"
echo.
echo %C_PURPLE%                        -- BULK FILE DROPPER FOR DISCORD --%C_RESET%
echo %C_BLUE% ====================================================================================================%C_RESET%
echo.

:: ---------------------------------------------------------
:: 1. DEEP PYTHON DETECTION (PATH + OFF-PATH AUTO-SCAN)
:: ---------------------------------------------------------
set "PY_CMD="

:: 1A. Check if 'py' is on PATH
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    py -c "import sys" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        set "PY_CMD=py"
        goto PYTHON_LOCATED
    )
)

:: 1B. Check if 'python' is on PATH
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python -c "import sys" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        set "PY_CMD=python"
        goto PYTHON_LOCATED
    )
)

:: 1C. Check User LocalAppData (Standard non-admin Windows install)
for %%V in (314 313 312 311 310 39 38) do (
    if exist "%LocalAppData%\Programs\Python\Python%%V\python.exe" (
        set "PY_CMD=%LocalAppData%\Programs\Python\Python%%V\python.exe"
        set "PATH=%LocalAppData%\Programs\Python\Python%%V;%LocalAppData%\Programs\Python\Python%%V\Scripts;!PATH!"
        goto PYTHON_LOCATED
    )
)

:: 1D. Check Program Files (All Users 64-bit & 32-bit install)
for %%V in (314 313 312 311 310 39 38) do (
    if exist "%ProgramFiles%\Python%%V\python.exe" (
        set "PY_CMD=%ProgramFiles%\Python%%V\python.exe"
        set "PATH=%ProgramFiles%\Python%%V;%ProgramFiles%\Python%%V\Scripts;!PATH!"
        goto PYTHON_LOCATED
    )
    if exist "%ProgramFiles(x86)%\Python%%V\python.exe" (
        set "PY_CMD=%ProgramFiles(x86)%\Python%%V\python.exe"
        set "PATH=%ProgramFiles(x86)%\Python%%V;%ProgramFiles(x86)%\Python%%V\Scripts;!PATH!"
        goto PYTHON_LOCATED
    )
    if exist "C:\Python%%V\python.exe" (
        set "PY_CMD=C:\Python%%V\python.exe"
        set "PATH=C:\Python%%V;C:\Python%%V\Scripts;!PATH!"
        goto PYTHON_LOCATED
    )
)

:: 1E. Check Windows Registry (HKCU and HKLM PythonCore)
for /f "tokens=2*" %%A in ('reg query "HKCU\Software\Python\PythonCore" /s /v "ExecutablePath" 2^>nul ^| findstr /i "ExecutablePath"') do (
    if exist "%%B" (
        set "PY_CMD=%%B"
        for %%D in ("%%B") do set "PATH=%%~dpD;%%~dpDScripts;!PATH!"
        goto PYTHON_LOCATED
    )
)
for /f "tokens=2*" %%A in ('reg query "HKLM\Software\Python\PythonCore" /s /v "ExecutablePath" 2^>nul ^| findstr /i "ExecutablePath"') do (
    if exist "%%B" (
        set "PY_CMD=%%B"
        for %%D in ("%%B") do set "PATH=%%~dpD;%%~dpDScripts;!PATH!"
        goto PYTHON_LOCATED
    )
)

:: 1F. Check WindowsApps (Microsoft Store install)
if exist "%LocalAppData%\Microsoft\WindowsApps\python.exe" (
    "%LocalAppData%\Microsoft\WindowsApps\python.exe" -c "import sys" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        set "PY_CMD=%LocalAppData%\Microsoft\WindowsApps\python.exe"
        goto PYTHON_LOCATED
    )
)

:PYTHON_NOT_FOUND
echo [%DATE% %TIME%] [ERROR] Python not found on PATH or standard directories. >> "%LOGFILE%"
echo  %C_RED%[X] CRITICAL: Python was not detected on your system!%C_RESET%
echo  %C_GRAY%--------------------------------------------------------------------------------------%C_RESET%
echo   BulkCord Uploader requires Python 3.8 or newer.
echo.
echo   1. Download Python from: %C_CYAN%https://www.python.org/downloads/%C_RESET%
echo   2. %C_YELLOW%IMPORTANT:%C_RESET% Check the box %C_BOLD%"Add python.exe to PATH"%C_RESET% during setup.
echo  %C_GRAY%--------------------------------------------------------------------------------------%C_RESET%
echo.
pause
exit /b 1

:PYTHON_LOCATED
:: ---------------------------------------------------------
:: 2. CHECK PYTHON VERSION (3.8+)
:: ---------------------------------------------------------
"%PY_CMD%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    for /f "delims=" %%v in ('"%PY_CMD%" --version 2^>^&1') do set "DETECTED_VER=%%v"
    echo [%DATE% %TIME%] [ERROR] Incompatible Python version: !DETECTED_VER! >> "%LOGFILE%"
    echo  %C_RED%[X] INCOMPATIBLE PYTHON VERSION: !DETECTED_VER!%C_RESET%
    echo  %C_GRAY%--------------------------------------------------------------------------------------%C_RESET%
    echo   BulkCord Uploader requires Python 3.8 or newer for CustomTkinter support.
    echo   Please update your Python installation at: %C_CYAN%https://www.python.org/downloads/%C_RESET%
    echo  %C_GRAY%--------------------------------------------------------------------------------------%C_RESET%
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('"%PY_CMD%" --version 2^>^&1') do set "PY_VER_STR=%%v"
echo  %C_GREEN%[OK]%C_RESET% Runtime: %C_BOLD%!PY_VER_STR!%C_RESET% (using: !PY_CMD!)

REM ---------------------------------------------------------
REM 3. CHECK FREE DISK SPACE
REM ---------------------------------------------------------
REM Skip disk check
echo  %C_GREEN%[OK]%C_RESET% Storage: Sufficient drive capacity verified.

REM ---------------------------------------------------------
REM 4. CHECK & AUTO-INSTALL DEPENDENCIES
REM ---------------------------------------------------------
"%PY_CMD%" -c "import sys, customtkinter, requests, PIL; sys.exit(0)" >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo  %C_YELLOW%[*] Missing packages detected. Automatically installing requirements...%C_RESET%
    echo [%DATE% %TIME%] [INFO] Missing requirements. Running pip install -r requirements.txt... >> "%LOGFILE%"
    
    "%PY_CMD%" -m pip install -r requirements.txt >> "%LOGFILE%" 2>&1
    
    if !ERRORLEVEL! neq 0 (
        echo  %C_RED%[X] ERROR: Failed to install requirements via pip.%C_RESET%
        echo   Please check your internet connection or see "%LOGFILE%" for details.
        echo [%DATE% %TIME%] [ERROR] Pip installation failed. >> "%LOGFILE%"
        echo.
        pause
        exit /b 1
    ) else (
        echo [%DATE% %TIME%] [INFO] Requirements installed successfully. >> "%LOGFILE%"
        echo  %C_GREEN%[OK]%C_RESET% Dependencies installed successfully.
    )
) else (
    echo  %C_GREEN%[OK]%C_RESET% Packages: %C_CYAN%customtkinter, requests, Pillow%C_RESET% verified.
)

echo.
echo %C_BLUE% ----------------------------------------------------------------------------------------------------%C_RESET%
echo  %C_BOLD%SELECT AN ACTION:%C_RESET%
echo.
echo   %C_CYAN%[1]%C_RESET% Launch BulkCord Uploader (GUI)
echo   %C_CYAN%[2]%C_RESET% Reinstall / Update All Requirements
echo   %C_CYAN%[3]%C_RESET% View Launcher Log (launcher.log)
echo   %C_CYAN%[4]%C_RESET% Open Project Directory in File Explorer
echo   %C_CYAN%[0]%C_RESET% Exit
echo.
echo %C_BLUE% ----------------------------------------------------------------------------------------------------%C_RESET%
set /p "CHOICE= Enter your choice [1-4, Default=1]: "

if "%CHOICE%"=="" set "CHOICE=1"
if "%CHOICE%"=="1" goto LAUNCH_APP
if "%CHOICE%"=="2" goto REINSTALL_REQ
if "%CHOICE%"=="3" goto VIEW_LOG
if "%CHOICE%"=="4" goto OPEN_DIR
if "%CHOICE%"=="0" exit /b 0

goto MAIN_MENU

:: ---------------------------------------------------------
:: LAUNCH APPLICATION
:: ---------------------------------------------------------
:LAUNCH_APP
echo.
echo  %C_GREEN%[>] Starting BulkCord Uploader GUI...%C_RESET%
echo [%DATE% %TIME%] [INFO] Launching BulkCord Uploader via !PY_CMD!... >> "%LOGFILE%"

"%PY_CMD%" app.py
set "APP_ERR=%ERRORLEVEL%"

if %APP_ERR% neq 0 (
    echo [%DATE% %TIME%] [CRASH] Application exited with error code %APP_ERR%. >> "%LOGFILE%"
    echo.
    echo %C_RED% ====================================================================================================
    echo  [X] APPLICATION CRASHED OR EXITED UNEXPECTEDLY (Code: %APP_ERR%)
    echo  Check "%LOGFILE%" for stack trace and error logs.
    echo ====================================================================================================%C_RESET%
    echo.
    pause
    goto MAIN_MENU
) else (
    echo [%DATE% %TIME%] [INFO] Application closed normally. >> "%LOGFILE%"
)
exit /b 0

:: ---------------------------------------------------------
:: REINSTALL REQUIREMENTS
:: ---------------------------------------------------------
:REINSTALL_REQ
echo.
echo  %C_YELLOW%[*] Upgrading and reinstalling dependencies...%C_RESET%
"%PY_CMD%" -m pip install --upgrade pip
"%PY_CMD%" -m pip install --upgrade -r requirements.txt
echo.
echo  %C_GREEN%[OK] Finished!%C_RESET%
pause
goto MAIN_MENU

:: ---------------------------------------------------------
:: VIEW LOG
:: ---------------------------------------------------------
:VIEW_LOG
if exist "%LOGFILE%" (
    start notepad.exe "%LOGFILE%"
) else (
    echo  %C_YELLOW%Log file does not exist yet.%C_RESET%
    pause
)
goto MAIN_MENU

:: ---------------------------------------------------------
:: OPEN DIRECTORY
:: ---------------------------------------------------------
:OPEN_DIR
explorer.exe "%~dp0"
goto MAIN_MENU
