#!/bin/bash
# Aktualisiert den Cron-Job auf 13:15 und fügt bilder_downloader.py hinzu

echo "=== Aktualisiere Cron-Job auf 13:15 mit bilder_downloader.py ==="
echo ""

# 1. Erweitere run_schiffs_datenbank.sh um bilder_downloader.py
echo "1. Erweitere run_schiffs_datenbank.sh..."
cat > /root/Skrip/run_schiffs_datenbank.sh << 'EOF'
#!/bin/bash
# Shell-Script zum Ausführen von Schiffs_Datenbank.py und bilder_downloader.py
# Wird von Cron-Job aufgerufen

# Pfade
SCRIPT_PATH="/root/Skrip/Datenbank/Schiffs_Datenbank.py"
BILDER_SCRIPT="/root/Skrip/Datenbank/bilder_downloader.py"
LOG_FILE="/root/Skrip/logs/schiffs_datenbank_cron.log"
LOCK_FILE="/var/lock/schiffs_datenbank.lock"

# Erstelle Log-Verzeichnis falls nicht vorhanden
mkdir -p "$(dirname "$LOG_FILE")"

# Log-Trenner
echo "========================================" >> "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Start Cron-Job" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# 1. Führe Schiffs_Datenbank.py aus
echo "$(date '+%Y-%m-%d %H:%M:%S') - Starte Schiffs_Datenbank.py" >> "$LOG_FILE"
/usr/bin/flock -n "$LOCK_FILE" python3 "$SCRIPT_PATH" --import >> "$LOG_FILE" 2>&1
EXIT_CODE_1=$?

if [ $EXIT_CODE_1 -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Schiffs_Datenbank.py erfolgreich" >> "$LOG_FILE"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Schiffs_Datenbank.py mit Fehler beendet (Code: $EXIT_CODE_1)" >> "$LOG_FILE"
fi

# 2. Führe bilder_downloader.py aus (falls vorhanden)
if [ -f "$BILDER_SCRIPT" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Starte bilder_downloader.py" >> "$LOG_FILE"
    python3 "$BILDER_SCRIPT" >> "$LOG_FILE" 2>&1
    EXIT_CODE_2=$?
    
    if [ $EXIT_CODE_2 -eq 0 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - bilder_downloader.py erfolgreich" >> "$LOG_FILE"
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') - bilder_downloader.py mit Fehler beendet (Code: $EXIT_CODE_2)" >> "$LOG_FILE"
    fi
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - WARNUNG: bilder_downloader.py nicht gefunden: $BILDER_SCRIPT" >> "$LOG_FILE"
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - Cron-Job beendet" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Exit mit Fehlercode wenn eines der Skripte fehlgeschlagen ist
if [ $EXIT_CODE_1 -ne 0 ] || [ $EXIT_CODE_2 -ne 0 ]; then
    exit 1
fi

exit 0
EOF

chmod +x /root/Skrip/run_schiffs_datenbank.sh
echo "   ✓ Script aktualisiert"
echo ""

# 2. Aktualisiere Timer-Datei auf 13:15
echo "2. Aktualisiere Timer-Datei auf 13:15..."
cat > /root/Skrip/Timer/schiffs_datenbank << 'EOF'
# Täglich 13:15 Uhr: Schiffsdaten importieren und Bilder downloaden
15 13 * * * root /usr/bin/flock -n /var/lock/schiffs_datenbank.lock /root/Skrip/run_schiffs_datenbank.sh >> /root/Skrip/logs/schiffs_datenbank_cron.log 2>&1
EOF
echo "   ✓ Timer-Datei aktualisiert (13:15 Uhr)"
echo ""

# 3. Aktualisiere crontab
echo "3. Aktualisiere crontab..."
# Entferne alten Eintrag (13:00)
sudo crontab -l 2>/dev/null | grep -v "schiffs_datenbank" | sudo crontab -

# Füge neuen Eintrag hinzu (13:15)
(sudo crontab -l 2>/dev/null; echo "15 13 * * * root /usr/bin/flock -n /var/lock/schiffs_datenbank.lock /root/Skrip/run_schiffs_datenbank.sh >> /root/Skrip/logs/schiffs_datenbank_cron.log 2>&1") | sudo crontab -

echo "   ✓ Crontab aktualisiert"
echo ""

# 4. Prüfe ob bilder_downloader.py existiert
echo "4. Prüfe bilder_downloader.py..."
if [ -f "/root/Skrip/Datenbank/bilder_downloader.py" ]; then
    echo "   ✓ bilder_downloader.py gefunden"
    ls -lh /root/Skrip/Datenbank/bilder_downloader.py | awk '{print "   Größe: " $5}'
else
    echo "   ⚠️  bilder_downloader.py nicht gefunden: /root/Skrip/Datenbank/bilder_downloader.py"
    echo "   Das Script wird trotzdem versuchen, es auszuführen (mit Warnung im Log)"
fi
echo ""

# 5. Zeige aktuelle Crontab
echo "5. Aktuelle Cron-Jobs (schiffs_datenbank):"
sudo crontab -l | grep "schiffs_datenbank" | sed 's/^/   /'
echo ""

echo "=== Aktualisierung abgeschlossen ==="
echo ""
echo "Der Cron-Job läuft jetzt täglich um 13:15 Uhr"
echo "Führt aus:"
echo "  1. Schiffs_Datenbank.py --import"
echo "  2. bilder_downloader.py (falls vorhanden)"
echo ""
echo "Zum Testen:"
echo "  /root/Skrip/run_schiffs_datenbank.sh"

