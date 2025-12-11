#!/bin/bash
# Erstellt zwei separate Cron-Jobs: 13:00 und 13:15

echo "=== Erstelle zwei separate Cron-Jobs ==="
echo ""

# 1. Erstelle Script für Schiffs_Datenbank.py (13:00)
echo "1. Erstelle run_schiffs_datenbank.sh (13:00 Uhr)..."
cat > /root/Skrip/run_schiffs_datenbank.sh << 'EOF'
#!/bin/bash
# Shell-Script zum Ausführen von Schiffs_Datenbank.py
# Wird täglich um 13:00 Uhr von Cron-Job aufgerufen

SCRIPT_PATH="/root/Skrip/Datenbank/Schiffs_Datenbank.py"
LOG_FILE="/root/Skrip/logs/schiffs_datenbank_cron.log"
LOCK_FILE="/var/lock/schiffs_datenbank.lock"

mkdir -p "$(dirname "$LOG_FILE")"

echo "========================================" >> "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Start Schiffs_Datenbank.py" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

/usr/bin/flock -n "$LOCK_FILE" python3 "$SCRIPT_PATH" --import >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

echo "$(date '+%Y-%m-%d %H:%M:%S') - Schiffs_Datenbank.py beendet (Code: $EXIT_CODE)" >> "$LOG_FILE"
exit $EXIT_CODE
EOF

chmod +x /root/Skrip/run_schiffs_datenbank.sh
echo "   ✓ Script erstellt: /root/Skrip/run_schiffs_datenbank.sh"
echo ""

# 2. Erstelle Script für bilder_downloader.py (13:15)
echo "2. Erstelle run_bilder_downloader.sh (13:15 Uhr)..."
cat > /root/Skrip/run_bilder_downloader.sh << 'EOF'
#!/bin/bash
# Shell-Script zum Ausführen von bilder_downloader.py
# Wird täglich um 13:15 Uhr von Cron-Job aufgerufen

BILDER_SCRIPT="/root/Skrip/Datenbank/bilder_downloader.py"
LOG_FILE="/root/Skrip/logs/bilder_downloader_cron.log"
LOCK_FILE="/var/lock/bilder_downloader.lock"

mkdir -p "$(dirname "$LOG_FILE")"

# Prüfe ob Script existiert
if [ ! -f "$BILDER_SCRIPT" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - FEHLER: bilder_downloader.py nicht gefunden: $BILDER_SCRIPT" >> "$LOG_FILE"
    exit 1
fi

echo "========================================" >> "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Start bilder_downloader.py" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

/usr/bin/flock -n "$LOCK_FILE" python3 "$BILDER_SCRIPT" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

echo "$(date '+%Y-%m-%d %H:%M:%S') - bilder_downloader.py beendet (Code: $EXIT_CODE)" >> "$LOG_FILE"
exit $EXIT_CODE
EOF

chmod +x /root/Skrip/run_bilder_downloader.sh
echo "   ✓ Script erstellt: /root/Skrip/run_bilder_downloader.sh"
echo ""

# 3. Erstelle/aktualisiere Timer-Dateien
echo "3. Erstelle Timer-Dateien..."

# Timer für Schiffs_Datenbank (13:00)
cat > /root/Skrip/Timer/schiffs_datenbank << 'EOF'
# Täglich 13:00 Uhr: Schiffsdaten importieren
0 13 * * * root /usr/bin/flock -n /var/lock/schiffs_datenbank.lock /root/Skrip/run_schiffs_datenbank.sh >> /root/Skrip/logs/schiffs_datenbank_cron.log 2>&1
EOF
echo "   ✓ Timer-Datei erstellt: /root/Skrip/Timer/schiffs_datenbank (13:00 Uhr)"

# Timer für bilder_downloader (13:15)
cat > /root/Skrip/Timer/bilder_downloader << 'EOF'
# Täglich 13:15 Uhr: Schiffsbilder downloaden
15 13 * * * root /usr/bin/flock -n /var/lock/bilder_downloader.lock /root/Skrip/run_bilder_downloader.sh >> /root/Skrip/logs/bilder_downloader_cron.log 2>&1
EOF
echo "   ✓ Timer-Datei erstellt: /root/Skrip/Timer/bilder_downloader (13:15 Uhr)"
echo ""

# 4. Aktualisiere crontab
echo "4. Aktualisiere crontab..."

# Entferne alte Einträge
sudo crontab -l 2>/dev/null | grep -v "schiffs_datenbank\|bilder_downloader" | sudo crontab -

# Füge beide Einträge hinzu
(sudo crontab -l 2>/dev/null; 
 echo "# Täglich 13:00 Uhr: Schiffsdaten importieren";
 echo "0 13 * * * root /usr/bin/flock -n /var/lock/schiffs_datenbank.lock /root/Skrip/run_schiffs_datenbank.sh >> /root/Skrip/logs/schiffs_datenbank_cron.log 2>&1";
 echo "# Täglich 13:15 Uhr: Schiffsbilder downloaden";
 echo "15 13 * * * root /usr/bin/flock -n /var/lock/bilder_downloader.lock /root/Skrip/run_bilder_downloader.sh >> /root/Skrip/logs/bilder_downloader_cron.log 2>&1") | sudo crontab -

echo "   ✓ Crontab aktualisiert"
echo ""

# 5. Prüfe beide Skripte
echo "5. Prüfe Skripte..."
if [ -f "/root/Skrip/Datenbank/Schiffs_Datenbank.py" ]; then
    echo "   ✓ Schiffs_Datenbank.py gefunden"
else
    echo "   ✗ Schiffs_Datenbank.py nicht gefunden"
fi

if [ -f "/root/Skrip/Datenbank/bilder_downloader.py" ]; then
    echo "   ✓ bilder_downloader.py gefunden"
else
    echo "   ⚠️  bilder_downloader.py nicht gefunden (wird beim Lauf eine Fehlermeldung geben)"
fi
echo ""

# 6. Zeige aktuelle Cron-Jobs
echo "6. Aktuelle Cron-Jobs:"
sudo crontab -l | grep -E "schiffs_datenbank|bilder_downloader" | sed 's/^/   /'
echo ""

echo "=== Installation abgeschlossen ==="
echo ""
echo "Cron-Jobs:"
echo "  13:00 Uhr - Schiffs_Datenbank.py --import"
echo "  13:15 Uhr - bilder_downloader.py"
echo ""
echo "Logs:"
echo "  /root/Skrip/logs/schiffs_datenbank_cron.log"
echo "  /root/Skrip/logs/bilder_downloader_cron.log"
echo ""
echo "Zum Testen:"
echo "  /root/Skrip/run_schiffs_datenbank.sh"
echo "  /root/Skrip/run_bilder_downloader.sh"

