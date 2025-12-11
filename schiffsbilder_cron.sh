#!/bin/bash
# Cron-Job Skript für Schiffsbilder
# Wird täglich um 08:00 Uhr ausgeführt

cd /root/Skrip/Datenbank
/usr/bin/python3 /root/Skrip/Datenbank/Schiffsbilder.py >> /root/Skrip/Datenbank/schiffsbilder.log 2>&1
