#!/bin/bash
# Installationsskript für Schiffsbilder automatischen Start

SCRIPT_DIR="/root/Skrip/Datenbank"
SERVICE_FILE="schiffsbilder.service"
CRON_FILE="schiffsbilder_cron.sh"

echo "=== Schiffsbilder Installer ==="
echo ""

# Prüfe ob Skript existiert
if [ ! -f "$SCRIPT_DIR/Schiffsbilder.py" ]; then
    echo "FEHLER: Schiffsbilder.py nicht gefunden in $SCRIPT_DIR"
    exit 1
fi

# Mache Skripte ausführbar
chmod +x "$SCRIPT_DIR/start_schiffsbilder.sh"
chmod +x "$SCRIPT_DIR/schiffsbilder_cron.sh"

echo "Wähle Installationsmethode:"
echo "1) systemd Service (empfohlen - läuft als Hintergrund-Service)"
echo "2) Cron Job (täglich um 08:00 Uhr)"
echo "3) Beide"
read -p "Auswahl (1-3): " choice

case $choice in
    1)
        echo ""
        echo "Installiere systemd Service..."
        sudo cp "$SCRIPT_DIR/$SERVICE_FILE" /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable schiffsbilder.service
        echo "Service installiert und aktiviert!"
        echo ""
        echo "Befehle:"
        echo "  Start:   sudo systemctl start schiffsbilder"
        echo "  Stop:    sudo systemctl stop schiffsbilder"
        echo "  Status:  sudo systemctl status schiffsbilder"
        echo "  Logs:    sudo journalctl -u schiffsbilder -f"
        ;;
    2)
        echo ""
        echo "Installiere Cron Job..."
        # Füge Cron Job hinzu (täglich um 08:00)
        (crontab -l 2>/dev/null; echo "0 8 * * * $SCRIPT_DIR/$CRON_FILE") | crontab -
        echo "Cron Job installiert! Läuft täglich um 08:00 Uhr"
        echo ""
        echo "Cron Jobs anzeigen: crontab -l"
        ;;
    3)
        echo ""
        echo "Installiere systemd Service..."
        sudo cp "$SCRIPT_DIR/$SERVICE_FILE" /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable schiffsbilder.service
        
        echo ""
        echo "Installiere Cron Job..."
        (crontab -l 2>/dev/null; echo "0 8 * * * $SCRIPT_DIR/$CRON_FILE") | crontab -
        
        echo ""
        echo "Beide Methoden installiert!"
        echo ""
        echo "systemd Service:"
        echo "  Start:   sudo systemctl start schiffsbilder"
        echo "  Status:  sudo systemctl status schiffsbilder"
        echo ""
        echo "Cron Job:"
        echo "  Anzeigen: crontab -l"
        ;;
    *)
        echo "Ungültige Auswahl!"
        exit 1
        ;;
esac

echo ""
echo "=== Installation abgeschlossen ==="

