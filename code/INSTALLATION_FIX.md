# Korrigierte Installation für Schiffs_Datenbank Cron-Job

## Problem
- `/root/Skrip/Timer` ist ein **Verzeichnis**, keine Datei
- Die Datei `run_schiffs_datenbank.sh` muss erst auf den Server kopiert werden

## Lösung

### Schritt 1: Datei auf Server kopieren

**Option A: Mit SCP von Windows aus:**
```bash
# Von deinem Windows-Computer aus:
scp run_schiffs_datenbank.sh root@dein-server:/root/Skrip/
```

**Option B: Datei manuell erstellen auf dem Server:**
```bash
# Auf dem Server:
cat > /root/Skrip/run_schiffs_datenbank.sh << 'EOF'
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
EOF

chmod +x /root/Skrip/run_schiffs_datenbank.sh
```

### Schritt 2: Timer-Datei erstellen oder prüfen

Da `/root/Skrip/Timer` ein Verzeichnis ist, müssen wir prüfen, wie die Cron-Jobs geladen werden:

```bash
# Prüfe, ob es eine zentrale Cron-Datei gibt
ls -la /root/Skrip/Timer/

# Schaue, wie die bestehenden Timer-Dateien aussehen
cat /root/Skrip/Timer/segelliste
```

### Schritt 3: Neue Timer-Datei erstellen

```bash
# Erstelle eine neue Timer-Datei für Schiffs_Datenbank
cat > /root/Skrip/Timer/schiffs_datenbank << 'EOF'
# Täglich 13:00 Uhr: Schiffsdaten importieren
0 13 * * * root /usr/bin/flock -n /var/lock/schiffs_datenbank.lock /root/Skrip/run_schiffs_datenbank.sh >> /root/Skrip/logs/schiffs_datenbank_cron.log 2>&1
EOF
```

### Schritt 4: Cron-Jobs neu laden

**Prüfe zuerst, wie die Cron-Jobs geladen werden:**

```bash
# Option 1: Wenn es ein Script gibt, das alle Timer-Dateien einliest
# (z.B. update_timer_log_links.sh könnte ein Hinweis sein)
cat /root/Skrip/Timer/update_timer_log_links.sh

# Option 2: Manuell in crontab einfügen
sudo crontab -e
# Dann diese Zeile hinzufügen:
# 0 13 * * * root /usr/bin/flock -n /var/lock/schiffs_datenbank.lock /root/Skrip/run_schiffs_datenbank.sh >> /root/Skrip/logs/schiffs_datenbank_cron.log 2>&1

# Option 3: Alle Timer-Dateien zusammenführen
cat /root/Skrip/Timer/* | sudo crontab -
```

### Schritt 5: Testen

```bash
# Teste das Script manuell
/root/Skrip/run_schiffs_datenbank.sh

# Prüfe das Log
tail -f /root/Skrip/logs/schiffs_datenbank_cron.log

# Prüfe ob Cron-Job eingetragen ist
sudo crontab -l | grep schiffs_datenbank
```

