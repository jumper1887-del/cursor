#!/bin/bash
# Startet Schiffsbilder sofort (ohne auf Timer zu warten)

cd /root/Skrip/Datenbank

echo "=== Starte Schiffsbilder jetzt ==="
echo ""

# Starte den Service direkt (ohne Timer)
sudo systemctl start schiffsbilder.service

echo "Skript gestartet!"
echo ""
echo "Status prüfen mit:"
echo "  sudo systemctl status schiffsbilder.service"
echo ""
echo "Logs live anzeigen mit:"
echo "  sudo journalctl -u schiffsbilder.service -f"
echo ""
echo "Das Skript läuft jetzt im Hintergrund weiter, auch wenn du dich abmeldest!"

