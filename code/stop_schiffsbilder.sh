#!/bin/bash
# Stop-Skript für Schiffsbilder.py

cd /root/Skrip/Datenbank

if [ ! -f "schiffsbilder.pid" ]; then
    echo "✗ Kein laufender Prozess gefunden (keine PID-Datei)"
    exit 1
fi

PID=$(cat schiffsbilder.pid)

if ps -p $PID > /dev/null 2>&1; then
    echo "Stoppe Schiffsbilder (PID: $PID)..."
    kill $PID
    
    # Warte bis Prozess beendet ist
    for i in {1..10}; do
        if ! ps -p $PID > /dev/null 2>&1; then
            echo "✓ Prozess erfolgreich gestoppt"
            rm -f schiffsbilder.pid
            exit 0
        fi
        sleep 1
    done
    
    # Falls noch läuft, hart beenden
    if ps -p $PID > /dev/null 2>&1; then
        echo "⚠️  Prozess reagiert nicht, beende hart..."
        kill -9 $PID
        rm -f schiffsbilder.pid
        echo "✓ Prozess gestoppt (SIGKILL)"
    fi
else
    echo "✗ Prozess läuft nicht mehr (PID $PID existiert nicht)"
    rm -f schiffsbilder.pid
fi
