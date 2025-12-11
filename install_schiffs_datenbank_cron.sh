#!/bin/bash
# Installations-Script für Schiffs_Datenbank Cron-Job
# Führt alle notwendigen Schritte aus

set -e

echo "=== Installation Schiffs_Datenbank Cron-Job ==="
echo ""

# 1. Erstelle run_schiffs_datenbank.sh
echo "1. Erstelle run_schiffs_datenbank.sh..."
cat > /root/Skrip/run_schiffs_datenbank.sh << 'SCRIPTEOF'
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
SCRIPTEOF

chmod +x /root/Skrip/run_schiffs_datenbank.sh
echo "   ✓ Script erstellt: /root/Skrip/run_schiffs_datenbank.sh"
echo ""

# 2. Erstelle Timer-Datei
echo "2. Erstelle Timer-Datei..."
TIMER_DIR="/root/Skrip/Timer"
TIMER_FILE="$TIMER_DIR/schiffs_datenbank"

# Prüfe ob Timer-Verzeichnis existiert
if [ ! -d "$TIMER_DIR" ]; then
    echo "   ⚠️  Timer-Verzeichnis nicht gefunden: $TIMER_DIR"
    echo "   Erstelle Verzeichnis..."
    mkdir -p "$TIMER_DIR"
fi

# Erstelle Timer-Datei
cat > "$TIMER_FILE" << 'CRONEOF'
# Täglich 13:00 Uhr: Schiffsdaten importieren
0 13 * * * root /usr/bin/flock -n /var/lock/schiffs_datenbank.lock /root/Skrip/run_schiffs_datenbank.sh >> /root/Skrip/logs/schiffs_datenbank_cron.log 2>&1
CRONEOF

echo "   ✓ Timer-Datei erstellt: $TIMER_FILE"
echo ""

# 3. Prüfe bestehende Cron-Struktur
echo "3. Prüfe bestehende Cron-Struktur..."
if [ -f "$TIMER_DIR/segelliste" ]; then
    echo "   ✓ Gefunden: $TIMER_DIR/segelliste"
    echo "   Zeige ersten Eintrag:"
    head -1 "$TIMER_DIR/segelliste"
    echo ""
fi

# 4. Füge zu crontab hinzu
echo "4. Füge Cron-Job zu crontab hinzu..."
CRON_ENTRY="0 13 * * * root /usr/bin/flock -n /var/lock/schiffs_datenbank.lock /root/Skrip/run_schiffs_datenbank.sh >> /root/Skrip/logs/schiffs_datenbank_cron.log 2>&1"

# Prüfe ob Eintrag bereits existiert
if sudo crontab -l 2>/dev/null | grep -q "schiffs_datenbank"; then
    echo "   ⚠️  Cron-Job für schiffs_datenbank existiert bereits"
    echo "   Überspringe Hinzufügen..."
else
    # Füge Eintrag hinzu
    (sudo crontab -l 2>/dev/null; echo "$CRON_ENTRY") | sudo crontab -
    echo "   ✓ Cron-Job hinzugefügt"
fi
echo ""

# 5. Zeige aktuelle Crontab
echo "5. Aktuelle Cron-Jobs (schiffs_datenbank):"
sudo crontab -l | grep "schiffs_datenbank" || echo "   (keine gefunden)"
echo ""

# 6. Test
echo "6. Test: Prüfe ob Script ausführbar ist..."
if [ -x "/root/Skrip/run_schiffs_datenbank.sh" ]; then
    echo "   ✓ Script ist ausführbar"
else
    echo "   ✗ Script ist nicht ausführbar - setze Berechtigung..."
    chmod +x /root/Skrip/run_schiffs_datenbank.sh
    echo "   ✓ Berechtigung gesetzt"
fi
echo ""

echo "=== Installation abgeschlossen ==="
echo ""
echo "Nächste Schritte:"
echo "  1. Teste manuell: /root/Skrip/run_schiffs_datenbank.sh"
echo "  2. Prüfe Log: tail -f /root/Skrip/logs/schiffs_datenbank_cron.log"
echo "  3. Prüfe Cron: sudo crontab -l | grep schiffs_datenbank"
echo ""

