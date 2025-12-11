#!/bin/bash
# Verifizierungs-Script für den Cron-Job Setup

echo "=== Verifizierung Schiffs_Datenbank Cron-Job ==="
echo ""

# 1. Prüfe ob Script existiert
echo "1. Prüfe run_schiffs_datenbank.sh..."
if [ -f "/root/Skrip/run_schiffs_datenbank.sh" ]; then
    echo "   ✓ Script existiert"
    if [ -x "/root/Skrip/run_schiffs_datenbank.sh" ]; then
        echo "   ✓ Script ist ausführbar"
    else
        echo "   ✗ Script ist nicht ausführbar - setze Berechtigung..."
        chmod +x /root/Skrip/run_schiffs_datenbank.sh
        echo "   ✓ Berechtigung gesetzt"
    fi
    
    # Zeige den Pfad im Script
    echo "   Script-Pfad:"
    grep "SCRIPT_PATH=" /root/Skrip/run_schiffs_datenbank.sh | head -1
else
    echo "   ✗ Script nicht gefunden!"
fi
echo ""

# 2. Prüfe ob Python-Skript existiert
echo "2. Prüfe Schiffs_Datenbank.py..."
PYTHON_SCRIPT="/root/Skrip/Datenbank/Schiffs_Datenbank.py"
if [ -f "$PYTHON_SCRIPT" ]; then
    echo "   ✓ Python-Skript existiert: $PYTHON_SCRIPT"
    ls -lh "$PYTHON_SCRIPT" | awk '{print "   Größe: " $5}'
else
    echo "   ✗ Python-Skript nicht gefunden: $PYTHON_SCRIPT"
fi
echo ""

# 3. Prüfe Timer-Datei
echo "3. Prüfe Timer-Datei..."
TIMER_FILE="/root/Skrip/Timer/schiffs_datenbank"
if [ -f "$TIMER_FILE" ]; then
    echo "   ✓ Timer-Datei existiert: $TIMER_FILE"
    echo "   Inhalt:"
    cat "$TIMER_FILE" | sed 's/^/      /'
else
    echo "   ✗ Timer-Datei nicht gefunden: $TIMER_FILE"
fi
echo ""

# 4. Prüfe ob in crontab eingetragen
echo "4. Prüfe crontab..."
if sudo crontab -l 2>/dev/null | grep -q "schiffs_datenbank"; then
    echo "   ✓ Cron-Job ist in crontab eingetragen:"
    sudo crontab -l | grep "schiffs_datenbank" | sed 's/^/      /'
else
    echo "   ⚠️  Cron-Job nicht in crontab gefunden"
    echo "   Möglicherweise werden Timer-Dateien anders geladen"
fi
echo ""

# 5. Prüfe Log-Verzeichnis
echo "5. Prüfe Log-Verzeichnis..."
LOG_DIR="/root/Skrip/logs"
if [ -d "$LOG_DIR" ]; then
    echo "   ✓ Log-Verzeichnis existiert: $LOG_DIR"
    if [ -f "$LOG_DIR/schiffs_datenbank_cron.log" ]; then
        echo "   ✓ Log-Datei existiert"
        echo "   Letzte 5 Zeilen:"
        tail -5 "$LOG_DIR/schiffs_datenbank_cron.log" | sed 's/^/      /'
    else
        echo "   ⚠️  Log-Datei noch nicht erstellt (wird beim ersten Lauf erstellt)"
    fi
else
    echo "   ⚠️  Log-Verzeichnis existiert nicht (wird beim ersten Lauf erstellt)"
fi
echo ""

# 6. Test-Vorschau
echo "6. Test-Vorschau (trockener Lauf)..."
echo "   Würde ausführen:"
echo "   /usr/bin/flock -n /var/lock/schiffs_datenbank.lock /root/Skrip/run_schiffs_datenbank.sh"
echo ""

# 7. Nächste Cron-Ausführung
echo "7. Nächste Ausführung:"
echo "   Der Cron-Job läuft täglich um 13:00 Uhr"
echo "   Aktuelle Zeit: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

echo "=== Verifizierung abgeschlossen ==="
echo ""
echo "Zum Testen:"
echo "  /root/Skrip/run_schiffs_datenbank.sh"
echo ""
echo "Log beobachten:"
echo "  tail -f /root/Skrip/logs/schiffs_datenbank_cron.log"

