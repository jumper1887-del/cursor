# Repository-Struktur

## Ordner-Organisation

```
├── scripts/          # Python-Skripte
├── shell/           # Shell-Skripte (.sh, .bat)
├── docs/            # Dokumentation (.md)
├── config/          # Konfigurationsdateien (.gs, .tsx, etc.)
├── services/        # Systemd-Service-Dateien
├── timers/          # Systemd-Timer-Dateien
├── chats/           # Chat-Verläufe
├── supabase/        # Supabase-Konfiguration
└── fertig/          # Fertige Projekte
```

## Was wird synchronisiert:

✅ **Wird synchronisiert:**
- Alle Python-Skripte (`scripts/`)
- Alle Shell-Skripte (`shell/`)
- Dokumentation (`docs/`)
- Konfigurationsdateien (`config/`)
- Chat-Verläufe (`chats/`)

❌ **Wird NICHT synchronisiert** (siehe `.gitignore`):
- Log-Dateien (*.log)
- Credentials (*.json mit Secrets)
- Medien-Dateien (*.jpg, *.png)
- Temporäre Dateien
- Sensible Daten

