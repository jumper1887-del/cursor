# Installation des Cron-Jobs für Schiffs_Datenbank.py

## Dateien

1. **run_schiffs_datenbank.sh** - Shell-Script zum Ausführen des Python-Skripts
2. **schiffs_datenbank_cron.txt** - Cron-Job-Eintrag

## Installation

### 1. Shell-Script kopieren und ausführbar machen

```bash
# Kopiere das Script nach /root/Skrip/
cp run_schiffs_datenbank.sh /root/Skrip/
chmod +x /root/Skrip/run_schiffs_datenbank.sh
```

### 2. Log-Verzeichnis erstellen (falls nicht vorhanden)

```bash
mkdir -p /root/Skrip/logs
```

### 3. Cron-Job hinzufügen

**Option A: Direkt in crontab einfügen**
```bash
# Öffne crontab für root
sudo crontab -e

# Füge diese Zeile hinzu:
0 13 * * * root /usr/bin/flock -n /var/lock/schiffs_datenbank.lock /root/Skrip/run_schiffs_datenbank.sh >> /root/Skrip/logs/schiffs_datenbank_cron.log 2>&1
```

**Option B: In /root/Skrip/Timer Datei einfügen**
```bash
# Öffne die Timer-Datei
sudo nano /root/Skrip/Timer

# Füge am Ende hinzu:
# Täglich 13:00 Uhr: Schiffsdaten importieren
0 13 * * * root /usr/bin/flock -n /var/lock/schiffs_datenbank.lock /root/Skrip/run_schiffs_datenbank.sh >> /root/Skrip/logs/schiffs_datenbank_cron.log 2>&1

# Dann crontab neu laden (falls die Datei automatisch eingelesen wird)
# Oder manuell: sudo crontab /root/Skrip/Timer
```

## Was macht der Cron-Job?

- **Zeit**: Täglich um 13:00 Uhr
- **Aktion**: Führt `Schiffs_Datenbank.py --import` aus
- **Lock**: Verhindert gleichzeitige Ausführung mit `/usr/bin/flock`
- **Logging**: Alle Ausgaben werden in `/root/Skrip/logs/schiffs_datenbank_cron.log` geschrieben

## Testen

```bash
# Manuell ausführen zum Testen
/root/Skrip/run_schiffs_datenbank.sh

# Log ansehen
tail -f /root/Skrip/logs/schiffs_datenbank_cron.log
```

## Cron-Job prüfen

```bash
# Zeige alle Cron-Jobs für root
sudo crontab -l -u root

# Oder prüfe ob der Job läuft
grep "schiffs_datenbank" /var/log/cron
```

