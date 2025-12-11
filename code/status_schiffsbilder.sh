#!/bin/bash
# Status-Skript für Schiffsbilder.py

cd /root/Skrip/Datenbank

echo "======================================"
echo "Schiffsbilder Status"
echo "======================================"
echo ""

if [ ! -f "schiffsbilder.pid" ]; then
    echo "Status: ✗ Nicht gestartet"
    echo ""
    exit 0
fi

PID=$(cat schiffsbilder.pid)

if ps -p $PID > /dev/null 2>&1; then
    echo "Status: ✓ Läuft"
    echo "PID: $PID"
    echo ""
    
    # Zeige Prozess-Info
    echo "Prozess-Info:"
    ps -p $PID -o pid,etime,cmd --no-headers
    echo ""
    
    # Zeige letztes Log
    LATEST_LOG=$(ls -t Log/schiffsbilder_*.log 2>/dev/null | head -1)
    if [ -n "$LATEST_LOG" ]; then
        echo "Aktuelles Logfile: $LATEST_LOG"
        echo ""
        echo "Letzte 15 Zeilen:"
        echo "--------------------------------------"
        tail -15 "$LATEST_LOG"
        echo "--------------------------------------"
        echo ""
        echo "Live-Log ansehen: tail -f $LATEST_LOG"
    fi
else
    echo "Status: ✗ Prozess läuft nicht (PID $PID existiert nicht)"
    echo ""
    rm -f schiffsbilder.pid
fi

echo ""
