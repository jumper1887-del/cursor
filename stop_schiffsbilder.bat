@echo off
REM Stop-Skript für Schiffsbilder.py (Windows)

cd /d "%~dp0"

echo Stoppe Schiffsbilder...

REM Suche nach Python-Prozessen die Schiffsbilder.py ausführen
tasklist /FI "WINDOWTITLE eq Schiffsbilder*" 2>NUL | find /I /N "python.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo Prozess gefunden, beende...
    taskkill /FI "WINDOWTITLE eq Schiffsbilder*" /T /F >nul 2>&1
    echo ✓ Prozess gestoppt
) else (
    REM Alternative: Suche nach Prozess über Kommandozeile
    for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV ^| findstr /I "Schiffsbilder"') do (
        set PID=%%a
        goto :kill
    )
    echo ✗ Kein laufender Prozess gefunden
    exit /b 1
)

:kill
REM Versuche Prozess über PID zu beenden (falls gefunden)
if defined PID (
    taskkill /PID %PID% /T /F >nul 2>&1
    echo ✓ Prozess gestoppt (PID: %PID%)
) else (
    echo ✗ Kein laufender Prozess gefunden
)

pause

