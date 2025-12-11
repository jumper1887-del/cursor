#!/bin/bash
# Shell-Script zum Ausführen von Schiffs_Datenbank.py
# Wird von Cron-Job aufgerufen

# Pfad zum Python-Skript
SCRIPT_PATH="/root/Skrip/Schiffs_Datenbank.py"
LOG_FILE="/root/Skrip/logs/schiffs_datenbank_cron.log"
LOCK_FILE="/var/lock/schiffs_datenbank.lock"

# Erstelle Log-Verzeichnis falls nicht vorhanden
mkdir -p "$(dirname "$LOG_FILE")"

# Führe das Skript mit --import aus (sucht Schiffe und importiert Daten)
/usr/bin/flock -n "$LOCK_FILE" python3 "$SCRIPT_PATH" --import >> "$LOG_FILE" 2>&1

exit $?

