@echo off
REM Startet Schiffsbilder.py im Hintergrund ohne Fenster
REM Für automatischen Start z.B. über Task Scheduler

cd /d "%~dp0"
start /B pythonw Schiffsbilder.py

REM Optional: Log-Datei erstellen
REM pythonw Schiffsbilder.py >> schiffsbilder_log.txt 2>&1

