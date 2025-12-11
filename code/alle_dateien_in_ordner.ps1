# PowerShell-Script: Verschiebt alle Dateien in einen einzigen Ordner

Write-Host "=== Verschiebe alle Dateien in einen Ordner ===" -ForegroundColor Cyan
Write-Host ""

$targetFolder = "code"

# Erstelle Zielordner falls nicht vorhanden
if (-not (Test-Path $targetFolder)) {
    New-Item -ItemType Directory -Path $targetFolder -Force | Out-Null
    Write-Host "OK Ordner erstellt: $targetFolder" -ForegroundColor Green
}

# Dateien die NICHT verschoben werden sollen
$excludeFiles = @("README.md", ".gitignore", "requirements.txt", "alle_dateien_in_ordner.ps1")

Write-Host ""
Write-Host "Verschiebe Dateien nach $targetFolder/..." -ForegroundColor Yellow

# Verschiebe alle Dateien (außer ausgeschlossene)
$files = Get-ChildItem -File | Where-Object { $excludeFiles -notcontains $_.Name }
$count = 0

foreach ($file in $files) {
    $destination = Join-Path $targetFolder $file.Name
    if (-not (Test-Path $destination)) {
        Move-Item -Path $file.FullName -Destination $destination -Force -ErrorAction SilentlyContinue
        Write-Host "  -> $($file.Name)" -ForegroundColor Gray
        $count++
    }
}

# Verschiebe alle Unterordner (außer .git und Zielordner)
$folders = Get-ChildItem -Directory | Where-Object { $_.Name -ne ".git" -and $_.Name -ne $targetFolder }
foreach ($folder in $folders) {
    $destination = Join-Path $targetFolder $folder.Name
    if (-not (Test-Path $destination)) {
        Move-Item -Path $folder.FullName -Destination $destination -Force -ErrorAction SilentlyContinue
        Write-Host "  -> $($folder.Name)/" -ForegroundColor Gray
        $count++
    }
}

Write-Host ""
Write-Host "OK $count Dateien/Ordner verschoben" -ForegroundColor Green

# Git Status prüfen
Write-Host ""
Write-Host "Fuege Aenderungen zu Git hinzu..." -ForegroundColor Yellow
git add -A 2>&1 | Out-Null

$status = git status --short
if ($status) {
    Write-Host ""
    Write-Host "Geaenderte Dateien:" -ForegroundColor Cyan
    $status | Select-Object -First 30 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
    
    Write-Host ""
    $antwort = Read-Host "Commit erstellen und zu GitHub pushen? (j/n)"
    if ($antwort -eq "j" -or $antwort -eq "J" -or $antwort -eq "y" -or $antwort -eq "Y") {
        git commit -m "Repository: Alle Dateien in '$targetFolder' Ordner verschoben" 2>&1 | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "OK Commit erstellt" -ForegroundColor Green
            Write-Host ""
            Write-Host "Pushe zu GitHub..." -ForegroundColor Yellow
            git push origin main 2>&1 | Out-Host
            if ($LASTEXITCODE -eq 0) {
                Write-Host ""
                Write-Host "OK Erfolgreich synchronisiert!" -ForegroundColor Green
            }
        }
    }
} else {
    Write-Host ""
    Write-Host "OK Keine Aenderungen" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Fertig ===" -ForegroundColor Cyan

