#!/bin/bash
# Passe das Script mit dem korrekten Pfad an

echo "=== Passe run_schiffs_datenbank.sh an ==="

cat > /root/Skrip/run_schiffs_datenbank.sh << 'EOF'
#!/bin/bash
# Shell-Script zum Ausführen von Schiffs_Datenbank.py
# Wird von Cron-Job aufgerufen

# Pfad zum Python-Skript (korrigierter Pfad)
SCRIPT_PATH="/root/Skrip/Datenbank/Schiffs_Datenbank.py"
LOG_FILE="/root/Skrip/logs/schiffs_datenbank_cron.log"
LOCK_FILE="/var/lock/schiffs_datenbank.lock"

# Erstelle Log-Verzeichnis falls nicht vorhanden
mkdir -p "$(dirname "$LOG_FILE")"

# Führe das Skript mit --import aus (sucht Schiffe und importiert Daten)
/usr/bin/flock -n "$LOCK_FILE" python3 "$SCRIPT_PATH" --import >> "$LOG_FILE" 2>&1

exit $?
EOF

chmod +x /root/Skrip/run_schiffs_datenbank.sh

echo "✓ Script aktualisiert mit Pfad: /root/Skrip/Datenbank/Schiffs_Datenbank.py"
echo ""
echo "=== Test ==="
echo "Führe Test aus..."
/root/Skrip/run_schiffs_datenbank.sh

echo ""
echo "=== Prüfe Log (letzte 20 Zeilen) ==="
if [ -f "/root/Skrip/logs/schiffs_datenbank_cron.log" ]; then
    tail -20 /root/Skrip/logs/schiffs_datenbank_cron.log
else
    echo "Log-Datei noch nicht erstellt (wird beim ersten Lauf erstellt)"
fi

echo ""
echo "=== Fertig ==="
echo "Das Script sollte jetzt funktionieren!"
echo "Prüfe mit: tail -f /root/Skrip/logs/schiffs_datenbank_cron.log"

