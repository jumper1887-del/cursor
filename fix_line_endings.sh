#!/bin/bash
# Konvertiert Windows-Zeilenenden zu Unix-Zeilenenden

cd /root/Skrip/Datenbank

# Installiere dos2unix falls nicht vorhanden
if ! command -v dos2unix &> /dev/null; then
    echo "Installiere dos2unix..."
    apt-get update && apt-get install -y dos2unix
fi

# Konvertiere alle .sh Dateien
dos2unix *.sh 2>/dev/null || sed -i 's/\r$//' *.sh

echo "Zeilenenden korrigiert!"

