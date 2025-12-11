#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Schiffsbilder Formatieren – Formatiert Schiffsnamen in Google Sheets fett, wenn Bild vorhanden
- Prüft welche Bilder im Ordner vorhanden sind
- Formatiert Schiffsnamen in Spalte A fett, wenn Bild existiert
"""

import os
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ============================================
# KONFIGURATION
# ============================================

# Google Sheets Einstellungen
GOOGLE_SPREADSHEET_ID = '1Q_Dvufm0LCUxYtktMtM18Xz30sXQxCnGfI9SSDFPUNw'
GOOGLE_SHEET_NAME = 'Schiffsdaten HHLA'
GOOGLE_NAME_COLUMN = 'A'      # Spalte mit Schiffsnamen
GOOGLE_NUMBER_COLUMN = 'C'    # Spalte mit Nummern
GOOGLE_START_ROW = 2          # Erste Datenzeile

# Bilder-Ordner
BILDER_ORDNER = '/root/Skrip/Datenbank/Schiffsbilder'

# Service Account Datei
if os.name == 'nt':  # Windows
    current_dir_file = os.path.join(os.path.dirname(__file__), "segelliste-83c2a17a5e89.json")
    documents_file = os.path.join(os.path.expanduser("~"), "Documents", "Scripts", "segelliste-83c2a17a5e89.json")
    SERVICE_ACCOUNT_FILE = current_dir_file if os.path.exists(current_dir_file) else documents_file
else:  # Linux
    SERVICE_ACCOUNT_FILE = "/root/Skrip/segelliste-83c2a17a5e89.json"

# Google Sheets API Scopes (mit Schreibrechten)
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def sanitize_filename(filename: str) -> str:
    """Bereinigt Dateinamen (wie in bilder_downloader.py)"""
    filename = filename.replace(' ', '_')
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    filename = filename.strip('. ')
    while '__' in filename:
        filename = filename.replace('__', '_')
    return filename


def get_existing_images() -> set:
    """Sammelt alle vorhandenen Bilddateinamen (ohne Erweiterung)"""
    bilder_set = set()
    bilder_path = Path(BILDER_ORDNER)
    
    if not bilder_path.exists():
        print(f"⚠️  Ordner nicht gefunden: {BILDER_ORDNER}")
        return bilder_set
    
    # Durchsuche alle Bilddateien
    bild_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    for file in bilder_path.iterdir():
        if file.is_file() and file.suffix.lower() in bild_extensions:
            # Entferne Erweiterung und normalisiere (Kleinschreibung, Unterstriche)
            name_without_ext = file.stem.lower().replace(' ', '_')
            bilder_set.add(name_without_ext)
    
    print(f"📁 {len(bilder_set)} Bilder im Ordner gefunden")
    return bilder_set


def col_to_index(col):
    """Konvertiert Spaltenbuchstaben zu Indizes (A=1, B=2, etc.)"""
    if isinstance(col, int):
        return col
    if isinstance(col, str):
        col = col.upper()
        if col.isdigit():
            return int(col)
        result = 0
        for char in col:
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result
    return col


def get_ship_data_from_sheets():
    """Liest Schiffsdaten aus Google Sheets"""
    try:
        print(f"📊 Verbinde mit Google Sheets...")
        
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=creds)
        
        # Lese Daten
        name_col_idx = col_to_index(GOOGLE_NAME_COLUMN)
        num_col_idx = col_to_index(GOOGLE_NUMBER_COLUMN)
        max_col = max(name_col_idx, num_col_idx)
        col_letter = chr(64 + max_col)
        range_name = f'{GOOGLE_SHEET_NAME}!A:{col_letter}'
        
        result = service.spreadsheets().values().get(
            spreadsheetId=GOOGLE_SPREADSHEET_ID,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        if not values:
            print("⚠️  Keine Daten gefunden")
            return []
        
        # Extrahiere Schiffsdaten
        ships = []
        for i, row in enumerate(values[GOOGLE_START_ROW - 1:], start=GOOGLE_START_ROW):
            while len(row) < max_col:
                row.append('')
            
            name = str(row[name_col_idx - 1]).strip() if len(row) >= name_col_idx else ''
            number = str(row[num_col_idx - 1]).strip() if len(row) >= num_col_idx else ''
            
            if name:  # Nur Zeilen mit Namen
                ships.append({
                    'row': i,
                    'name': name,
                    'number': number
                })
        
        print(f"✅ {len(ships)} Schiffe in Tabelle gefunden")
        return ships, service
        
    except Exception as e:
        print(f"❌ Fehler beim Lesen: {e}")
        import traceback
        traceback.print_exc()
        return [], None


def format_ship_names(service, ships, existing_images: set):
    """Formatiert Schiffsnamen fett, wenn Bild vorhanden"""
    try:
        print(f"\n🔍 Prüfe welche Schiffe Bilder haben...")
        
        # Finde Zeilen die formatiert werden sollen
        rows_to_format = []
        rows_to_unformat = []
        
        for ship in ships:
            name = ship['name']
            number = ship['number']
            row = ship['row']
            
            # Erstelle mögliche Dateinamen
            possible_names = []
            if name and number:
                possible_names.append(sanitize_filename(f"{name}_{number}").lower())
            if name:
                possible_names.append(sanitize_filename(name).lower())
            if number:
                possible_names.append(sanitize_filename(f"bild_{number}").lower())
            
            # Prüfe ob eines der möglichen Namen existiert
            has_image = any(name_variant in existing_images for name_variant in possible_names)
            
            if has_image:
                rows_to_format.append(row)
            else:
                rows_to_unformat.append(row)
        
        print(f"✅ {len(rows_to_format)} Schiffe mit Bildern gefunden")
        print(f"⏭️  {len(rows_to_unformat)} Schiffe ohne Bilder")
        
        # Formatiere Zeilen
        if rows_to_format:
            format_cells_bold(service, rows_to_format, True)
        
        if rows_to_unformat:
            format_cells_bold(service, rows_to_unformat, False)
        
        return len(rows_to_format)
        
    except Exception as e:
        print(f"❌ Fehler beim Formatieren: {e}")
        import traceback
        traceback.print_exc()
        return 0


def format_cells_bold(service, rows: list, bold: bool):
    """Formatiert Zellen in Spalte A fett oder normal"""
    if not rows:
        return
    
    try:
        # Hole Sheet-ID
        spreadsheet = service.spreadsheets().get(spreadsheetId=GOOGLE_SPREADSHEET_ID).execute()
        sheet_id = None
        for sheet in spreadsheet.get('sheets', []):
            if sheet['properties']['title'] == GOOGLE_SHEET_NAME:
                sheet_id = sheet['properties']['sheetId']
                break
        
        if sheet_id is None:
            print(f"❌ Blatt '{GOOGLE_SHEET_NAME}' nicht gefunden")
            return
        
        # Erstelle Requests für Batch-Update
        requests = []
        name_col_idx = col_to_index(GOOGLE_NAME_COLUMN) - 1  # 0-basiert
        
        for row in rows:
            requests.append({
                'repeatCell': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': row - 1,  # 0-basiert
                        'endRowIndex': row,
                        'startColumnIndex': name_col_idx,
                        'endColumnIndex': name_col_idx + 1,
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'textFormat': {
                                'bold': bold
                            }
                        }
                    },
                    'fields': 'userEnteredFormat.textFormat.bold'
                }
            })
        
        # Führe Batch-Update aus (in Batches von 100)
        batch_size = 100
        for i in range(0, len(requests), batch_size):
            batch = requests[i:i + batch_size]
            body = {'requests': batch}
            service.spreadsheets().batchUpdate(
                spreadsheetId=GOOGLE_SPREADSHEET_ID,
                body=body
            ).execute()
        
        status = "fett" if bold else "normal"
        print(f"✅ {len(rows)} Zeilen auf {status} formatiert")
        
    except Exception as e:
        print(f"❌ Fehler beim Formatieren: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("=" * 50)
    print("🚢 Schiffsbilder Formatieren")
    print("=" * 50)
    print(f"📁 Bilder-Ordner: {BILDER_ORDNER}")
    print(f"📊 Tabelle: {GOOGLE_SPREADSHEET_ID}")
    print(f"📋 Blatt: {GOOGLE_SHEET_NAME}")
    print("=" * 50)
    
    # Sammle vorhandene Bilder
    existing_images = get_existing_images()
    
    if not existing_images:
        print("\n⚠️  Keine Bilder gefunden. Beende.")
        return
    
    # Lese Schiffsdaten
    ships, service = get_ship_data_from_sheets()
    
    if not ships or not service:
        print("\n❌ Konnte keine Daten lesen. Beende.")
        return
    
    # Formatiere Schiffsnamen
    formatted_count = format_ship_names(service, ships, existing_images)
    
    print(f"\n{'='*50}")
    print(f"✅ Fertig! {formatted_count} Schiffsnamen fett formatiert")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()

