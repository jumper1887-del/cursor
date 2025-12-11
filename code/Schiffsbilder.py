#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Schiffsbilder – Lädt Schiffsbilder von shipfinder.com
- Liest MMSI-Nummern aus Google Sheets "Schiffsdaten HHLA" Spalte C
- Ruft für jedes Schiff die shipfinder.com Seite auf
- Extrahiert das Bild mit id="pic1" aus der HTML
- Schreibt die Bild-URL in Spalte K
"""

import re
import time
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import os

# Selenium für JavaScript-rendered Content
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("WARNUNG: Selenium nicht verfügbar. Installiere mit: pip install selenium webdriver-manager")

# Google Sheets API Scopes
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Spreadsheet ID
SPREADSHEET_ID = '1Q_Dvufm0LCUxYtktMtM18Xz30sXQxCnGfI9SSDFPUNw'
SHEET_NAME = 'Schiffsdaten HHLA'

# Service Account Datei - wie in Schiffs_Datenbank.py
if os.name == 'nt':  # Windows
    # Versuche zuerst im aktuellen Verzeichnis, dann im Documents/Scripts Ordner
    current_dir_file = os.path.join(os.path.dirname(__file__), "segelliste-83c2a17a5e89.json")
    documents_file = os.path.join(os.path.expanduser("~"), "Documents", "Scripts", "segelliste-83c2a17a5e89.json")
    if os.path.exists(current_dir_file):
        SERVICE_ACCOUNT_FILE = current_dir_file
    else:
        SERVICE_ACCOUNT_FILE = documents_file
else:  # Linux
    SERVICE_ACCOUNT_FILE = "/root/Skrip/segelliste-83c2a17a5e89.json"

# Maximale Anzahl Schiffe pro Batch (0 = alle Schiffe)
# Wird verwendet um Website nicht zu überlasten
MAX_SHIPS = 0  # 0 bedeutet alle Schiffe verarbeiten

def get_credentials():
    """Holt Google API Credentials vom Service Account"""
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(
            f"Service Account Datei nicht gefunden: {SERVICE_ACCOUNT_FILE}\n"
            f"Bitte stelle sicher, dass die Datei existiert."
        )
    
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    
    return creds

def get_sheet_data(service, spreadsheet_id, sheet_name):
    """Liest alle Daten aus dem Sheet"""
    range_name = f'{sheet_name}!A:K'
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name
    ).execute()
    return result.get('values', [])

def update_cell(service, spreadsheet_id, sheet_name, row, col, value):
    """Aktualisiert eine Zelle im Sheet"""
    range_name = f'{sheet_name}!{chr(64 + col)}{row}'
    body = {
        'values': [[value]]
    }
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body=body
    ).execute()

def extract_image_url(mmsi):
    """Extrahiert die Bild-URL von shipfinder.com mit Selenium (für JavaScript-rendered Content)"""
    if not SELENIUM_AVAILABLE:
        print("    FEHLER: Selenium nicht verfügbar. Installiere mit: pip install selenium webdriver-manager")
        return None
    
    url = f'https://www.shipfinder.com/Ship/Detail?mmsi={mmsi}'
    
    # Chrome Options für Headless-Browser
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--log-level=3")  # Reduziere Logging
    
    driver = None
    try:
        # ChromeDriver starten - lade immer neueste Version
        # Lösche Cache zuerst, um sicherzustellen, dass neueste Version geladen wird
        try:
            import shutil
            cache_path = os.path.join(os.path.expanduser("~"), ".wdm")
            if os.path.exists(cache_path):
                try:
                    shutil.rmtree(cache_path)
                    print(f"    ChromeDriver-Cache gelöscht, lade neueste Version...")
                except:
                    pass
        except:
            pass
        
        # Installiere ChromeDriver mit neuester Version
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        
        # Lade-Seite mit Fortschrittsanzeige
        import threading
        
        loading_done = threading.Event()
        loading_phase = {"phase": "start", "ready_state": "loading"}
        
        def loading_indicator():
            phases = {
                "start": "🌐 Verbinde mit Server",
                "loading": "📥 Lade Seite",
                "interactive": "⚙️  Lade Ressourcen",
                "complete": "✅ Seite geladen"
            }
            dots = 0
            while not loading_done.is_set():
                phase = loading_phase.get("phase", "start")
                ready_state = loading_phase.get("ready_state", "loading")
                
                # Bestimme Phase basierend auf readyState
                if ready_state == "loading":
                    display_phase = phases["loading"]
                elif ready_state == "interactive":
                    display_phase = phases["interactive"]
                elif ready_state == "complete":
                    display_phase = phases["complete"]
                else:
                    display_phase = phases.get(phase, phases["start"])
                
                dots_str = "." * (dots % 4)
                print(f"\r    {display_phase}{dots_str}   ", end='', flush=True)
                dots += 1
                time.sleep(0.3)
        
        # Starte Ladeindikator
        indicator_thread = threading.Thread(target=loading_indicator, daemon=True)
        indicator_thread.start()
        
        try:
            # Starte Seitenladevorgang
            driver.get(url)
            
            # Überwache readyState während des Ladens
            max_wait = 20
            waited = 0
            while waited < max_wait:
                try:
                    ready_state = driver.execute_script("return document.readyState")
                    loading_phase["ready_state"] = ready_state
                    
                    if ready_state == "complete":
                        loading_phase["phase"] = "complete"
                        break
                    elif ready_state == "interactive":
                        loading_phase["phase"] = "interactive"
                    
                    time.sleep(0.2)
                    waited += 0.2
                except:
                    break
            
            # Warte explizit auf vollständiges Laden
            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            loading_phase["ready_state"] = "complete"
            loading_phase["phase"] = "complete"
            time.sleep(0.5)  # Kurze Pause für Anzeige
            
        finally:
            loading_done.set()
            indicator_thread.join(timeout=1)
        
        # Suche nach Bild-Element
        print(f"\r    🔍 Suche Bild-Element...                    ", end='', flush=True)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "pic1"))
            )
            print(f"\r    ✅ Bild-Element gefunden!                    ")
        except TimeoutException:
            print(f"\r    ⚠️  Bild-Element nicht gefunden, versuche trotzdem...                    ")
        
        # Zusätzliche Wartezeit für JavaScript-Rendering
        print(f"    ⚙️  Warte 3 Sekunden für JavaScript-Rendering...", end='', flush=True)
        for wait in range(3, 0, -1):
            print(f"\r    ⚙️  Warte {wait} Sekunden für JavaScript-Rendering...", end='', flush=True)
            time.sleep(1)
        print("\r    ✅ JavaScript-Rendering abgeschlossen.                    ")
        
        # HTML nach dem JavaScript-Rendering abrufen
        html = driver.page_source
        
        # Verschiedene Patterns versuchen
        # Pattern 1: Exaktes Format - <img src="URL" ... id="pic1" ...>
        img_pattern = r'<img\s+src\s*=\s*["\']([^"\']*picture\.shipxy\.com[^"\']+)["\'][^>]*id\s*=\s*["\']pic1["\'][^>]*>'
        match = re.search(img_pattern, html, re.IGNORECASE)
        
        # Pattern 2: <img ... id="pic1" ... src="URL" ...>
        if not match:
            img_pattern = r'<img[^>]*id\s*=\s*["\']pic1["\'][^>]*src\s*=\s*["\']([^"\']*picture\.shipxy\.com[^"\']+)["\'][^>]*>'
            match = re.search(img_pattern, html, re.IGNORECASE)
        
        # Pattern 3: Versuche direkt das Element zu finden
        if not match:
            try:
                img_element = driver.find_element(By.ID, "pic1")
                image_url = img_element.get_attribute("src")
                if image_url and 'picture.shipxy.com' in image_url:
                    return image_url
            except NoSuchElementException:
                pass
        
        # Pattern 4: Suche nach allen picture.shipxy.com URLs
        if not match:
            img_pattern = r'src\s*=\s*["\']([^"\']*picture\.shipxy\.com[^"\']+)["\']'
            match = re.search(img_pattern, html, re.IGNORECASE)
        
        if match and match.group(1):
            return match.group(1)
        
        return None
        
    except Exception as e:
        print(f"    Fehler beim Abrufen der Seite: {e}")
        return None
    finally:
        if driver:
            driver.quit()

def process_ships_batch(service, running_flag=None):
    """Verarbeitet einen Batch von Schiffen (max. MAX_SHIPS)"""
    # Daten aus Sheet lesen
    data = get_sheet_data(service, SPREADSHEET_ID, SHEET_NAME)
    
    if not data:
        print("Keine Daten gefunden!")
        return 0, 0, 0
    
    processed = 0
    skipped = 0
    errors = 0
    with_images = 0
    without_images = 0
    
    # Zähle zuerst alle zu verarbeitenden Schiffe
    total_to_process = 0
    for i in range(1, len(data)):
        row = data[i]
        while len(row) < 11:
            row.append('')
        
        mmsi = row[2] if len(row) > 2 else ''
        existing_image = row[10] if len(row) > 10 else ''
        
        if mmsi and str(mmsi).strip():
            existing_str = str(existing_image).strip() if existing_image else ''
            # Zähle nur Schiffe die noch verarbeitet werden müssen
            if not existing_str or (not existing_str.startswith('http') and 'Keine Bild' not in existing_str):
                total_to_process += 1
    
    print(f"\n📊 Statistiken:")
    print(f"   Gesamt zu verarbeiten: {total_to_process} Schiffe")
    print(f"{'='*50}\n")
    
    # Header überspringen (Zeile 0)
    for i in range(1, len(data)):
        # Prüfe ob Skript beendet werden soll (Strg+C)
        if running_flag is not None and not running_flag():
            print("\n=== Verarbeitung abgebrochen ===")
            break
            
        # Stoppe wenn bereits MAX_SHIPS Schiffe verarbeitet wurden (nur wenn MAX_SHIPS > 0)
        if MAX_SHIPS > 0 and processed >= MAX_SHIPS:
            break
        
        # Stelle sicher, dass genug Spalten vorhanden sind
        row = data[i]
        while len(row) < 11:
            row.append('')
        
        ship_name = row[0] if len(row) > 0 else ''  # Spalte A
        mmsi = row[2] if len(row) > 2 else ''  # Spalte C
        
        # Überspringe Zeilen ohne MMSI-Nummer
        if not mmsi or str(mmsi).strip() == '':
            continue
        
        # Überspringe wenn bereits ein Bild oder "Keine Bild" vorhanden ist
        existing_image = row[10] if len(row) > 10 else ''  # Spalte K
        if existing_image and str(existing_image).strip() != '':
            existing_str = str(existing_image).strip()
            # Überspringe wenn es eine URL ist (beginnt mit http/https) oder "Keine Bild" enthält
            if existing_str.startswith('http') or existing_str.startswith('https'):
                skipped += 1
                continue
            elif 'Keine Bild' in existing_str:
                # Überspringe Schiffe mit "Keine Bild" - werden nicht mehr durchsucht
                skipped += 1
                continue
        
        mmsi_number = str(mmsi).strip()
        current_index = processed + skipped + errors + 1
        remaining = total_to_process - (current_index - 1)
        
        print(f"\n🚢 [{current_index}/{total_to_process}] Verarbeite: {ship_name}")
        print(f"   MMSI: {mmsi_number}")
        print(f"   📊 Status: {with_images} mit Bild, {without_images} ohne Bild, {remaining} verbleibend")
        
        image_url = extract_image_url(mmsi_number)
        
        if image_url:
            print(f"   ✅ Bild gefunden!")
            print(f"   📷 URL: {image_url}")
            try:
                update_cell(service, SPREADSHEET_ID, SHEET_NAME, i + 1, 11, image_url)
                processed += 1
                with_images += 1
                # Pause um Server nicht zu überlasten
                print(f"  Warte 3 Sekunden...", end='', flush=True)
                for wait in range(3, 0, -1):
                    print(f"\r  Warte {wait} Sekunden...", end='', flush=True)
                print("\r  Weiter...                                    ")
            except Exception as e:
                print(f"  Fehler beim Schreiben: {e}")
                errors += 1
        else:
            print(f"   ❌ Kein Bild gefunden")
            # Schreibe "Keine Bild [Schiffsname] [MMSI]" in Spalte K
            try:
                ship_name_clean = str(ship_name).strip() if ship_name else "Unbekannt"
                mmsi_clean = str(mmsi_number).strip() if mmsi_number else ""
                keine_bild_text = f"Keine Bild {ship_name_clean} {mmsi_clean}".strip()
                update_cell(service, SPREADSHEET_ID, SHEET_NAME, i + 1, 11, keine_bild_text)
                print(f"   📝 Geschrieben in Spalte K: {keine_bild_text}")
                processed += 1  # Zähle als verarbeitet, nicht als Fehler
                without_images += 1
            except Exception as e:
                print(f"  Fehler beim Schreiben: {e}")
                errors += 1
    
    return processed, skipped, errors, with_images, without_images

def main():
    import signal
    import sys
    
    # Flag für sauberes Beenden (als Liste für Referenz)
    running = [True]
    
    def signal_handler(sig, frame):
        print("\n\n=== Beende Skript... ===")
        running[0] = False
        # Versuche auch alle offenen Browser zu schließen
        try:
            import gc
            for obj in gc.get_objects():
                if hasattr(obj, 'quit') and 'webdriver' in str(type(obj)):
                    try:
                        obj.quit()
                    except:
                        pass
        except:
            pass
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Lambda-Funktion für running-Flag
    def is_running():
        return running[0]
    
    print("=== Schiffsbilder Downloader ===\n")
    
    # Prüfe ob Spreadsheet ID gesetzt ist
    if SPREADSHEET_ID == 'DEINE_SPREADSHEET_ID_HIER':
        print("FEHLER: Bitte setze SPREADSHEET_ID in der Datei!")
        print("Die Spreadsheet ID findest du in der URL:")
        print("https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HIER/edit")
        return
    
    # Google Sheets API initialisieren
    print("Verbinde mit Google Sheets...")
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)
    
    total_processed = 0
    total_skipped = 0
    total_errors = 0
    batch_count = 0
    
    if MAX_SHIPS > 0:
        print(f"Starte kontinuierliche Verarbeitung (max. {MAX_SHIPS} Schiffe pro Batch)...\n")
    else:
        print(f"Starte Verarbeitung aller Schiffe...\n")
    
    # Hauptschleife - läuft bis alle Schiffe verarbeitet sind oder gestoppt wird
    while running[0]:
        batch_count += 1
        print(f"\n{'='*50}")
        print(f"Batch {batch_count} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}\n")
        
        result = process_ships_batch(service, is_running)
        processed, skipped, errors, with_images, without_images = result
        
        total_processed += processed
        total_skipped += skipped
        total_errors += errors
        total_with_images += with_images
        total_without_images += without_images
        
        print(f"\n{'─'*50}")
        print(f"📊 Batch {batch_count} Zusammenfassung")
        print(f"{'─'*50}")
        print(f"✅ Verarbeitet: {processed} Schiffe")
        print(f"   📷 Mit Bild: {with_images} Schiffe")
        print(f"   ❌ Ohne Bild: {without_images} Schiffe")
        print(f"⏭️  Übersprungen: {skipped} Schiffe (bereits vorhanden)")
        print(f"❌ Fehler: {errors} Schiffe")
        print(f"{'─'*50}")
        
        # Wenn MAX_SHIPS > 0 und weniger als MAX_SHIPS verarbeitet wurden, sind alle fertig
        # Wenn MAX_SHIPS = 0, dann wurde alles in einem Batch verarbeitet
        if MAX_SHIPS > 0 and processed < MAX_SHIPS:
            print(f"\n✅ Alle Schiffe verarbeitet!")
            break
        elif MAX_SHIPS == 0:
            # Bei MAX_SHIPS = 0 wird alles in einem Batch gemacht
            print(f"\n✅ Alle Schiffe verarbeitet!")
            break
        
        if not running[0]:
            break
        
        # Pause zwischen Batches
        print(f"\n⏱️  Warte 10 Sekunden vor nächstem Batch...")
        for wait in range(10, 0, -1):
            if not running[0]:
                break
            print(f"\r⏱️  Nächster Batch in {wait} Sekunden...", end='', flush=True)
            time.sleep(1)
        if running[0]:
            print("\r⏱️  Starte nächsten Batch...                    ")
    
    print(f"\n{'='*50}")
    print(f"🎯 FINALE ZUSAMMENFASSUNG")
    print(f"{'='*50}")
    print(f"📦 Batches verarbeitet: {batch_count}")
    print(f"✅ Gesamt verarbeitet: {total_processed} Schiffe")
    print(f"   📷 Mit Bild: {total_with_images} Schiffe")
    print(f"   ❌ Ohne Bild: {total_without_images} Schiffe")
    print(f"⏭️  Gesamt übersprungen: {total_skipped} Schiffe")
    print(f"❌ Gesamt Fehler: {total_errors} Schiffe")
    print(f"{'='*50}")

if __name__ == '__main__':
    main()
