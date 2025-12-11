#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Schiffsbilder Server – Flask-Server für Bild-Upload und -Verarbeitung
- Akzeptiert Bild-URLs oder File-Uploads
- Passt Größe an (nur verkleinern wenn > 1024px)
- Benennt Dateien um (NAME_NUMMER.jpg)
- Speichert auf Server
"""

import os
import sys
import re
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import requests
from PIL import Image
from io import BytesIO
from typing import Optional, Tuple, Dict, List

# Google Sheets Integration
try:
    import gspread
    from google.oauth2.service_account import Credentials
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False
    print("WARNUNG: gspread nicht verfügbar. Google Sheets-Funktionen deaktiviert.")

# Importiere Funktionen aus bilder_downloader.py
sys.path.insert(0, os.path.dirname(__file__))
try:
    from bilder_downloader import sanitize_filename, download_image, resize_image
except ImportError:
    # Fallback falls bilder_downloader nicht verfügbar
    def sanitize_filename(filename: str, max_length: int = 255) -> str:
        # Ersetze Leerzeichen durch Unterstriche
        filename = filename.replace(' ', '_')
        
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        filename = filename.strip('. ')
        
        # Entferne mehrfache Unterstriche
        while '__' in filename:
            filename = filename.replace('__', '_')
        
        if len(filename) > max_length:
            name, ext = os.path.splitext(filename)
            filename = name[:max_length - len(ext)] + ext
        return filename if filename else "image"
    
    def download_image(url: str, timeout: int = 30) -> Optional[bytes]:
        """Lädt ein Bild von einer URL herunter - unterstützt marinetraffic.com und vesselfinder.net"""
        try:
            # Erweiterte Headers für bessere Kompatibilität
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://www.vesselfinder.com/' if 'vesselfinder' in url else 'https://www.marinetraffic.com/',
            }
            
            response = requests.get(url, headers=headers, timeout=timeout, stream=True, allow_redirects=True)
            response.raise_for_status()
            
            # Prüfe ob es wirklich ein Bild ist (auch wenn Content-Type falsch ist)
            content_type = response.headers.get('content-type', '').lower()
            if content_type and not content_type.startswith('image/'):
                # Prüfe Magic Bytes für Bilder
                content_preview = response.content[:20]
                is_image = (
                    content_preview.startswith(b'\xff\xd8\xff') or  # JPEG
                    content_preview.startswith(b'\x89PNG\r\n\x1a\n') or  # PNG
                    content_preview.startswith(b'GIF89a') or content_preview.startswith(b'GIF87a') or  # GIF
                    (content_preview.startswith(b'RIFF') and b'WEBP' in content_preview[:12]) or  # WEBP
                    url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'))
                )
                if not is_image:
                    print(f"Warnung: Content-Type ist '{content_type}', aber könnte trotzdem ein Bild sein")
            
            return response.content
        except Exception as e:
            print(f"Fehler beim Herunterladen: {e}")
            return None
    
    def resize_image(image_data: bytes, max_width: int, max_height: Optional[int] = None, quality: int = 85) -> Optional[bytes]:
        try:
            img = Image.open(BytesIO(image_data))
            original_format = img.format
            
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = rgb_img
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            original_width, original_height = img.size
            
            if original_width <= max_width:
                return None
            
            ratio = max_width / original_width
            new_width = int(original_width * ratio)
            new_height = int(original_height * ratio)
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            output = BytesIO()
            save_format = original_format if original_format in ('JPEG', 'PNG', 'WEBP') else 'JPEG'
            img.save(output, format=save_format, quality=quality, optimize=True)
            return output.getvalue()
        except Exception as e:
            print(f"Fehler beim Größenanpassen: {e}")
            return None

app = Flask(__name__)
CORS(app)

# Konfiguration
BASE_UPLOAD_FOLDER = '/root/Skrip/Datenbank/Schiffsbilder'
MAX_WIDTH = 1024
QUALITY = 85
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}

# Google Sheets Konfiguration
if os.name == 'nt':  # Windows
    SERVICE_ACCOUNT_FILE = os.path.join(os.path.expanduser("~"), "Documents", "Scripts", "segelliste-83c2a17a5e89.json")
else:  # Linux
    SERVICE_ACCOUNT_FILE = "/root/Skrip/segelliste-83c2a17a5e89.json"

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1Q_Dvufm0LCUxYtktMtM18Xz30sXQxCnGfI9SSDFPUNw/edit"
SHEET_NAME = "Schiffsdaten HHLA"

# Erstelle Basis-Ordner falls nicht vorhanden
os.makedirs(BASE_UPLOAD_FOLDER, exist_ok=True)

def get_google_sheets_connection():
    """Stellt Verbindung zu Google Sheets her"""
    if not SHEETS_AVAILABLE:
        return None
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
        gc = gspread.authorize(credentials)
        sh = gc.open_by_url(SPREADSHEET_URL)
        return sh
    except Exception as e:
        print(f"Fehler bei Google Sheets Verbindung: {e}")
        return None

def get_ships_without_image() -> List[Dict]:
    """Holt alle Schiffe mit 'Keine Bild' in Spalte K"""
    sh = get_google_sheets_connection()
    if not sh:
        return []
    
    try:
        worksheet = sh.worksheet(SHEET_NAME)
        all_data = worksheet.get_all_values()
        
        if len(all_data) < 2:
            return []
        
        ships = []
        for i, row in enumerate(all_data[1:], start=2):  # Überspringe Header
            if len(row) < 11:  # Mindestens Spalte K (Index 10)
                continue
            
            ship_name = row[0].strip() if len(row) > 0 else ''  # Spalte A
            mmsi = row[2].strip() if len(row) > 2 else ''  # Spalte C
            k_value = row[10].strip() if len(row) > 10 else ''  # Spalte K
            
            if ship_name and k_value and 'keine bild' in k_value.lower():
                ships.append({
                    'name': ship_name,
                    'mmsi': mmsi,
                    'row': i,
                    'k_value': k_value
                })
        
        return ships
    except Exception as e:
        print(f"Fehler beim Lesen der Schiffe: {e}")
        return []

def find_mmsi_by_name(ship_name: str) -> Optional[str]:
    """Sucht MMSI-Nummer basierend auf Schiffsname"""
    sh = get_google_sheets_connection()
    if not sh:
        return None
    
    try:
        worksheet = sh.worksheet(SHEET_NAME)
        all_data = worksheet.get_all_values()
        
        ship_name_upper = ship_name.upper().strip()
        
        for row in all_data[1:]:  # Überspringe Header
            if len(row) < 3:
                continue
            
            name = row[0].strip().upper() if len(row) > 0 else ''
            mmsi = row[2].strip() if len(row) > 2 else ''
            
            if name == ship_name_upper and mmsi:
                return mmsi
        
        return None
    except Exception as e:
        print(f"Fehler beim Suchen der MMSI: {e}")
        return None

def extract_name_and_mmsi(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extrahiert Name und MMSI aus Text wie 'Keine Bild BALTIC TRANSPORT 255916084'"""
    if not text:
        return None, None
    
    # Entferne "Keine Bild" am Anfang
    text = re.sub(r'^keine\s+bild\s*', '', text, flags=re.IGNORECASE).strip()
    
    # Suche nach MMSI (9-stellige Zahl)
    mmsi_match = re.search(r'\b(\d{9})\b', text)
    mmsi = mmsi_match.group(1) if mmsi_match else None
    
    # Name ist der Rest ohne MMSI
    if mmsi:
        name = re.sub(r'\b' + re.escape(mmsi) + r'\b', '', text).strip()
    else:
        name = text.strip()
    
    # Wenn Name leer, versuche MMSI aus Google Sheets zu finden
    if not name and mmsi:
        # Suche Name basierend auf MMSI
        sh = get_google_sheets_connection()
        if sh:
            try:
                worksheet = sh.worksheet(SHEET_NAME)
                all_data = worksheet.get_all_values()
                for row in all_data[1:]:
                    if len(row) > 2 and row[2].strip() == mmsi:
                        name = row[0].strip() if len(row) > 0 else None
                        break
            except:
                pass
    
    # Wenn nur Name, suche MMSI
    if name and not mmsi:
        mmsi = find_mmsi_by_name(name)
    
    return name if name else None, mmsi if mmsi else None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_filename(name: Optional[str] = None, number: Optional[str] = None, original_filename: Optional[str] = None) -> str:
    """Erstellt einen Dateinamen im Format NAME-NUMMER.jpg"""
    if name and number:
        filename = f"{name}-{number}"
    elif name:
        filename = name
    elif number:
        filename = f"bild-{number}"
    elif original_filename:
        # Extrahiere Name ohne Erweiterung
        filename = os.path.splitext(original_filename)[0]
    else:
        import hashlib
        import time
        filename = f"bild_{int(time.time())}"
    
    # Bereinige Dateinamen
    filename = sanitize_filename(filename)
    
    # Stelle sicher, dass .jpg angehängt ist
    if '.' not in filename:
        filename += '.jpg'
    elif not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
        # Ändere Erweiterung zu .jpg
        filename = os.path.splitext(filename)[0] + '.jpg'
    
    return filename

def save_image(image_data: bytes, filename: str, upload_folder: str) -> Tuple[bool, str]:
    """Speichert Bild auf Server im angegebenen Ordner - überspringt wenn bereits vorhanden"""
    try:
        # Bereinige Dateinamen (Leerzeichen zu Unterstrichen)
        filename = sanitize_filename(filename)
        filepath = os.path.join(upload_folder, filename)
        
        # Prüfe ob Datei bereits existiert
        if os.path.exists(filepath):
            print(f"⏭️  Übersprungen (bereits vorhanden): {filename}")
            return True, filepath  # Erfolg, aber nicht neu gespeichert
        
        with open(filepath, 'wb') as f:
            f.write(image_data)
        
        return True, filepath
    except Exception as e:
        return False, str(e)

@app.route('/')
def index():
    """Zeigt die HTML-Seite"""
    # Versuche HTML-Datei in verschiedenen Verzeichnissen zu finden
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    
    possible_paths = [
        '/var/www/html/schiffsbilder.html',  # Webserver-Verzeichnis
        os.path.join(script_dir, 'schiffsbilder.html'),
        os.path.join(parent_dir, 'schiffsbilder.html'),
        '/root/Skrip/schiffsbilder.html',
        '/root/Skrip/Datenbank/schiffsbilder.html',
        os.path.join(os.path.expanduser('~'), 'Skrip', 'schiffsbilder.html'),
        os.path.join(os.path.expanduser('~'), 'Skrip', 'Datenbank', 'schiffsbilder.html'),
    ]
    
    html_path = None
    for path in possible_paths:
        if os.path.exists(path):
            html_path = path
            break
    
    if html_path:
        print(f"✅ Lade HTML von: {html_path}")
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                from flask import Response
                return Response(f.read(), mimetype='text/html')
        except Exception as e:
            print(f"❌ Fehler beim Lesen der HTML-Datei: {e}")
            return f"Fehler beim Lesen der HTML-Datei: {e}", 500
    else:
        # Erstelle eine einfache HTML-Seite mit Fehlermeldung und Anweisungen
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Schiffsbilder Server</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 40px; background: #f5f5f5; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #d32f2f; }}
                code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>⚠️ Schiffsbilder.html nicht gefunden!</h1>
                <p>Die HTML-Datei wurde in folgenden Verzeichnissen gesucht:</p>
                <ul>
        """
        for path in possible_paths:
            error_html += f"<li><code>{path}</code></li>\n"
        error_html += """
                </ul>
                <p><strong>Lösung:</strong></p>
                <p>Kopiere die Datei <code>schiffsbilder.html</code> in eines der folgenden Verzeichnisse:</p>
                <ul>
                    <li><code>/root/Skrip/Datenbank/</code> (aktuelles Verzeichnis)</li>
                    <li><code>/root/Skrip/</code> (übergeordnetes Verzeichnis)</li>
                </ul>
                <p>Oder starte den Server aus dem Verzeichnis, in dem sich die HTML-Datei befindet.</p>
            </div>
        </body>
        </html>
        """
        print(f"❌ Schiffsbilder.html nicht gefunden! Gesucht in: {possible_paths}")
        from flask import Response
        return Response(error_html, mimetype='text/html')

@app.route('/schiffsbilder.html')
def schiffsbilder_html():
    """Zeigt die HTML-Seite (alternativer Pfad)"""
    return index()

@app.route('/api/test', methods=['GET'])
def test():
    """Test-Route um zu prüfen ob Server läuft"""
    return jsonify({'status': 'ok', 'message': 'Server läuft!'})

@app.route('/api/ships-without-image', methods=['GET'])
def ships_without_image():
    """Gibt Liste aller Schiffe mit 'Keine Bild' in Spalte K zurück"""
    ships = get_ships_without_image()
    return jsonify({
        'success': True,
        'count': len(ships),
        'ships': ships
    })

@app.route('/api/extract-ship-info', methods=['POST'])
def extract_ship_info():
    """Extrahiert Name und MMSI aus Text"""
    data = request.get_json()
    text = data.get('text', '').strip() if data else ''
    
    if not text:
        return jsonify({'error': 'Kein Text angegeben'}), 400
    
    name, mmsi = extract_name_and_mmsi(text)
    
    return jsonify({
        'success': True,
        'name': name,
        'mmsi': mmsi,
        'original_text': text
    })

@app.route('/api/upload-image', methods=['POST'])
def upload_image():
    """Verarbeitet Bild-Upload oder URL-Download"""
    try:
        print(f"POST /api/upload-image empfangen")
        print(f"Form data: {request.form}")
        print(f"Files: {list(request.files.keys())}")
        
        # Prüfe ob einfache Eingabe (Name + MMSI zusammen)
        simple_input = request.form.get('simple_input', '').strip()
        if simple_input:
            # Extrahiere Name und MMSI automatisch
            name, mmsi = extract_name_and_mmsi(simple_input)
            print(f"Extrahiert aus '{simple_input}': Name={name}, MMSI={mmsi}")
        else:
            # Alte Methode: separate Felder
            name = request.form.get('name', '').strip() or None
            mmsi = request.form.get('number', '').strip() or None
            # Wenn nur Name, suche MMSI
            if name and not mmsi:
                mmsi = find_mmsi_by_name(name)
        
        number = mmsi  # Verwende MMSI als Nummer
        
        image_data = None
        original_filename = None
        
        # Prüfe ob URL oder File-Upload
        if 'url' in request.form and request.form['url']:
            # URL-Download
            url = request.form['url'].strip()
            print(f"Lade Bild von URL: {url}")
            image_data = download_image(url)
            if not image_data:
                return jsonify({'error': 'Fehler beim Herunterladen des Bildes von der URL'}), 400
            original_filename = os.path.basename(url) if url else None
            
        elif 'file' in request.files:
            # File-Upload
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'Keine Datei ausgewählt'}), 400
            
            if not allowed_file(file.filename):
                return jsonify({'error': f'Dateityp nicht erlaubt. Erlaubt: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
            
            image_data = file.read()
            original_filename = file.filename
            print(f"Empfange Datei-Upload: {original_filename} ({len(image_data)} Bytes)")
        else:
            return jsonify({'error': 'Bitte gib eine URL ein oder lade eine Datei hoch'}), 400
        
        if not image_data:
            return jsonify({'error': 'Keine Bilddaten erhalten'}), 400
        
        # Passe Größe an (nur wenn größer als MAX_WIDTH)
        print(f"Prüfe Bildgröße (max. {MAX_WIDTH}px Breite)...")
        resized_data = resize_image(image_data, MAX_WIDTH, None, QUALITY)
        if resized_data:
            image_data = resized_data
            print("Bild wurde verkleinert")
        else:
            print("Bild bleibt in Originalgröße")
        
        # Erstelle Dateinamen (mit Schiffsname im Dateinamen)
        # Verwende MMSI als Nummer falls vorhanden
        filename = create_filename(name, number, original_filename)
        print(f"Dateiname: {filename}")
        
        # Speichere direkt im Basis-Ordner (kein Unterordner pro Schiff)
        print(f"Speichere in Ordner: {BASE_UPLOAD_FOLDER}")
        
        # Speichere Bild
        success, filepath = save_image(image_data, filename, BASE_UPLOAD_FOLDER)
        if not success:
            return jsonify({'error': f'Fehler beim Speichern: {filepath}'}), 500
        
        # Relativer Pfad für URL
        relative_path = os.path.relpath(filepath, BASE_UPLOAD_FOLDER)
        image_url = f'/downloads/{os.path.basename(filepath)}'
        
        return jsonify({
            'success': True,
            'filename': os.path.basename(filepath),
            'filepath': relative_path,
            'image_url': image_url,
            'size': len(image_data)
        })
        
    except Exception as e:
        print(f"Fehler: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server-Fehler: {str(e)}'}), 500

@app.route('/downloads/<filename>')
def download_file(filename):
    """Served hochgeladene Bilder aus dem Datenbank-Ordner"""
    full_path = os.path.join(BASE_UPLOAD_FOLDER, filename)
    
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return send_from_directory(BASE_UPLOAD_FOLDER, filename)
    else:
        return jsonify({'error': 'Datei nicht gefunden'}), 404

if __name__ == '__main__':
    print("=" * 50)
    print("🚢 Schiffsbilder Server")
    print("=" * 50)
    print(f"📁 Upload-Ordner: {BASE_UPLOAD_FOLDER}")
    print(f"📁 Bilder werden direkt in: {BASE_UPLOAD_FOLDER} gespeichert")
    print(f"📁 Dateiname Format: SCHIFFSNAME-NUMMER.jpg")
    print(f"📏 Maximale Breite: {MAX_WIDTH}px")
    print(f"🌐 Server startet auf: http://localhost:5000")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=True)

