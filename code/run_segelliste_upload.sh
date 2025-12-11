#!/usr/bin/env bash
set -euo pipefail

#############################################
# KONFIGURATION
#############################################
PYTHON_BIN="/usr/bin/python3"
SCRIPT="/root/Skrip/segelliste_upload.py"

LOGDIR="/root/Skrip/logs"
# Tageslog (YYYY-MM-DD)
TODAY="$(date +%F)"
LOGFILE="${LOGDIR}/segelliste_upload_${TODAY}.log"
LOCKFILE="/tmp/segelliste_upload.lock"

# Aufbewahrungsregeln
RETENTION_DAYS=30          # Alter in Tagen (älter als X Tage -> löschen)
RETENTION_COUNT=0          # 0 = deaktiviert; >0 = maximal so viele Dateien behalten (älteste zuerst löschen)
LOG_PREFIX="segelliste_upload_"
LOG_PATTERN="${LOG_PREFIX}"'*'.log

#############################################
# HILFSFUNKTIONEN
#############################################
log_line () {
  # Schreibt eine Zeile in die aktuelle Tageslogdatei (auch bevor sie existiert)
  # Timestamp konsistent im selben Format wie dein Python-Skript
  echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOGFILE"
}

delete_old_logs_by_age () {
  # Löscht nach Alter (mtime) > RETENTION_DAYS
  # -print vor -delete, damit wir sehen was entfernt wurde
  # 2>/dev/null falls keine Dateien passen
  local deleted
  deleted=$(find "$LOGDIR" -type f -name "${LOG_PATTERN}" -mtime +${RETENTION_DAYS} -print -delete 2>/dev/null || true)
  if [ -n "$deleted" ]; then
    while IFS= read -r f; do
      [ -z "$f" ] && continue
      log_line "[CLEANUP] Entfernt (älter als ${RETENTION_DAYS} Tage): $f"
    done <<< "$deleted"
  fi
}

delete_old_logs_by_count () {
  # Nur ausführen, falls RETENTION_COUNT > 0
  [ "$RETENTION_COUNT" -gt 0 ] || return 0

  # Liste aller Logs sortiert (älteste zuerst) nach mtime
  # Falls sehr viele Dateien existieren, werden die ältesten entfernt, bis nur RETENTION_COUNT übrig sind.
  mapfile -t files < <(ls -1tr "${LOGDIR}"/${LOG_PATTERN} 2>/dev/null || true)
  local total=${#files[@]}
  if [ "$total" -le "$RETENTION_COUNT" ]; then
    return 0
  fi

  local to_delete=$(( total - RETENTION_COUNT ))
  for (( i=0; i<to_delete; i++ )); do
    local f="${files[$i]}"
    [ -f "$f" ] || continue
    rm -f -- "$f"
    log_line "[CLEANUP] Entfernt (Überzählige Datei, Count>${RETENTION_COUNT}): $f"
  done
}

#############################################
# HAUPT
#############################################
mkdir -p "$LOGDIR"

# Symlink auf "aktuelles" Log (vorher löschen, dann neu)
ln -sf "$LOGFILE" "${LOGDIR}/segelliste_upload_current.log"

# 1. Altersbasierte Bereinigung
delete_old_logs_by_age

# 2. Optional: Count-basierte Bereinigung (falls aktiviert)
delete_old_logs_by_count

# Jetzt eigentlicher Lauf mit Lock (flock verhindert Parallelstart)
{
  flock -n 9 || {
    # Läuft schon – kurze Notiz in HEUTIGEM Log
    log_line "[INFO] Lauf übersprungen (bereits aktiv)"
    exit 0
  }

  # Trenner & Start
  echo "------------------------------------------------------------" >> "$LOGFILE"
  log_line "[INFO] Start (PID $$)"

  # Falls du ein Python venv nutzen willst, hier aktivieren:
  # source /root/Skrip/venv/bin/activate

  if ! "$PYTHON_BIN" "$SCRIPT" >>"$LOGFILE" 2>&1; then
    log_line "[ERROR] Skript mit Fehler beendet"
    exit 1
  fi

  log_line "[INFO] Ende"
} 9>"$LOCKFILE"