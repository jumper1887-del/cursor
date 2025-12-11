@echo off
REM Status-Skript für Schiffsbilder.py (Windows)

cd /d "%~dp0"

echo ======================================
echo Schiffsbilder Status
echo ======================================
echo.

REM Prüfe ob Prozess läuft
tasklist /FI "WINDOWTITLE eq Schiffsbilder*" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo Status: ✓ Läuft
    echo.
    
    REM Zeige Prozess-Info
    echo Prozess-Info:
    tasklist /FI "WINDOWTITLE eq Schiffsbilder*" /FO LIST
    echo.
) else (
    echo Status: ✗ Nicht gestartet
    echo.
)

REM Zeige letztes Log
if exist "Log\schiffsbilder_*.log" (
    for /f "delims=" %%i in ('dir /b /o-d Log\schiffsbilder_*.log 2^>nul') do (
        set LATEST_LOG=Log\%%i
        goto :found
    )
)

:found
if defined LATEST_LOG (
    echo Aktuelles Logfile: %LATEST_LOG%
    echo.
    echo Letzte 15 Zeilen:
    echo --------------------------------------
    powershell -Command "Get-Content '%LATEST_LOG%' -Tail 15"
    echo --------------------------------------
    echo.
    echo Live-Log ansehen: powershell Get-Content '%LATEST_LOG%' -Wait -Tail 20
) else (
    echo Kein Logfile gefunden.
)

echo.
pause

