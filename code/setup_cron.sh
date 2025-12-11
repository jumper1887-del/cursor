#!/bin/bash
# Richtet den Cron-Job für Schiffsbilder ein

SCRIPT_DIR="/root/Skrip/Datenbank"
CRON_FILE="schiffsbilder_cron.sh"

# Mache Skript ausführbar
chmod +x "$SCRIPT_DIR/$CRON_FILE"

# Entferne alte Einträge
crontab -l 2>/dev/null | grep -v "$CRON_FILE" | crontab -

# Füge neuen Cron-Job hinzu (täglich um 08:00)
(crontab -l 2>/dev/null; echo "0 8 * * * $SCRIPT_DIR/$CRON_FILE") | crontab -

echo "Cron-Job installiert!"
echo "Zeitplan: Täglich um 08:00 Uhr"
echo ""
echo "Aktuelle Cron-Jobs:"
crontab -l | grep -v "^#"

