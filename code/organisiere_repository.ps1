# PowerShell-Script zur Organisation des Repositorys
# Verschiebt alle Dateien in die entsprechenden Ordner und synchronisiert mit Git

Write-Host "=== Repository-Organisation ===" -ForegroundColor Cyan
Write-Host ""

# Pruefe ob Git Repository vorhanden ist
if (-not (Test-Path ".git")) {
    Write-Host "FEHLER: Kein Git-Repository gefunden!" -ForegroundColor Red
    exit 1
}

# Erstelle Ordner falls nicht vorhanden
$ordner = @("scripts", "shell", "docs", "config", "services", "timers")
foreach ($o in $ordner) {
    if (-not (Test-Path $o)) {
        New-Item -ItemType Directory -Path $o -Force | Out-Null
        Write-Host "OK Ordner erstellt: $o" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Verschiebe Dateien..." -ForegroundColor Yellow

# Python-Dateien nach scripts/
$pythonFiles = Get-ChildItem -File -Filter "*.py" -ErrorAction SilentlyContinue | Where-Object { $_.Directory.Name -eq "Script" }
foreach ($file in $pythonFiles) {
    $destination = Join-Path "scripts" $file.Name
    if (-not (Test-Path $destination)) {
        Move-Item -Path $file.FullName -Destination $destination -Force -ErrorAction SilentlyContinue
        Write-Host "  -> $($file.Name) -> scripts/" -ForegroundColor Gray
    }
}

# Shell-Skripte nach shell/
$shellFiles = Get-ChildItem -File -Filter "*.sh" -ErrorAction SilentlyContinue | Where-Object { $_.Directory.Name -eq "Script" }
foreach ($file in $shellFiles) {
    $destination = Join-Path "shell" $file.Name
    if (-not (Test-Path $destination)) {
        Move-Item -Path $file.FullName -Destination $destination -Force -ErrorAction SilentlyContinue
        Write-Host "  -> $($file.Name) -> shell/" -ForegroundColor Gray
    }
}

# Batch-Dateien nach shell/
$batFiles = Get-ChildItem -File -Filter "*.bat" -ErrorAction SilentlyContinue | Where-Object { $_.Directory.Name -eq "Script" }
foreach ($file in $batFiles) {
    $destination = Join-Path "shell" $file.Name
    if (-not (Test-Path $destination)) {
        Move-Item -Path $file.FullName -Destination $destination -Force -ErrorAction SilentlyContinue
        Write-Host "  -> $($file.Name) -> shell/" -ForegroundColor Gray
    }
}

# Dokumentation nach docs/ (außer README.md)
$mdFiles = Get-ChildItem -File -Filter "*.md" -ErrorAction SilentlyContinue | Where-Object { $_.Directory.Name -eq "Script" -and $_.Name -ne "README.md" }
foreach ($file in $mdFiles) {
    $destination = Join-Path "docs" $file.Name
    if (-not (Test-Path $destination)) {
        Move-Item -Path $file.FullName -Destination $destination -Force -ErrorAction SilentlyContinue
        Write-Host "  -> $($file.Name) -> docs/" -ForegroundColor Gray
    }
}

# Service-Dateien nach services/
$serviceFiles = Get-ChildItem -File -Filter "*.service" -ErrorAction SilentlyContinue | Where-Object { $_.Directory.Name -eq "Script" }
foreach ($file in $serviceFiles) {
    $destination = Join-Path "services" $file.Name
    if (-not (Test-Path $destination)) {
        Move-Item -Path $file.FullName -Destination $destination -Force -ErrorAction SilentlyContinue
        Write-Host "  -> $($file.Name) -> services/" -ForegroundColor Gray
    }
}

# Timer-Dateien nach timers/
$timerFiles = Get-ChildItem -File -Filter "*.timer" -ErrorAction SilentlyContinue | Where-Object { $_.Directory.Name -eq "Script" }
foreach ($file in $timerFiles) {
    $destination = Join-Path "timers" $file.Name
    if (-not (Test-Path $destination)) {
        Move-Item -Path $file.FullName -Destination $destination -Force -ErrorAction SilentlyContinue
        Write-Host "  -> $($file.Name) -> timers/" -ForegroundColor Gray
    }
}

# Konfigurationsdateien nach config/
$configPatterns = @("*.gs", "*.tsx", "*.ts", "*.xml")
foreach ($pattern in $configPatterns) {
    $files = Get-ChildItem -File -Filter $pattern -ErrorAction SilentlyContinue | Where-Object { $_.Directory.Name -eq "Script" }
    foreach ($file in $files) {
        $destination = Join-Path "config" $file.Name
        if (-not (Test-Path $destination)) {
            Move-Item -Path $file.FullName -Destination $destination -Force -ErrorAction SilentlyContinue
            Write-Host "  -> $($file.Name) -> config/" -ForegroundColor Gray
        }
    }
}

Write-Host ""
Write-Host "Fuege Aenderungen zu Git hinzu..." -ForegroundColor Yellow

# Git add fuer alle neuen/geaenderten Dateien
git add -A 2>&1 | Out-Null

# Zeige Status
$status = git status --short
if ($status) {
    Write-Host ""
    Write-Host "Geaenderte Dateien:" -ForegroundColor Cyan
    $status | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    if (($status | Measure-Object).Count -gt 20) {
        Write-Host "  ... und $(($status | Measure-Object).Count - 20) weitere" -ForegroundColor Gray
    }
    
    Write-Host ""
    $antwort = Read-Host "Commit erstellen und zu GitHub pushen? (j/n)"
    if ($antwort -eq "j" -or $antwort -eq "J" -or $antwort -eq "y" -or $antwort -eq "Y") {
        git commit -m "Repository: Restliche Dateien organisiert und synchronisiert" 2>&1 | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "OK Commit erstellt" -ForegroundColor Green
            Write-Host ""
            Write-Host "Pushe zu GitHub..." -ForegroundColor Yellow
            git push origin main 2>&1 | Out-Host
            if ($LASTEXITCODE -eq 0) {
                Write-Host ""
                Write-Host "OK Erfolgreich zu GitHub synchronisiert!" -ForegroundColor Green
            } else {
                Write-Host ""
                Write-Host "FEHLER beim Pushen. Bitte manuell pruefen." -ForegroundColor Red
            }
        } else {
            Write-Host ""
            Write-Host "FEHLER beim Commit. Bitte manuell pruefen." -ForegroundColor Red
        }
    } else {
        Write-Host ""
        Write-Host "Abgebrochen. Dateien wurden organisiert, aber nicht committed." -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "OK Keine Aenderungen gefunden - alles ist bereits synchronisiert!" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Fertig ===" -ForegroundColor Cyan
