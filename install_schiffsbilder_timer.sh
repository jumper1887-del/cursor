#!/bin/bash
# Installiert Schiffsbilder als systemd Timer
# Läuft täglich um 08:00 Uhr, auch wenn Rechner zu diesem Zeitpunkt aus war

SCRIPT_DIR="/root/Skrip/Datenbank"

echo "=== Schiffsbilder Timer Installation ==="
echo ""

# Prüfe ob Dateien existieren
if [ ! -f "$SCRIPT_DIR/Schiffsbilder.py" ]; then
    echo "FEHLER: Schiffsbilder.py nicht gefunden in $SCRIPT_DIR"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/schiffsbilder.service" ]; then
    echo "FEHLER: schiffsbilder.service nicht gefunden"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/schiffsbilder.timer" ]; then
    echo "FEHLER: schiffsbilder.timer nicht gefunden"
    exit 1
fi

# Installiere Service
echo "Installiere systemd Service..."
sudo cp "$SCRIPT_DIR/schiffsbilder.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable schiffsbilder.service

# Installiere Timer
echo "Installiere systemd Timer..."
sudo cp "$SCRIPT_DIR/schiffsbilder.timer" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable schiffsbilder.timer
sudo systemctl start schiffsbilder.timer

echo ""
echo "=== Installation abgeschlossen ==="
echo ""
echo "Timer Status:"
sudo systemctl status schiffsbilder.timer --no-pager -l

echo ""
echo "Nützliche Befehle:"
echo "  Status:    sudo systemctl status schiffsbilder.timer"
echo "  Start:     sudo systemctl start schiffsbilder.timer"
echo "  Stop:      sudo systemctl stop schiffsbilder.timer"
echo "  Nächster:  sudo systemctl list-timers schiffsbilder.timer"
echo "  Logs:      sudo journalctl -u schiffsbilder.service -f"

