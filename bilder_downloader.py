#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bilder Downloader – Lädt Bilder von URLs herunter, passt Größe an und benennt sie um
- Liest Bild-URLs aus einer Liste, Datei oder Google Sheets
- Lädt Bilder herunter
- Passt die Größe an (optional)
- Benennt Bilder um (optional)
- Speichert in einem Zielordner
"""

import os
import sys
import requests
from pathlib import Path
from PIL import Image
import hashlib
from urllib.parse import urlparse
import argparse
from typing import List, Optional, Tuple

# Google Sheets API Support
try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False

# ============================================
# KONFIGURATION - Hier kannst du alles anpassen
# ============================================

# Ordner für Bilder
BASE_OUTPUT_DIR = "/root/Skrip/Datenbank/Schiffsbilder"
DEFAULT_OUTPUT_DIR = "downloads"

# Bild-Einstellungen
DEFAULT_MAX_WIDTH = 1024  # Maximale Breite (nur verkleinern wenn größer)
DEFAULT_QUALITY = 85

# Google Sheets Einstellungen
GOOGLE_SPREADSHEET_ID = '1Q_Dvufm0LCUxYtktMtM18Xz30sXQxCnGfI9SSDFPUNw'
GOOGLE_SHEET_NAME = 'Schiffsdaten HHLA'
GOOGLE_NAME_COLUMN = 'A'      # Spalte mit Schiffsnamen
GOOGLE_NUMBER_COLUMN = 'C'    # Spalte mit Nummern
GOOGLE_URL_COLUMN = 'K'       # Spalte mit Bild-URLs
GOOGLE_START_ROW = 2          # Erste Datenzeile (Zeile 1 = Header)

# Service Account Datei
if os.name == 'nt':  # Windows
    current_dir_file = os.path.join(os.path.dirname(__file__), "segelliste-83c2a17a5e89.json")
    documents_file = os.path.join(os.path.expanduser("~"), "Documents", "Scripts", "segelliste-83c2a17a5e89.json")
    SERVICE_ACCOUNT_FILE = current_dir_file if os.path.exists(current_dir_file) else documents_file
else:  # Linux
    SERVICE_ACCOUNT_FILE = "/root/Skrip/segelliste-83c2a17a5e89.json"

# Google Sheets API (mit Schreibrechten für Formatierung)
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """Bereinigt einen Dateinamen von ungültigen Zeichen"""
    # Ersetze Leerzeichen durch Unterstriche
    filename = filename.replace(' ', '_')
    
    # Entferne ungültige Zeichen für Windows/Linux
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Entferne führende/trailing Punkte und Leerzeichen
    filename = filename.strip('. ')
    
    # Entferne mehrfache Unterstriche
    while '__' in filename:
        filename = filename.replace('__', '_')
    
    # Begrenze Länge
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[:max_length - len(ext)] + ext
    
    return filename if filename else "image"


def get_filename_from_url(url: str, custom_name: Optional[str] = None) -> str:
    """Extrahiert oder generiert einen Dateinamen aus der URL"""
    if custom_name:
        # Wenn custom_name bereits eine Erweiterung hat, behalte sie
        if '.' in custom_name:
            return sanitize_filename(custom_name)
        # Sonst füge .jpg hinzu
        return sanitize_filename(custom_name) + '.jpg'
    
    # Versuche Dateinamen aus URL zu extrahieren
    parsed = urlparse(url)
    path = parsed.path
    
    # Extrahiere Dateinamen aus Pfad
    filename = os.path.basename(path)
    
    # Wenn kein Dateiname gefunden, versuche aus Query-Parametern oder generiere einen
    if not filename or '.' not in filename:
        # Prüfe ob URL eine bekannte Erweiterung in Query-Parametern hat
        if '.webp' in url.lower() or url.endswith('.webp'):
            filename = f"image_{hashlib.md5(url.encode()).hexdigest()[:8]}.webp"
        elif '.jpg' in url.lower() or '.jpeg' in url.lower():
            filename = f"image_{hashlib.md5(url.encode()).hexdigest()[:8]}.jpg"
        elif '.png' in url.lower():
            filename = f"image_{hashlib.md5(url.encode()).hexdigest()[:8]}.png"
        else:
            # Erstelle Hash aus URL für eindeutigen Namen
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            # Standard: .jpg
            filename = f"image_{url_hash}.jpg"
    
    return sanitize_filename(filename)


def download_image(url: str, timeout: int = 30) -> Optional[bytes]:
    """Lädt ein Bild von einer URL herunter - unterstützt marinetraffic.com und vesselfinder.net"""
    try:
        # Erweiterte Headers für bessere Kompatibilität
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.vesselfinder.com/' if 'vesselfinder' in url else 'https://www.marinetraffic.com/',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site'
        }
        
        # Spezielle Behandlung für bestimmte Domains
        if 'marinetraffic.com' in url or 'vesselfinder.net' in url:
            # Für diese Domains: Erlaube auch nicht-image Content-Types (manchmal liefern sie Bilder mit falschem Content-Type)
            response = requests.get(url, headers=headers, timeout=timeout, stream=True, allow_redirects=True)
            response.raise_for_status()
            
            # Prüfe Content-Type, aber akzeptiere auch wenn nicht explizit image/*
            content_type = response.headers.get('content-type', '').lower()
            if content_type and not content_type.startswith('image/'):
                # Prüfe ob es trotzdem ein Bild sein könnte (anhand der ersten Bytes)
                content_preview = response.content[:20]
                # JPEG, PNG, GIF, WEBP Magic Bytes
                is_image = (
                    content_preview.startswith(b'\xff\xd8\xff') or  # JPEG
                    content_preview.startswith(b'\x89PNG\r\n\x1a\n') or  # PNG
                    content_preview.startswith(b'GIF89a') or  # GIF
                    content_preview.startswith(b'GIF87a') or  # GIF
                    content_preview.startswith(b'RIFF') and b'WEBP' in content_preview[:12] or  # WEBP
                    url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'))
                )
                if not is_image:
                    print(f"  ⚠️  Warnung: Content-Type ist '{content_type}', aber URL sieht nach Bild aus")
        else:
            # Normale Prüfung für andere URLs
            response = requests.get(url, headers=headers, timeout=timeout, stream=True, allow_redirects=True)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '').lower()
            if content_type and not content_type.startswith('image/'):
                print(f"  ⚠️  Warnung: Content-Type ist '{content_type}', nicht 'image/*'")
        
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Fehler beim Herunterladen: {e}")
        return None


def resize_image(image_data: bytes, max_width: int, max_height: Optional[int] = None, quality: int = 85) -> Optional[bytes]:
    """Passt die Größe eines Bildes an - begrenzt nur die Breite, Höhe bleibt proportional"""
    try:
        from io import BytesIO
        
        # Öffne Bild aus Bytes
        img = Image.open(BytesIO(image_data))
        original_format = img.format
        
        # Konvertiere zu RGB falls nötig (für JPEG), aber behalte WEBP/PNG mit Alpha-Kanal wenn möglich
        if original_format == 'WEBP' and img.mode in ('RGBA', 'LA'):
            # WEBP mit Alpha-Kanal behalten
            pass  # Behalte RGBA für WEBP
        elif original_format == 'PNG' and img.mode in ('RGBA', 'LA'):
            # PNG mit Alpha-Kanal behalten
            pass  # Behalte RGBA für PNG
        elif img.mode in ('RGBA', 'LA', 'P'):
            # Für andere Formate: Erstelle weißes Hintergrundbild für transparente Bilder
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = rgb_img
        elif img.mode != 'RGB' and original_format not in ('WEBP', 'PNG'):
            img = img.convert('RGB')
        
        # Berechne neue Größe
        original_width, original_height = img.size
        
        # Nur verkleinern wenn größer als max_width, nie vergrößern
        if original_width <= max_width:
            # Bild ist bereits klein genug - keine Anpassung nötig
            print(f"  📏 Größe: {original_width}x{original_height} (bereits ≤ {max_width}px, keine Anpassung)")
            return None  # Keine Änderung nötig, verwende Original
        else:
            # Bild ist größer - verkleinern
            # Berechne Skalierungsfaktor basierend nur auf Breite
            ratio = max_width / original_width
            
            new_width = int(original_width * ratio)
            new_height = int(original_height * ratio)
            
            # Resize mit hoher Qualität
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            print(f"  📏 Größe verkleinert: {original_width}x{original_height} → {new_width}x{new_height} (Höhe proportional)")
        
        # Speichere in Bytes
        output = BytesIO()
        # Unterstütze JPEG, PNG, WEBP
        if original_format in ('JPEG', 'PNG', 'WEBP'):
            save_format = original_format
        else:
            save_format = 'JPEG'
        
        # Speichere mit entsprechenden Optionen
        if save_format == 'WEBP':
            # WEBP kann RGBA haben
            if img.mode == 'RGBA':
                img.save(output, format='WEBP', quality=quality, method=6)
            else:
                img.save(output, format='WEBP', quality=quality, method=6)
        elif save_format == 'PNG':
            # PNG kann RGBA haben
            if img.mode == 'RGBA':
                img.save(output, format='PNG', optimize=True)
            else:
                img.save(output, format='PNG', optimize=True)
        else:  # JPEG
            # JPEG braucht RGB
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(output, format='JPEG', quality=quality, optimize=True)
        
        return output.getvalue()
        
    except Exception as e:
        print(f"  ❌ Fehler beim Größenanpassen: {e}")
        return None


def process_image(
    url: str,
    output_dir: str,
    max_width: int = DEFAULT_MAX_WIDTH,
    max_height: Optional[int] = None,
    quality: int = DEFAULT_QUALITY,
    custom_name: Optional[str] = None,
    resize: bool = True
) -> Tuple[bool, str]:
    """
    Verarbeitet ein einzelnes Bild: Download, Größenanpassung, Speicherung
    
    Returns:
        (success: bool, filepath: str)
    """
    # Ausgabeordner
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Lade Bild
    image_data = download_image(url)
    if not image_data:
        return False, ""
    
    # Größe anpassen
    if resize:
        resized_data = resize_image(image_data, max_width, max_height, quality)
        if resized_data:
            image_data = resized_data
    
    # Dateiname
    filename = get_filename_from_url(url, custom_name)
    if '.' not in filename:
        filename += '.jpg'
    
    # Bereinige Dateinamen (Leerzeichen zu Unterstrichen)
    filename = sanitize_filename(filename)
    
    # Prüfe ob Datei bereits existiert
    filepath = output_path / filename
    if filepath.exists():
        print(f"⏭️  Übersprungen (bereits vorhanden): {filename}")
        return True, str(filepath)  # Erfolg, aber nicht neu gespeichert
    
    try:
        with open(filepath, 'wb') as f:
            f.write(image_data)
        print(f"✅ {filename}")
        return True, str(filepath)
    except Exception as e:
        print(f"❌ Fehler: {e}")
        return False, ""


def col_to_index_for_formatting(col):
    """Konvertiert Spaltenbuchstaben zu Indizes für Formatierung"""
    return col_to_index(col)

def format_ship_names_in_sheets():
    """Formatiert Schiffsnamen in Spalte A fett, wenn Bild vorhanden"""
    try:
        from pathlib import Path
        
        # Sammle vorhandene Bilder
        bilder_path = Path(BASE_OUTPUT_DIR)
        if not bilder_path.exists():
            print("⚠️  Bilder-Ordner nicht gefunden")
            return
        
        bild_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        existing_images = set()
        for file in bilder_path.iterdir():
            if file.is_file() and file.suffix.lower() in bild_extensions:
                name_without_ext = file.stem.lower().replace(' ', '_')
                existing_images.add(name_without_ext)
        
        if not existing_images:
            print("⚠️  Keine Bilder gefunden")
            return
        
        print(f"📁 {len(existing_images)} Bilder im Ordner gefunden")
        
        # Verbinde mit Google Sheets
        creds = get_google_sheets_credentials()
        service = build('sheets', 'v4', credentials=creds)
        
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
        
        # Lese Schiffsdaten
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
            return
        
        # Finde Zeilen die formatiert werden sollen
        rows_to_format = []
        rows_to_unformat = []
        
        for i, row in enumerate(values[GOOGLE_START_ROW - 1:], start=GOOGLE_START_ROW):
            while len(row) < max_col:
                row.append('')
            
            name = str(row[name_col_idx - 1]).strip() if len(row) >= name_col_idx else ''
            number = str(row[num_col_idx - 1]).strip() if len(row) >= num_col_idx else ''
            
            if name:
                # Erstelle mögliche Dateinamen
                possible_names = []
                if name and number:
                    possible_names.append(sanitize_filename(f"{name}-{number}").lower())
                if name:
                    possible_names.append(sanitize_filename(name).lower())
                if number:
                    possible_names.append(sanitize_filename(f"bild-{number}").lower())
                
                # Prüfe ob Bild existiert
                has_image = any(name_variant in existing_images for name_variant in possible_names)
                
                if has_image:
                    rows_to_format.append(i)
                else:
                    rows_to_unformat.append(i)
        
        print(f"✅ {len(rows_to_format)} Schiffe mit Bildern gefunden")
        
        # Formatiere Zeilen
        if rows_to_format:
            format_cells_bold(service, sheet_id, rows_to_format, True)
        
        if rows_to_unformat:
            format_cells_bold(service, sheet_id, rows_to_unformat, False)
        
        print(f"✅ Formatierung abgeschlossen")
        
    except Exception as e:
        print(f"⚠️  Fehler beim Formatieren: {e}")
        # Nicht kritisch, nur Warnung


def format_cells_bold(service, sheet_id: int, rows: list, bold: bool):
    """Formatiert Zellen in Spalte A fett oder normal"""
    if not rows:
        return
    
    try:
        requests = []
        name_col_idx = col_to_index(GOOGLE_NAME_COLUMN) - 1  # 0-basiert
        
        for row in rows:
            requests.append({
                'repeatCell': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': row - 1,
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
        
        # Batch-Update in Chunks von 100
        batch_size = 100
        for i in range(0, len(requests), batch_size):
            batch = requests[i:i + batch_size]
            body = {'requests': batch}
            service.spreadsheets().batchUpdate(
                spreadsheetId=GOOGLE_SPREADSHEET_ID,
                body=body
            ).execute()
        
    except Exception as e:
        print(f"⚠️  Fehler beim Formatieren: {e}")


def read_urls_from_file(filepath: str) -> List[str]:
    """Liest URLs aus einer Textdatei (eine URL pro Zeile)"""
    urls = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):  # Ignoriere leere Zeilen und Kommentare
                    urls.append(line)
    except Exception as e:
        print(f"❌ Fehler beim Lesen der Datei: {e}")
    return urls


def get_google_sheets_credentials():
    """Holt Google API Credentials vom Service Account"""
    if not GOOGLE_SHEETS_AVAILABLE:
        raise ImportError("Google Sheets API nicht verfügbar. Installiere: pip install google-auth google-api-python-client")
    
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(f"Service Account Datei nicht gefunden: {SERVICE_ACCOUNT_FILE}")
    
    return Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)


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

def read_urls_from_google_sheets() -> List[Tuple[str, str]]:
    """Liest Namen, Nummern und URLs aus Google Sheets - verwendet Konfiguration oben"""
    if not GOOGLE_SHEETS_AVAILABLE:
        print("❌ Google Sheets API nicht verfügbar. Installiere: pip install google-auth google-api-python-client")
        return []
    
    try:
        print(f"📊 Verbinde mit Google Sheets...")
        print(f"   Tabelle: {GOOGLE_SPREADSHEET_ID}")
        print(f"   Blatt: {GOOGLE_SHEET_NAME}")
        
        # Konvertiere Spalten zu Indizes
        name_col_idx = col_to_index(GOOGLE_NAME_COLUMN)
        url_col_idx = col_to_index(GOOGLE_URL_COLUMN)
        num_col_idx = col_to_index(GOOGLE_NUMBER_COLUMN)
        
        # Verbinde mit Google Sheets
        creds = get_google_sheets_credentials()
        service = build('sheets', 'v4', credentials=creds)
        
        # Lese Daten
        max_col = max(name_col_idx, url_col_idx, num_col_idx)
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
        
        # Extrahiere Daten
        name_url_pairs = []
        for i, row in enumerate(values[GOOGLE_START_ROW - 1:], start=GOOGLE_START_ROW):
            while len(row) < max_col:
                row.append('')
            
            name = str(row[name_col_idx - 1]).strip() if len(row) >= name_col_idx else ''
            url = str(row[url_col_idx - 1]).strip() if len(row) >= url_col_idx else ''
            number = str(row[num_col_idx - 1]).strip() if len(row) >= num_col_idx else ''
            
            if url:  # Nur Zeilen mit URL
                if name and number:
                    filename = f"{name}-{number}"
                elif name:
                    filename = name
                elif number:
                    filename = f"bild-{number}"
                else:
                    filename = f"bild-{i}"
                
                name_url_pairs.append((sanitize_filename(filename), url))
        
        print(f"✅ {len(name_url_pairs)} Bilder gefunden")
        return name_url_pairs
        
    except Exception as e:
        print(f"❌ Fehler: {e}")
        import traceback
        traceback.print_exc()
        return []


def main():
    parser = argparse.ArgumentParser(
        description='Lädt Bilder von URLs herunter oder aus Google Sheets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Einfache Verwendung:
  python3 bilder_downloader.py              # Lädt alle Bilder aus Google Sheets
  python3 bilder_downloader.py -u URL       # Einzelnes Bild von URL
  python3 bilder_downloader.py -f urls.txt # Mehrere URLs aus Datei
        """
    )
    
    parser.add_argument('-u', '--url', type=str, help='Einzelne Bild-URL')
    parser.add_argument('-f', '--file', type=str, help='Datei mit URLs (eine pro Zeile)')
    parser.add_argument('-o', '--output', type=str, default=None, help=f'Ausgabeordner (Standard: {BASE_OUTPUT_DIR})')
    parser.add_argument('-w', '--width', type=int, default=DEFAULT_MAX_WIDTH, help=f'Maximale Breite (Standard: {DEFAULT_MAX_WIDTH}px)')
    parser.add_argument('-q', '--quality', type=int, default=DEFAULT_QUALITY, help=f'JPEG Qualität 1-100 (Standard: {DEFAULT_QUALITY})')
    parser.add_argument('-n', '--name', type=str, help='Dateiname (nur bei -u)')
    parser.add_argument('--no-resize', action='store_true', help='Keine Größenanpassung')
    
    args = parser.parse_args()
    
    # Sammle URLs
    name_url_pairs = []
    
    if args.url:
        name_url_pairs.append((args.name, args.url))
    elif args.file:
        urls = read_urls_from_file(args.file)
        if not urls:
            print("❌ Keine URLs gefunden!")
            return
        for url in urls:
            name_url_pairs.append((None, url))
    else:
        # Standard: Google Sheets
        print("📊 Lade Daten aus Google Sheets...")
        name_url_pairs = read_urls_from_google_sheets()
        if not name_url_pairs:
            print("❌ Keine Bilder gefunden!")
            return
    
    # Ausgabeordner
    output_dir = args.output if args.output else BASE_OUTPUT_DIR
    
    print(f"\n{'='*50}")
    print(f"🚢 Schiffsbilder Downloader")
    print(f"{'='*50}")
    print(f"📁 Ordner: {output_dir}")
    print(f"📏 Max. Breite: {args.width}px")
    print(f"🎨 Qualität: {args.quality}")
    print(f"🖼️  Bilder: {len(name_url_pairs)}")
    if args.no_resize:
        print(f"⚠️  Größenanpassung: AUS")
    print(f"{'='*50}\n")
    
    # Verarbeite Bilder
    success_count = 0
    error_count = 0
    
    for i, (name, url) in enumerate(name_url_pairs, 1):
        print(f"[{i}/{len(name_url_pairs)}] ", end='')
        success, filepath = process_image(
            url=url,
            output_dir=output_dir,
            max_width=args.width,
            max_height=None,
            quality=args.quality,
            custom_name=name,
            resize=not args.no_resize
        )
        
        if success:
            success_count += 1
        else:
            error_count += 1
    
    # Zusammenfassung
    print(f"\n{'='*50}")
    print(f"✅ Erfolgreich: {success_count}")
    print(f"❌ Fehler: {error_count}")
    print(f"📁 Ordner: {os.path.abspath(output_dir)}")
    print(f"{'='*50}")
    
    # Formatiere Schiffsnamen in Google Sheets (wenn Bilder heruntergeladen wurden)
    if success_count > 0 and GOOGLE_SHEETS_AVAILABLE and output_dir == BASE_OUTPUT_DIR:
        print(f"\n🎨 Formatiere Schiffsnamen in Google Sheets...")
        try:
            format_ship_names_in_sheets()
        except Exception as e:
            print(f"⚠️  Formatierung übersprungen: {e}")


if __name__ == '__main__':
    main()

