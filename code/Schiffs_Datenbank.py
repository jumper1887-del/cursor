#!/usr/bin/env python3
"""
Schiffs_Datenbank.py

Datenbank-Management-System für Schiffsdaten mit Google Sheets Integration.
Nutzt die Konfiguration und Credentials aus segelliste_upload.py.

Funktionen:
- SQLite-Datenbank für Schiffsdaten erstellen und verwalten
- Daten aus Google Sheets lesen 0815
- Daten in die Datenbank importieren
- Daten abfragen und exportieren
- Synchronisation zwischen Datenbank und Google Sheets

Benutzung (kurze Befehle):
    python3 Schiffs_Datenbank.py --init                    # Datenbank initialisieren
    python3 Schiffs_Datenbank.py --sync                   # Schiffe synchronisieren (Segelliste → HHLA)
    python3 Schiffs_Datenbank.py --import                 # Daten von VesselFinder importieren (mit Live-Update)
    python3 Schiffs_Datenbank.py --import --max 5         # Erste 5 Schiffe importieren
    python3 Schiffs_Datenbank.py --keine-daten            # Schiffe mit 'Keine Daten' nochmal suchen
    python3 Schiffs_Datenbank.py --show                   # Alle Schiffe anzeigen
"""

import os
import sys
import sqlite3
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
import time
import re
import logging
import glob

# Google Sheets Integration
try:
    import pandas as pd
    import gspread
    from google.oauth2.service_account import Credentials
    SHEETS_AVAILABLE = True
except ImportError:
    SHEETS_AVAILABLE = False
    print("WARNUNG: gspread/pandas nicht verfügbar. Google Sheets-Funktionen sind deaktiviert.")
    print("Installiere mit: pip install gspread google-auth pandas openpyxl")

# Web Scraping für VesselFinder
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("WARNUNG: Selenium nicht verfügbar. VesselFinder-Import deaktiviert.")
    print("Installiere mit: pip install selenium webdriver-manager")

# Undetected ChromeDriver für bessere Bot-Erkennung-Umgehung
try:
    import undetected_chromedriver as uc
    UNDETECTED_AVAILABLE = True
except ImportError:
    UNDETECTED_AVAILABLE = False
    print("INFO: undetected-chromedriver nicht verfügbar. Verwende Standard-ChromeDriver.")
    print("Für bessere Bot-Erkennung-Umgehung: pip install undetected-chromedriver")

# Bildbearbeitung für Marker auf Screenshots
try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("WARNUNG: Pillow nicht verfügbar. Screenshot-Markierungen deaktiviert.")
    print("Installiere mit: pip install Pillow")

# ========================= KONFIGURATION =========================
# Aus segelliste_upload.py übernommene Konfiguration
SERVICE_ACCOUNT_FILE = "/root/Skrip/segelliste-83c2a17a5e89.json"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1Q_Dvufm0LCUxYtktMtM18Xz30sXQxCnGfI9SSDFPUNw/edit"

# Plattform-spezifische Pfade
if os.name == 'nt':  # Windows
    SERVICE_ACCOUNT_FILE = os.path.join(os.path.expanduser("~"), "Documents", "Scripts", "segelliste-83c2a17a5e89.json")
    DB_PATH = os.path.join(os.path.expanduser("~"), "Documents", "Scripts", "schiffe.db")
    LOG_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Scripts", "logs")
    SCREENSHOT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Scripts", "screenshots")
else:  # Linux
    SERVICE_ACCOUNT_FILE = "/root/Skrip/segelliste-83c2a17a5e89.json"
    DB_PATH = "/root/Skrip/Datenbank/schiffe.db"
    LOG_DIR = "/root/Skrip/Datenbank/Log"
    SCREENSHOT_DIR = "/root/Skrip/Datenbank/Fotos"

LOG_PREFIX = "schiffs_datenbank_"
LOG_RETENTION_DAYS = 30

# API-Key für Authentifizierung (aus api_server.py oder Umgebungsvariable)
try:
    # Versuche API-Key aus api_server.py zu importieren
    import sys
    import importlib.util
    api_server_path = os.path.join(os.path.dirname(__file__), "api_server.py")
    if os.path.exists(api_server_path):
        spec = importlib.util.spec_from_file_location("api_server", api_server_path)
        api_server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(api_server)
        SCHIFFS_DATENBANK_API_KEY = getattr(api_server, "SCHIFFS_DATENBANK_API_KEY", None)
    else:
        SCHIFFS_DATENBANK_API_KEY = None
except Exception:
    SCHIFFS_DATENBANK_API_KEY = None

# Fallback: Aus Umgebungsvariable oder Standard-Wert
if not SCHIFFS_DATENBANK_API_KEY:
    SCHIFFS_DATENBANK_API_KEY = os.getenv("SCHIFFS_DATENBANK_API_KEY", "schiffs-db-secret-key-2024")

# ========================= LOGGING =========================
def setup_logging():
    """Richtet das Logging-System ein"""
    os.makedirs(LOG_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    logfile = os.path.join(LOG_DIR, f"{LOG_PREFIX}{today}.log")
    
    # Erstelle Symlink für aktuelles Log
    current_link = os.path.join(LOG_DIR, f"{LOG_PREFIX}current.log")
    try:
        if os.path.exists(current_link):
            os.remove(current_link)
        # Auf Windows: kopiere statt symlink
        if os.name == 'nt':
            pass  # Kein Symlink auf Windows
        else:
            os.symlink(logfile, current_link)
    except Exception:
        pass
    
    # Lösche alte Logs
    cutoff = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)
    for f in glob.glob(os.path.join(LOG_DIR, f"{LOG_PREFIX}*.log")):
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(f))
            if mtime < cutoff:
                os.remove(f)
        except Exception:
            pass
    
    # Konfiguriere Logger
    logger = logging.getLogger("schiffs_datenbank")
    logger.setLevel(logging.INFO)
    
    # Entferne alte Handler
    logger.handlers.clear()
    
    # File Handler
    fh = logging.FileHandler(logfile, encoding="utf-8")
    fh.setLevel(logging.INFO)
    
    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    
    # Format
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", 
                                 datefmt="%Y-%m-%d %H:%M:%S")
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger

logger = setup_logging()

def log_info(msg):
    """Info-Meldung loggen"""
    logger.info(msg)
    
def log_warning(msg):
    """Warnung loggen"""
    logger.warning(msg)
    
def log_error(msg):
    """Fehler loggen"""
    logger.error(msg)

def log_header(title):
    """Loggt einen formatierten Header"""
    line = "=" * 70
    logger.info("")
    logger.info(line)
    logger.info(f"  {title}")
    logger.info(line)

def log_section(title):
    """Loggt einen Abschnitt"""
    logger.info("")
    logger.info(f"--- {title} ---")

# ========================= DATENBANK KLASSE =========================
class SchiffsDatenbank:
    """Hauptklasse für die Verwaltung der Schiffsdatenbank"""
    
    def __init__(self, db_path: str = DB_PATH):
        """
        Initialisiert die Datenbankverbindung
        
        Args:
            db_path: Pfad zur SQLite-Datenbankdatei
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
        # Erstelle Verzeichnis für Datenbank, falls es nicht existiert
        db_dir = os.path.dirname(os.path.abspath(db_path))
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                log_info(f"✓ Datenbankverzeichnis erstellt: {db_dir}")
            except Exception as e:
                log_warning(f"⚠️  Konnte Datenbankverzeichnis nicht erstellen: {e}")
        
    def connect(self):
        """Stellt die Verbindung zur Datenbank her"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            log_info(f"✓ Verbindung zur Datenbank hergestellt: {self.db_path}")
        except sqlite3.Error as e:
            log_error(f"✗ Fehler beim Verbinden mit der Datenbank: {e}")
            sys.exit(1)
    
    def disconnect(self):
        """Schließt die Datenbankverbindung"""
        if self.conn:
            self.conn.close()
            log_info("✓ Datenbankverbindung geschlossen")
    
    def init_database(self):
        """Erstellt die Datenbanktabellen, falls sie noch nicht existieren"""
        log_section("Datenbank Initialisierung")
        self.connect()
        
        log_info("Erstelle Tabelle 'schiffe'...")
        # Haupttabelle für Schiffe
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS schiffe (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                laenge REAL,
                breite REAL,
                tiefgang REAL,
                imo_nummer TEXT,
                mmsi_nummer TEXT,
                typ TEXT,
                flagge TEXT,
                baujahr INTEGER,
                vesselfinder_link TEXT,
                erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                aktualisiert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        log_info("Erstelle Tabelle 'positionen'...")
        # Tabelle für Liegeorte/Positionen
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS positionen (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schiff_id INTEGER NOT NULL,
                liegeort TEXT,
                berth TEXT,
                ankunft TIMESTAMP,
                abfahrt TIMESTAMP,
                status TEXT,
                erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (schiff_id) REFERENCES schiffe(id) ON DELETE CASCADE
            )
        """)
        
        log_info("Erstelle Tabelle 'import_historie'...")
        # Tabelle für Import-Historie
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS import_historie (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quelle TEXT NOT NULL,
                zeitpunkt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                anzahl_datensaetze INTEGER,
                status TEXT,
                bemerkung TEXT
            )
        """)
        
        log_info("Erstelle Indizes...")
        # Index für schnellere Suche
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_schiffe_name ON schiffe(name)
        """)
        
        self.conn.commit()
        log_info("✓ Datenbank erfolgreich initialisiert")
        log_info(f"  Datenbankpfad: {self.db_path}")
        log_info(f"  - Tabelle 'schiffe' erstellt/überprüft")
        log_info(f"  - Tabelle 'positionen' erstellt/überprüft")
        log_info(f"  - Tabelle 'import_historie' erstellt/überprüft")
        
    def add_ship(self, name: str, laenge: Optional[float] = None, 
                 liegeort: Optional[str] = None, **kwargs) -> int:
        """
        Fügt ein neues Schiff zur Datenbank hinzu oder aktualisiert es
        
        Args:
            name: Name des Schiffs (erforderlich)
            laenge: Länge des Schiffs in Metern
            liegeort: Aktueller Liegeort
            **kwargs: Weitere optionale Felder (breite, tiefgang, imo_nummer, etc.)
            
        Returns:
            ID des eingefügten/aktualisierten Schiffs
        """
        self.connect()
        
        # Prüfe ob Schiff bereits existiert
        self.cursor.execute("SELECT id FROM schiffe WHERE name = ?", (name,))
        existing = self.cursor.fetchone()
        
        if existing:
            # Update existierendes Schiff
            ship_id = existing[0]
            update_fields = []
            values = []
            
            if laenge is not None:
                update_fields.append("laenge = ?")
                values.append(laenge)
            
            for key, value in kwargs.items():
                if value is not None and key in ['breite', 'tiefgang', 'imo_nummer', 'mmsi_nummer', 
                                                   'typ', 'flagge', 'baujahr', 'vesselfinder_link']:
                    update_fields.append(f"{key} = ?")
                    values.append(value)
            
            if update_fields:
                update_fields.append("aktualisiert_am = CURRENT_TIMESTAMP")
                values.append(ship_id)
                query = f"UPDATE schiffe SET {', '.join(update_fields)} WHERE id = ?"
                self.cursor.execute(query, values)
                log_info(f"✓ Schiff aktualisiert: {name} (ID: {ship_id})")
        else:
            # Neues Schiff einfügen
            fields = ['name']
            values = [name]
            placeholders = ['?']
            
            if laenge is not None:
                fields.append('laenge')
                values.append(laenge)
                placeholders.append('?')
            
            for key, value in kwargs.items():
                if value is not None and key in ['breite', 'tiefgang', 'imo_nummer', 'mmsi_nummer', 
                                                   'typ', 'flagge', 'baujahr', 'vesselfinder_link']:
                    fields.append(key)
                    values.append(value)
                    placeholders.append('?')
            
            query = f"INSERT INTO schiffe ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
            self.cursor.execute(query, values)
            ship_id = self.cursor.lastrowid
            log_info(f"✓ Neues Schiff hinzugefügt: {name} (ID: {ship_id})")
        
        # Füge Position hinzu, falls Liegeort angegeben
        if liegeort:
            self.cursor.execute("""
                INSERT INTO positionen (schiff_id, liegeort, status)
                VALUES (?, ?, 'aktiv')
            """, (ship_id, liegeort))
        
        self.conn.commit()
        self.disconnect()
        return ship_id
    
    def get_all_ships(self) -> List[Dict]:
        """
        Gibt alle Schiffe aus der Datenbank zurück
        
        Returns:
            Liste von Dictionaries mit Schiffsdaten
        """
        self.connect()
        self.cursor.execute("""
            SELECT s.*, p.liegeort, p.status
            FROM schiffe s
            LEFT JOIN (
                SELECT schiff_id, liegeort, status
                FROM positionen
                WHERE id IN (
                    SELECT MAX(id) FROM positionen GROUP BY schiff_id
                )
            ) p ON s.id = p.schiff_id
            ORDER BY s.name
        """)
        
        columns = [desc[0] for desc in self.cursor.description]
        ships = []
        for row in self.cursor.fetchall():
            ships.append(dict(zip(columns, row)))
        
        self.disconnect()
        return ships
    
    def search_ship(self, search_term: str) -> List[Dict]:
        """
        Sucht nach Schiffen anhand des Namens
        
        Args:
            search_term: Suchbegriff für den Schiffsnamen
            
        Returns:
            Liste von Dictionaries mit passenden Schiffen
        """
        self.connect()
        self.cursor.execute("""
            SELECT s.*, p.liegeort, p.status
            FROM schiffe s
            LEFT JOIN (
                SELECT schiff_id, liegeort, status
                FROM positionen
                WHERE id IN (
                    SELECT MAX(id) FROM positionen GROUP BY schiff_id
                )
            ) p ON s.id = p.schiff_id
            WHERE s.name LIKE ?
            ORDER BY s.name
        """, (f"%{search_term}%",))
        
        columns = [desc[0] for desc in self.cursor.description]
        ships = []
        for row in self.cursor.fetchall():
            ships.append(dict(zip(columns, row)))
        
        self.disconnect()
        return ships
    
    def get_statistics(self) -> Dict:
        """
        Gibt Statistiken über die Datenbank zurück
        
        Returns:
            Dictionary mit Statistiken
        """
        self.connect()
        
        stats = {}
        
        # Gesamtzahl Schiffe
        self.cursor.execute("SELECT COUNT(*) FROM schiffe")
        stats['total_ships'] = self.cursor.fetchone()[0]
        
        # Schiffe nach Liegeort
        self.cursor.execute("""
            SELECT p.liegeort, COUNT(DISTINCT p.schiff_id) as anzahl
            FROM positionen p
            WHERE p.id IN (
                SELECT MAX(id) FROM positionen GROUP BY schiff_id
            )
            AND p.liegeort IS NOT NULL
            GROUP BY p.liegeort
            ORDER BY anzahl DESC
        """)
        stats['ships_by_location'] = dict(self.cursor.fetchall())
        
        # Durchschnittliche Schiffslänge
        self.cursor.execute("SELECT AVG(laenge) FROM schiffe WHERE laenge IS NOT NULL")
        avg_length = self.cursor.fetchone()[0]
        stats['avg_length'] = round(avg_length, 2) if avg_length else None
        
        # Letzter Import
        self.cursor.execute("""
            SELECT zeitpunkt, quelle, anzahl_datensaetze 
            FROM import_historie 
            ORDER BY zeitpunkt DESC 
            LIMIT 1
        """)
        last_import = self.cursor.fetchone()
        if last_import:
            stats['last_import'] = {
                'time': last_import[0],
                'source': last_import[1],
                'count': last_import[2]
            }
        
        self.disconnect()
        return stats

# ========================= GOOGLE SHEETS INTEGRATION =========================
class GoogleSheetsConnector:
    """Klasse für die Verbindung mit Google Sheets"""
    
    def __init__(self, service_account_file: str, spreadsheet_url: str):
        """
        Initialisiert die Verbindung zu Google Sheets
        
        Args:
            service_account_file: Pfad zur Service Account JSON-Datei
            spreadsheet_url: URL des Google Spreadsheets
        """
        if not SHEETS_AVAILABLE:
            raise ImportError("Google Sheets-Bibliotheken nicht verfügbar")
        
        if not os.path.exists(service_account_file):
            raise FileNotFoundError(f"Service Account Datei nicht gefunden: {service_account_file}")
        
        self.service_account_file = service_account_file
        self.spreadsheet_url = spreadsheet_url
        self.gc = None
        self.sh = None
        
    def connect(self):
        """Stellt die Verbindung zu Google Sheets her"""
        try:
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            credentials = Credentials.from_service_account_file(
                self.service_account_file, scopes=scopes
            )
            self.gc = gspread.authorize(credentials)
            self.sh = self.gc.open_by_url(self.spreadsheet_url)
            log_info(f"✓ Verbindung zu Google Sheets hergestellt")
        except Exception as e:
            log_error(f"✗ Fehler beim Verbinden mit Google Sheets: {e}")
            raise
    
    def get_segelliste_data(self) -> pd.DataFrame:
        """
        Liest Daten aus dem Blatt 'Segelliste'
        
        Returns:
            DataFrame mit den Daten
        """
        self.connect()
        try:
            worksheet = self.sh.worksheet("Segelliste")
            data = worksheet.get_all_values()
            
            if len(data) < 2:
                print("WARNUNG: Keine Daten in 'Segelliste' gefunden")
                return pd.DataFrame()
            
            # Erste Zeile ist Info-Text, zweite Zeile sind Header
            headers = data[1]
            rows = data[2:]
            
            df = pd.DataFrame(rows, columns=headers)
            print(f"✓ {len(df)} Zeilen aus 'Segelliste' gelesen")
            return df
            
        except gspread.WorksheetNotFound:
            print("✗ Blatt 'Segelliste' nicht gefunden")
            return pd.DataFrame()
    
    def get_schiffslaenge_data(self) -> pd.DataFrame:
        """
        Liest Daten aus dem Blatt 'Schiffslänge'
        
        Returns:
            DataFrame mit den Daten
        """
        self.connect()
        try:
            worksheet = self.sh.worksheet("Schiffslänge")
            data = worksheet.get_all_values()
            
            if len(data) < 2:
                print("WARNUNG: Keine Daten in 'Schiffslänge' gefunden")
                return pd.DataFrame()
            
            headers = data[0]
            rows = data[1:]
            
            df = pd.DataFrame(rows, columns=headers)
            print(f"✓ {len(df)} Zeilen aus 'Schiffslänge' gelesen")
            return df
            
        except gspread.WorksheetNotFound:
            print("✗ Blatt 'Schiffslänge' nicht gefunden")
            return pd.DataFrame()
    
    def export_to_sheet(self, df: pd.DataFrame, worksheet_name: str):
        """
        Exportiert einen DataFrame zu einem Google Sheet
        
        Args:
            df: DataFrame mit Daten
            worksheet_name: Name des Ziel-Worksheets
        """
        self.connect()
        try:
            worksheet = self.sh.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            worksheet = self.sh.add_worksheet(title=worksheet_name, rows="1000", cols="20")
            print(f"✓ Neues Blatt '{worksheet_name}' erstellt")
        
        # Lösche vorhandene Daten
        worksheet.clear()
        
        # Schreibe Header und Daten
        data = [df.columns.tolist()] + df.values.tolist()
        worksheet.update(values=data, range_name="A1")
        
        print(f"✓ {len(df)} Zeilen nach '{worksheet_name}' exportiert")

# ========================= SHIPXPLORER SCRAPER =========================
class VesselFinderScraper:
    """Klasse zum Abrufen von Schiffsdaten von shipfinder.com (verwendet alten Namen für Kompatibilität)"""
    
    def __init__(self, headless: bool = True, take_screenshots: bool = False):
        """
        Initialisiert den Scraper
        
        Args:
            headless: Browser im Headless-Modus starten (Standard: True)
            take_screenshots: Screenshots für Debug-Zwecke erstellen (Standard: False)
        """
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium nicht verfügbar")
        
        self.headless = headless
        self.driver = None
        self.take_screenshots = take_screenshots
        self.screenshot_counter = 0
        
        # Screenshot-Verzeichnis erstellen (immer, auch für Fehler-Screenshots)
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        if self.take_screenshots:
            log_info(f"Screenshots werden gespeichert in: {SCREENSHOT_DIR}")
        
    def setup_driver(self):
        """Richtet den Selenium WebDriver ein - versucht Undetected Chrome, dann Edge, dann Standard Chrome"""
        
        # Setze einen realistischen User-Agent
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        
        # BESTE OPTION: Undetected ChromeDriver (umgeht Bot-Erkennung am besten)
        if UNDETECTED_AVAILABLE:
            try:
                log_info("Starte Undetected ChromeDriver (Anti-Bot-Umgehung)...")
                
                options = uc.ChromeOptions()
                
                # Basis-Optionen
                if self.headless:
                    options.add_argument("--headless=new")
                
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--disable-gpu")
                options.add_argument(f"--user-agent={user_agent}")
                
                # Sprache
                options.add_argument("--lang=de-DE")
                options.add_argument("--accept-language=de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7")
                
                log_info("  Starte Undetected Chrome-Browser...")
                self.driver = uc.Chrome(options=options, version_main=None)
                
                log_info(f"✓ Undetected Chrome gestartet (Headless: {self.headless})")
                log_info(f"  User-Agent: {user_agent}")
                log_info(f"  ✨ Bot-Erkennung-Umgehung aktiv!")
                return
                
            except Exception as e:
                log_warning(f"Undetected Chrome fehlgeschlagen: {e}")
                log_info("Versuche Standard-Browser...")
        
        # Versuche Edge (funktioniert besser auf Windows)
        try:
            log_info("Starte Edge WebDriver...")
            options = EdgeOptions()
            
            options.add_argument(f"user-agent={user_agent}")
            
            # Browser-Optionen
            if self.headless:
                options.add_argument("--headless=new")
            
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--log-level=3")
            options.add_argument("--disable-gpu")
            
            # Bot-Erkennung verhindern
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Sprache
            options.add_argument("--lang=de-DE")
            
            log_info("  Installiere/aktualisiere EdgeDriver...")
            service = EdgeService(EdgeChromiumDriverManager().install())
            
            log_info("  Starte Edge-Browser...")
            self.driver = webdriver.Edge(service=service, options=options)
            
            # Entferne webdriver-Flag
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            log_info(f"✓ Edge Browser gestartet (Headless: {self.headless})")
            log_info(f"  User-Agent: {user_agent}")
            return
            
        except Exception as e:
            log_warning(f"Edge konnte nicht gestartet werden: {e}")
            log_info("Versuche Chrome als Alternative...")
        
        # Fallback: Chrome
        try:
            log_info("Starte Chrome WebDriver...")
            options = ChromeOptions()
            
            options.add_argument(f"user-agent={user_agent}")
            
            if self.headless:
                options.add_argument("--headless=new")
            
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--log-level=3")
            options.add_argument("--disable-gpu")
            
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            options.add_argument("--lang=de-DE")
            
            log_info("  Installiere/aktualisiere ChromeDriver...")
            service = ChromeService(ChromeDriverManager().install())
            
            log_info("  Starte Chrome-Browser...")
            self.driver = webdriver.Chrome(service=service, options=options)
            
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            log_info(f"✓ Chrome Browser gestartet (Headless: {self.headless})")
            log_info(f"  User-Agent: {user_agent}")
            
        except Exception as e:
            log_error(f"✗ Fehler beim Starten beider Browser (Edge & Chrome): {e}")
            log_error("\n💡 Lösungen:")
            log_error("  1. Aktualisiere Edge/Chrome auf die neueste Version")
            log_error("  2. Führe aus: pip install --upgrade selenium webdriver-manager")
            log_error("  3. Starte PowerShell als Administrator")
            raise
    
    def close_driver(self):
        """Schließt den WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def save_screenshot(self, vessel_name: str, step: str, mark_position: tuple = None):
        """
        Speichert einen Screenshot für Debug-Zwecke
        
        Args:
            vessel_name: Name des Schiffs
            step: Beschreibung des Schritts (z.B. "search", "detail")
            mark_position: Optional (x, y) Koordinaten für eine Markierung
        
        Returns:
            Pfad zum gespeicherten Screenshot oder None
        """
        if not self.driver:
            return None
        
        try:
            self.screenshot_counter += 1
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Bereinige Schiffsnamen für Dateinamen
            safe_name = "".join(c for c in vessel_name if c.isalnum() or c in (' ', '-', '_')).strip()
            safe_name = safe_name.replace(' ', '_')[:50]  # Max 50 Zeichen
            
            filename = f"{self.screenshot_counter:02d}_{safe_name}_{step}_{timestamp}.png"
            filepath = os.path.join(SCREENSHOT_DIR, filename)
            
            self.driver.save_screenshot(filepath)
            
            # Zeichne Markierung, falls Koordinaten angegeben
            if mark_position and PIL_AVAILABLE:
                self._add_marker_to_screenshot(filepath, mark_position)
                log_info(f"      📸 Screenshot mit Markierung gespeichert: {filename}")
            else:
                log_info(f"      📸 Screenshot gespeichert: {filename}")
            
            return filepath
        except Exception as e:
            log_warning(f"      Fehler beim Speichern des Screenshots: {e}")
            return None
    
    def _add_marker_to_screenshot(self, filepath: str, position: tuple):
        """
        Zeichnet ein rotes Kreuz auf dem Screenshot
        
        Args:
            filepath: Pfad zum Screenshot
            position: (x, y) Koordinaten für das Kreuz
        """
        try:
            img = Image.open(filepath)
            draw = ImageDraw.Draw(img)
            
            x, y = position
            size = 20  # Größe des Kreuzes
            width = 3  # Dicke der Linien
            
            # Zeichne rotes Kreuz
            color = (255, 0, 0)  # Rot
            
            # Horizontale Linie
            draw.line([(x - size, y), (x + size, y)], fill=color, width=width)
            # Vertikale Linie
            draw.line([(x, y - size), (x, y + size)], fill=color, width=width)
            
            # Zeichne Kreis um das Kreuz
            draw.ellipse([(x - size - 5, y - size - 5), (x + size + 5, y + size + 5)], 
                        outline=color, width=width)
            
            # Speichere das markierte Bild
            img.save(filepath)
            log_info(f"        ✓ Markierung hinzugefügt bei Position ({x}, {y})")
        except Exception as e:
            log_warning(f"        Fehler beim Hinzufügen der Markierung: {e}")
    
    def search_vessel(self, vessel_name: str) -> Optional[Dict]:
        """
        Sucht ein Schiff auf shipfinder.com und extrahiert die Daten
        
        Strategie:
        1. Öffne https://www.shipfinder.com/
        2. Verwende die Suchfunktion auf der Seite
        3. Extrahiere IMO, MMSI, Länge, Breite, Baujahr, Typ
        
        Args:
            vessel_name: Name des Schiffs
            
        Returns:
            Dictionary mit Schiffsdaten oder None bei Fehler
        """
        if not self.driver:
            self.setup_driver()
        
        try:
            # Gehe zur Hauptseite und verwende die Suchfunktion
            main_url = "https://www.shipfinder.com/"
            
            log_info(f"  Suche: {vessel_name}")
            log_info(f"    Öffne shipfinder.com Hauptseite...")
            self.driver.get(main_url)
            time.sleep(3)  # Warte auf Seitenload
            
            # Schließe Cookie-Consent-Popup (wichtig: muss VOR Suchfeld-Suche passieren!)
            log_info(f"    Prüfe auf Cookie-Consent-Popup...")
            try:
                # Warte kurz auf mögliches Popup
                time.sleep(2)
                
                # Versuche zuerst alle Overlays mit JavaScript zu entfernen
                try:
                    self.driver.execute_script("""
                        // Entferne alle Overlays
                        var overlays = document.querySelectorAll('.fc-dialog-overlay, [class*="overlay"], [class*="modal-backdrop"]');
                        overlays.forEach(function(overlay) {
                            overlay.style.display = 'none';
                            overlay.remove();
                        });
                        
                        // Entferne alle modals/dialogs die das Suchfeld blockieren könnten
                        var modals = document.querySelectorAll('[class*="modal"], [class*="dialog"], [class*="popup"]');
                        modals.forEach(function(modal) {
                            if (modal.style.display !== 'none') {
                                modal.style.display = 'none';
                            }
                        });
                    """)
                    log_info(f"      ✓ Overlays per JavaScript entfernt")
                    time.sleep(1)
                except Exception as e:
                    log_info(f"      ⚠️  JavaScript-Entfernung fehlgeschlagen: {e}")
                
                # Suche nach dem "Consent"-Button im Cookie-Popup
                try:
                    consent_buttons = self.driver.find_elements(By.XPATH, 
                        "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'consent')] | " +
                        "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]")
                    
                    if consent_buttons:
                        consent_buttons[0].click()
                        time.sleep(2)
                        log_info(f"      ✓ Cookie-Consent-Popup geschlossen (Consent-Button)")
                except Exception as e:
                    log_info(f"      ⚠️  Kein Consent-Button gefunden: {e}")
                
                # Alternative: Suche nach anderen Close-Buttons
                try:
                    close_selectors = [
                        "button[aria-label*='Close' i]",
                        "button[aria-label*='Schließen' i]",
                        ".close",
                        "[class*='close']",
                        "[class*='dismiss']",
                        "[id*='close']"
                    ]
                    for selector in close_selectors:
                        try:
                            close_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if close_buttons:
                                # Prüfe ob Button sichtbar ist
                                for btn in close_buttons[:5]:
                                    try:
                                        if btn.is_displayed():
                                            btn.click()
                                            time.sleep(2)
                                            log_info(f"      ✓ Popup geschlossen: {selector}")
                                            break
                                    except:
                                        continue
                        except:
                            continue
                except:
                    pass
                
                # Final: Nochmal alle Overlays entfernen (falls welche nachgeladen wurden)
                try:
                    self.driver.execute_script("""
                        var overlays = document.querySelectorAll('.fc-dialog-overlay, [class*="overlay"]');
                        overlays.forEach(function(overlay) {
                            overlay.remove();
                        });
                    """)
                except:
                    pass
                    
            except Exception as e:
                log_info(f"      ⚠️  Fehler beim Schließen des Popups: {e}")
            
            # Finde das Suchfeld und gebe den Schiffsnamen ein
            log_info(f"    Suche nach Suchfeld...")
            try:
                # shipfinder.com verwendet ein spezifisches Suchfeld mit id="txtKey"
                search_box = None
                search_selectors = [
                    "#txtKey",  # Das Haupt-Suchfeld auf shipfinder.com
                    "input[placeholder*='搜索船舶']",  # Chinesisch: "Suche Schiff"
                    "input[placeholder*='船']",  # Chinesisch: "Schiff"
                    "input[placeholder*='搜索']",  # Chinesisch: "Suchen"
                    "input[type='text']",
                    "input[placeholder*='Vessel']",
                    "input[placeholder*='IMO']",
                    "input[placeholder*='MMSI']",
                    "input[placeholder*='Ship']",
                    "#search",
                    ".search-input",
                    ".search-box",
                    "input[name='search']",
                    "input[id*='search']",
                    "input[class*='search']",
                    ".searchInput",
                    "#searchInput",
                    "#searchBox",
                    ".form-control",  # Bootstrap-Class
                    "input"  # Als letztes alle Input-Felder
                ]
                
                for selector in search_selectors:
                    try:
                        search_box = self.driver.find_element(By.CSS_SELECTOR, selector)
                        log_info(f"      ✓ Suchfeld gefunden: {selector}")
                        break
                    except NoSuchElementException:
                        continue
                
                if not search_box:
                    log_warning(f"    ✗ Suchfeld nicht gefunden")
                    return None
                
                # Warte bis das Suchfeld klickbar ist
                try:
                    wait = WebDriverWait(self.driver, 10)
                    search_box = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#search")))
                    log_info(f"      ✓ Suchfeld ist bereit")
                except:
                    log_warning(f"      ⚠️  Timeout beim Warten auf Suchfeld")
                
                # Gebe den Schiffsnamen ein
                log_info(f"    Gebe Schiffsnamen ein: {vessel_name}")
                
                # Versuche verschiedene Methoden, um Text einzugeben
                try:
                    # Methode 1: Fokussiere mit JavaScript und gib Text ein
                    try:
                        # Finde das Input-Feld innerhalb des search-Divs
                        input_field = search_box.find_element(By.TAG_NAME, "input")
                        # Fokussiere mit JavaScript
                        self.driver.execute_script("arguments[0].focus();", input_field)
                        time.sleep(0.5)
                        input_field.clear()
                        input_field.send_keys(vessel_name)
                        log_info(f"      ✓ Text eingegeben (Methode: Input-Feld)")
                    except:
                        # Methode 2: Klicke auf das Div und versuche dann Input
                        try:
                            # Entferne nochmal alle Overlays vor dem Klick
                            self.driver.execute_script("""
                                var overlays = document.querySelectorAll('.fc-dialog-overlay, [class*="overlay"]');
                                overlays.forEach(function(o) { o.remove(); });
                            """)
                            time.sleep(0.5)
                            
                            search_box.click()
                            time.sleep(1)
                            search_box.clear()
                            search_box.send_keys(vessel_name)
                            log_info(f"      ✓ Text eingegeben (Methode: Direkter Klick)")
                        except:
                            # Methode 3: Setze Wert direkt mit JavaScript
                            self.driver.execute_script("""
                                var searchInput = document.querySelector('#search input') || document.querySelector('#search');
                                if (searchInput) {
                                    searchInput.value = arguments[0];
                                    searchInput.dispatchEvent(new Event('input', { bubbles: true }));
                                }
                            """, vessel_name)
                            log_info(f"      ✓ Text eingegeben (Methode: JavaScript)")
                    
                    time.sleep(2)
                except Exception as e:
                    log_error(f"      ✗ Fehler beim Texteingeben: {e}")
                    raise
                
                # Drücke Enter oder klicke auf Such-Button
                log_info(f"    Starte Suche...")
                
                # Versuche verschiedene Methoden zum Absenden der Suche
                search_submitted = False
                
                # Methode 1: Verwende shipfinder.com-spezifische Suchfunktion
                try:
                    self.driver.execute_script("""
                        // Methode 1a: Verwende die native shipfinder.com Suchfunktion
                        if (typeof searchLayer !== 'undefined' && typeof searchLayer.showSearchResult === 'function') {
                            searchLayer.showSearchResult();
                            return true;
                        }
                        
                        // Methode 1b: Enter-Event auslösen
                        var searchInput = document.querySelector('#txtKey') || 
                                         document.querySelector('#search input') || 
                                         document.querySelector('#search');
                        if (searchInput) {
                            var event = new KeyboardEvent('keydown', {
                                key: 'Enter',
                                code: 'Enter',
                                keyCode: 13,
                                which: 13,
                                bubbles: true
                            });
                            searchInput.dispatchEvent(event);
                            
                            // Alternative: Submit-Event auslösen
                            var form = searchInput.closest('form');
                            if (form) {
                                form.submit();
                            }
                            return true;
                        }
                        return false;
                    """)
                    search_submitted = True
                    log_info(f"      ✓ Suche gestartet (Methode: JavaScript/searchLayer)")
                except Exception as e:
                    log_info(f"      ⚠️  JavaScript-Suche fehlgeschlagen: {e}")
                
                # Methode 2: Suche nach Such-Button und klicke darauf
                if not search_submitted:
                    try:
                        button_selectors = [
                            "#searchBtn",  # shipfinder.com Such-Button
                            "a.search_btn",  # shipfinder.com Such-Link
                            ".search_btn",
                            "button[type='submit']",
                            "button.search-button",
                            "button[class*='search']",
                            "input[type='submit']",
                            "//button[contains(@class, 'search')]",
                            "//button[@type='submit']",
                            "//a[@id='searchBtn']",
                            "//a[contains(@class, 'search_btn')]"
                        ]
                        
                        for selector in button_selectors:
                            try:
                                if selector.startswith("//"):
                                    btn = self.driver.find_element(By.XPATH, selector)
                                else:
                                    btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                                
                                if btn and btn.is_displayed():
                                    btn.click()
                                    search_submitted = True
                                    log_info(f"      ✓ Suche gestartet (Methode: Such-Button)")
                                    break
                            except:
                                continue
                    except Exception as e:
                        log_info(f"      ⚠️  Button-Klick fehlgeschlagen: {e}")
                
                if not search_submitted:
                    log_warning(f"      ⚠️  Konnte Suche nicht starten, warte trotzdem auf Ergebnisse...")
                
                time.sleep(4)  # Warte auf Suchergebnisse
                
                # Prüfe ob Schiff nicht gefunden wurde
                page_text = self.driver.page_source.lower()
                if "could not find" in page_text or "not found" in page_text or "no results" in page_text:
                    log_warning(f"    ✗ Schiff nicht gefunden: {vessel_name}")
                    return None
                
                # Klicke auf Position 100, 120 (wo das erste Suchergebnis ist)
                click_x, click_y = 100, 120
                log_info(f"    → Klicke auf Suchergebnis bei Position ({click_x}, {click_y})...")
                
                try:
                    # Klicke mit JavaScript auf die Position
                    clicked = self.driver.execute_script(f"""
                        var element = document.elementFromPoint({click_x}, {click_y});
                        if (element) {{
                            element.click();
                            return true;
                        }}
                        return false;
                    """)
                    
                    if clicked:
                        log_info(f"      ✓ Klick auf Position ({click_x}, {click_y}) erfolgreich")
                        time.sleep(4)  # Warte auf Detail-Seite
                    else:
                        log_warning(f"      ⚠️  Kein klickbares Element an Position ({click_x}, {click_y})")
                        # Fallback: Versuche ersten Link zu finden
                        raise Exception("Kein Element an Klick-Position")
                    
                except Exception as e:
                    log_warning(f"    ⚠️  Klick fehlgeschlagen, versuche Link zu finden: {e}")
                    try:
                        # Fallback: Suche nach erstem Vessel-Link
                        result_link = self.driver.find_element(By.CSS_SELECTOR, "a[href*='/vessels/'], a[onclick*='ship']")
                        result_url = result_link.get_attribute("href")
                        log_info(f"      ✓ Ergebnis-Link gefunden: {result_url}")
                        result_link.click()
                        time.sleep(4)
                    except NoSuchElementException:
                        log_warning(f"      ✗ Kein Ergebnis-Link gefunden")
                        return None
                
            except Exception as e:
                log_error(f"    ✗ Fehler beim Suchen: {e}")
                return None
            
            # Extrahiere Daten von der shipfinder.com Detail-Seite
            data = self._extract_shipfinder_data(vessel_name)
            
            if data:
                # Prüfe ob WICHTIGE Daten vorhanden sind (IMO oder Länge)
                has_important = data.get('imo_nummer') or data.get('laenge')
                
                if has_important:
                    # Zusammenfassung der gefundenen Daten
                    summary = []
                    if data.get('imo_nummer'):
                        summary.append(f"IMO={data['imo_nummer']}")
                    if data.get('mmsi_nummer'):
                        summary.append(f"MMSI={data['mmsi_nummer']}")
                    if data.get('typ'):
                        summary.append(f"Typ={data['typ']}")
                    if data.get('laenge'):
                        summary.append(f"Länge={data['laenge']}m")
                    if data.get('baujahr'):
                        summary.append(f"Jahr={data['baujahr']}")
                    
                    log_info(f"    ✓ Daten extrahiert: {', '.join(summary)}")
                    return data
                else:
                    # Nur unwichtige Daten (z.B. nur Typ)
                    log_warning(f"    ✗ Keine wichtigen Daten (nur: {', '.join([k for k, v in data.items() if v and k != 'name'])})")
                    return None
            else:
                log_warning(f"    ✗ Keine Daten extrahiert")
                return None
                
        except Exception as e:
            log_error(f"    ✗ Fehler bei der Suche: {e}")
            import traceback
            log_error(traceback.format_exc())
            return None
    
    def _extract_shipfinder_data(self, vessel_name: str) -> Optional[Dict]:
        """
        Extrahiert Schiffsdaten von der shipfinder.com Detail-Seite
        
        shipfinder.com verwendet spezifische IDs:
        - span#si_mmsi für MMSI
        - td#si_imo für IMO  
        - td#si__length für Länge
        - td#si__width für Breite
        
        Args:
            vessel_name: Name des Schiffs
            
        Returns:
            Dictionary mit Schiffsdaten
        """
        try:
            data = {'name': vessel_name}
            page_source = self.driver.page_source
            
            log_info(f"      Extrahiere Daten von shipfinder.com...")
            
            # IMO-Nummer aus <td id="si_imo" title="9597484">9597484</td>
            try:
                imo_elem = self.driver.find_element(By.CSS_SELECTOR, "#si_imo")
                imo_text = imo_elem.get_attribute("title") or imo_elem.text
                if imo_text:
                    data['imo_nummer'] = imo_text.strip()
                    log_info(f"        ✓ IMO: {data['imo_nummer']}")
            except:
                # Fallback: Regex-Suche
                imo_match = re.search(r'si_imo.*?(\d{7})', page_source)
                if imo_match:
                    data['imo_nummer'] = imo_match.group(1)
                else:
                    data['imo_nummer'] = None
            
            # MMSI-Nummer aus <span id="si_mmsi" title="566879000">566879000</span>
            try:
                mmsi_elem = self.driver.find_element(By.CSS_SELECTOR, "#si_mmsi")
                mmsi_text = mmsi_elem.get_attribute("title") or mmsi_elem.text
                if mmsi_text:
                    data['mmsi_nummer'] = mmsi_text.strip()
                    log_info(f"        ✓ MMSI: {data['mmsi_nummer']}")
            except:
                # Fallback: Regex-Suche
                mmsi_match = re.search(r'si_mmsi.*?(\d{9})', page_source)
                if mmsi_match:
                    data['mmsi_nummer'] = mmsi_match.group(1)
                else:
                    data['mmsi_nummer'] = None
            
            # Länge aus <td id="si__length" title="328m">328m</td>
            try:
                length_elem = self.driver.find_element(By.CSS_SELECTOR, "#si__length")
                length_text = length_elem.get_attribute("title") or length_elem.text
                if length_text:
                    # Entferne "m" und konvertiere zu Float
                    length_value = re.search(r'(\d{2,3})', length_text)
                    if length_value:
                        data['laenge'] = float(length_value.group(1))
                        log_info(f"        ✓ Länge: {data['laenge']}m")
            except:
                data['laenge'] = None
            
            # Breite aus <td id="si__width" title="45m">45m</td>
            try:
                width_elem = self.driver.find_element(By.CSS_SELECTOR, "#si__width")
                width_text = width_elem.get_attribute("title") or width_elem.text
                if width_text:
                    # Entferne "m" und konvertiere zu Float
                    width_value = re.search(r'(\d{2,3})', width_text)
                    if width_value:
                        data['breite'] = float(width_value.group(1))
                        log_info(f"        ✓ Breite: {data['breite']}m")
            except:
                data['breite'] = None
            
            # Baujahr - versuche verschiedene mögliche IDs/Klassen
            try:
                # Mögliche IDs/Selektoren für Baujahr
                year_selectors = ["#si_build", "#si_year", "#si_built", "[id*='year']", "[id*='build']"]
                for selector in year_selectors:
                    try:
                        year_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                        year_text = year_elem.get_attribute("title") or year_elem.text
                        year_match = re.search(r'(\d{4})', year_text)
                        if year_match:
                            data['baujahr'] = int(year_match.group(1))
                            log_info(f"        ✓ Baujahr: {data['baujahr']}")
                            break
                    except:
                        continue
                
                # Fallback: Regex im gesamten HTML
                if not data.get('baujahr'):
                    year_match = re.search(r'(?:建造年份|建造|Built|Year)[：:\s]+(\d{4})', page_source, re.IGNORECASE)
                    if year_match:
                        data['baujahr'] = int(year_match.group(1))
            except:
                data['baujahr'] = None
            
            # Schiffstyp
            try:
                # Suche nach Typ-Element oder Pattern
                type_selectors = ["#si_type", "#si_shiptype", "[id*='type']"]
                for selector in type_selectors:
                    try:
                        type_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                        type_text = type_elem.get_attribute("title") or type_elem.text
                        if type_text:
                            data['typ'] = type_text.strip()
                            log_info(f"        ✓ Typ: {data['typ']}")
                            break
                    except:
                        continue
                
                # Fallback: Regex
                if not data.get('typ'):
                    type_patterns = [
                        r'(Container Ship|Bulk Carrier|Tanker|Cargo|General Cargo|Passenger|Ro-Ro|Vehicle Carrier)',
                        r'(集装箱船|散货船|油轮|货船)'  # Chinesisch
                    ]
                    for pattern in type_patterns:
                        type_match = re.search(pattern, page_source, re.IGNORECASE)
                        if type_match:
                            data['typ'] = type_match.group(1)
                            break
            except:
                data['typ'] = None
            
            # Flagge
            try:
                flag_selectors = ["#si_flag", "#si_country", "[id*='flag']"]
                for selector in flag_selectors:
                    try:
                        flag_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                        flag_text = flag_elem.get_attribute("title") or flag_elem.text
                        if flag_text:
                            data['flagge'] = flag_text.strip()
                            break
                    except:
                        continue
            except:
                data['flagge'] = None
            
            # VesselFinder Link erstellen (wenn wir IMO haben)
            if data.get('imo_nummer'):
                data['vesselfinder_link'] = f"https://www.vesselfinder.com/de/?imo={data['imo_nummer']}"
            
            # Prüfe ob wir überhaupt Daten gefunden haben
            has_data = any(v for k, v in data.items() if k != 'name' and v is not None)
            
            if not has_data:
                log_warning(f"        ✗ Keine Daten gefunden (Seite möglicherweise noch am Laden)")
                return None
            
            return data
            
        except Exception as e:
            log_error(f"      Fehler beim Extrahieren: {e}")
            import traceback
            log_error(traceback.format_exc())
            return None
    
    def __enter__(self):
        """Context Manager Eingang"""
        self.setup_driver()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context Manager Ausgang"""
        self.close_driver()

# ========================= HAUPTFUNKTIONEN =========================
def import_from_sheets(db: SchiffsDatenbank):
    """
    Importiert Schiffsdaten aus Google Sheets in die Datenbank
    """
    if not SHEETS_AVAILABLE:
        print("✗ Google Sheets-Funktionen nicht verfügbar")
        return
    
    print("\n=== Import aus Google Sheets ===")
    
    try:
        gs = GoogleSheetsConnector(SERVICE_ACCOUNT_FILE, SPREADSHEET_URL)
        
        # Lese Segelliste
        df_segelliste = gs.get_segelliste_data()
        
        if df_segelliste.empty:
            print("Keine Daten zum Importieren gefunden")
            return
        
        # Bestimme Spaltennamen (können je nach Blatt variieren)
        # Typische Struktur: Spalte 2 = Liegeort, Spalte 3 = Länge, Spalte 4 = Name
        df_cols = df_segelliste.columns.tolist()
        
        imported_count = 0
        db.connect()
        
        for idx, row in df_segelliste.iterrows():
            try:
                # Versuche die relevanten Spalten zu identifizieren
                # Diese Indizes basieren auf der Struktur aus segelliste_upload.py
                if len(row) >= 5:
                    name = str(row[4]).strip() if len(row) > 4 else ""
                    laenge_str = str(row[3]).strip() if len(row) > 3 else ""
                    liegeort = str(row[2]).strip() if len(row) > 2 else ""
                    
                    if not name or name == "":
                        continue
                    
                    # Konvertiere Länge
                    laenge = None
                    if laenge_str and laenge_str != "":
                        try:
                            laenge = float(laenge_str.replace(",", "."))
                        except ValueError:
                            pass
                    
                    # Füge Schiff hinzu
                    db.add_ship(name=name, laenge=laenge, liegeort=liegeort)
                    imported_count += 1
                    
            except Exception as e:
                print(f"  Fehler bei Zeile {idx}: {e}")
                continue
        
        # Speichere Import-Historie
        db.cursor.execute("""
            INSERT INTO import_historie (quelle, anzahl_datensaetze, status)
            VALUES (?, ?, ?)
        """, ('Google Sheets - Segelliste', imported_count, 'erfolreich'))
        
        db.conn.commit()
        db.disconnect()
        
        print(f"\n✓ Import abgeschlossen: {imported_count} Schiffe importiert/aktualisiert")
        
    except Exception as e:
        print(f"✗ Fehler beim Import: {e}")

def export_to_sheets(db: SchiffsDatenbank, worksheet_name: str = "Schiffsdatenbank"):
    """
    Exportiert Schiffsdaten aus der Datenbank zu Google Sheets
    
    Args:
        db: Datenbank-Instanz
        worksheet_name: Name des Ziel-Worksheets
    """
    if not SHEETS_AVAILABLE:
        print("✗ Google Sheets-Funktionen nicht verfügbar")
        return
    
    print(f"\n=== Export zu Google Sheets ({worksheet_name}) ===")
    
    try:
        # Hole alle Schiffe
        ships = db.get_all_ships()
        
        if not ships:
            print("Keine Daten zum Exportieren gefunden")
            return
        
        # Konvertiere zu DataFrame
        df = pd.DataFrame(ships)
        
        # Wähle relevante Spalten
        export_columns = ['name', 'laenge', 'breite', 'tiefgang', 'imo_nummer', 
                         'mmsi_nummer', 'baujahr', 'typ', 'flagge', 'liegeort', 'status']
        existing_columns = [col for col in export_columns if col in df.columns]
        df_export = df[existing_columns]
        
        # Übersetze Spaltennamen ins Deutsche
        column_mapping = {
            'name': 'Name',
            'laenge': 'Länge (m)',
            'breite': 'Breite (m)',
            'tiefgang': 'Tiefgang (m)',
            'imo_nummer': 'IMO-Nummer',
            'mmsi_nummer': 'MMSI-Nummer',
            'baujahr': 'Baujahr',
            'typ': 'Typ',
            'flagge': 'Flagge',
            'liegeort': 'Liegeort',
            'status': 'Status'
        }
        df_export.rename(columns=column_mapping, inplace=True)
        
        # Exportiere zu Google Sheets
        gs = GoogleSheetsConnector(SERVICE_ACCOUNT_FILE, SPREADSHEET_URL)
        gs.export_to_sheet(df_export, worksheet_name)
        
        print(f"✓ {len(df_export)} Schiffe nach Google Sheets exportiert")
        
    except Exception as e:
        print(f"✗ Fehler beim Export: {e}")

def update_hhla_sheet_with_data(db: SchiffsDatenbank):
    """
    Aktualisiert das Sheet 'Schiffsdaten HHLA' mit Daten aus der Datenbank.
    Liest die Schiffsnamen aus Spalte A und schreibt die gefundenen Daten in die anderen Spalten.
    
    Spaltenaufteilung:
    A = Name
    B = Schiffstyp (WIRD NICHT GESCHRIEBEN)
    C = MMSI-Nummer (oder "Keine Daten" nach 3 Versuchen)
    D = IMO-Nummer
    E = Baujahr
    F = Länge
    G = Breite
    H = (Reserve)
    I = VesselFinder-Link
    """
    if not SHEETS_AVAILABLE:
        log_error("✗ Google Sheets-Funktionen nicht verfügbar")
        return
    
    log_header("Aktualisiere 'Schiffsdaten HHLA' mit Datenbank-Daten")
    
    try:
        gs = GoogleSheetsConnector(SERVICE_ACCOUNT_FILE, SPREADSHEET_URL)
        gs.connect()
        
        try:
            worksheet = gs.sh.worksheet("Schiffsdaten HHLA")
        except gspread.WorksheetNotFound:
            log_error("✗ Blatt 'Schiffsdaten HHLA' nicht gefunden")
            return
        
        # Lese alle Werte
        all_values = worksheet.get_all_values()
        
        if len(all_values) < 1:
            log_error("✗ Keine Daten im Sheet gefunden")
            return
        
        # Prüfe/erstelle Header
        header = all_values[0] if all_values else []
        expected_header = ['Name', 'Schiffstyp', 'MMSI-Nummer', 'IMO-Nummer', 'Baujahr', 'Länge (m)', 'Breite (m)', '', 'VesselFinder-Link']
        
        if len(header) < 9 or header[:7] != expected_header[:7]:
            # Erstelle/aktualisiere Header - neue API
            worksheet.update(values=[expected_header], range_name='A1:I1')
            log_info("✓ Header aktualisiert: A=Name, B=nicht geschrieben, C=MMSI, D=IMO, E=Jahr, F=Länge, G=Breite, I=Link")
        
        # Sammle Updates
        updates = []
        row_num = 2  # Start bei Zeile 2 (nach Header)
        
        # Statistiken
        count_skipped = 0  # Schiffe mit allen Daten
        count_no_changes = 0  # Schiffe ohne neue Daten
        count_updated = 0  # Schiffe mit Updates
        missing_ranges = []  # Bereiche von Schiffen nicht in DB
        missing_start = None
        missing_end = None
        
        db.connect()
        
        # Verarbeite alle Zeilen (ab Zeile 2)
        for row in all_values[1:]:
            if not row or not row[0].strip():
                row_num += 1
                continue
            
            vessel_name = row[0].strip()
            
            # Hole existierende Werte aus der Zeile (Spalten B-I)
            # Erweitere das Array falls nötig
            while len(row) < 9:
                row.append('')
            
            # Spalte B (Typ) wird NICHT geschrieben, aber C (MMSI) wird geschrieben
            existing_mmsi = row[2].strip() if len(row) > 2 else ''
            existing_imo = row[3].strip() if len(row) > 3 else ''
            existing_jahr = row[4].strip() if len(row) > 4 else ''
            existing_laenge = row[5].strip() if len(row) > 5 else ''
            existing_breite = row[6].strip() if len(row) > 6 else ''
            existing_link = row[8].strip() if len(row) > 8 else ''
            
            # Prüfe ob alle wichtigen Felder bereits ausgefüllt sind (ohne Typ, aber mit MMSI)
            if all([existing_mmsi, existing_imo, existing_jahr, existing_laenge, existing_breite, existing_link]):
                count_skipped += 1
                row_num += 1
                continue
            
            # Suche in Datenbank
            # Reihenfolge: typ, mmsi, imo, baujahr, laenge, breite, vesselfinder_link
            db.cursor.execute("""
                SELECT typ, mmsi_nummer, imo_nummer, baujahr, laenge, breite, vesselfinder_link
                FROM schiffe
                WHERE name = ?
            """, (vessel_name,))
            
            result = db.cursor.fetchone()
            
            if result:
                typ, mmsi, imo, baujahr, laenge, breite, vf_link = result
                
                # Bereite Update vor (Spalten C-G und I, ohne B/Typ)
                # NUR leere Zellen füllen, bestehende Werte NICHT überschreiben
                update_data_cg = [
                    existing_mmsi if existing_mmsi else (str(mmsi) if mmsi else ''),       # C: MMSI-Nummer
                    existing_imo if existing_imo else (str(imo) if imo else ''),           # D: IMO-Nummer
                    existing_jahr if existing_jahr else (str(baujahr) if baujahr else ''), # E: Baujahr
                    existing_laenge if existing_laenge else (str(laenge) if laenge else ''), # F: Länge
                    existing_breite if existing_breite else (str(breite) if breite else '')  # G: Breite
                ]
                
                # Spalte I: VesselFinder-Link
                update_data_i = existing_link if existing_link else (str(vf_link) if vf_link else '')
                
                # Prüfe ob tatsächlich etwas geändert wurde
                original_data = [existing_mmsi, existing_imo, existing_jahr, existing_laenge, existing_breite]
                changes_made = False
                
                if update_data_cg != original_data:
                    # Füge zu Batch-Update hinzu (ohne Spalte B)
                    updates.append({
                        'range': f'C{row_num}:G{row_num}',
                        'values': [update_data_cg]
                    })
                    changes_made = True
                
                # Update Spalte I (VesselFinder-Link)
                if not existing_link and vf_link:
                    updates.append({
                        'range': f'I{row_num}',
                        'values': [[update_data_i]]
                    })
                    changes_made = True
                
                if changes_made:
                    # Zeige nur die neu gefüllten Felder (ohne Typ)
                    filled = []
                    if not existing_mmsi and mmsi:
                        filled.append(f"MMSI={mmsi}")
                    if not existing_imo and imo:
                        filled.append(f"IMO={imo}")
                    if not existing_jahr and baujahr:
                        filled.append(f"Jahr={baujahr}")
                    if not existing_laenge and laenge:
                        filled.append(f"Länge={laenge}m")
                    if not existing_breite and breite:
                        filled.append(f"Breite={breite}m")
                    if not existing_link and vf_link:
                        filled.append(f"VF-Link")
                    
                    if filled:
                        log_info(f"  ✓ Zeile {row_num}: {vessel_name} → {', '.join(filled)}")
                        count_updated += 1
                        # Beende fehlenden Bereich falls einer läuft
                        if missing_start is not None:
                            missing_ranges.append((missing_start, missing_end))
                            missing_start = None
                            missing_end = None
                    else:
                        count_no_changes += 1
                else:
                    count_no_changes += 1
                    # Beende fehlenden Bereich falls einer läuft
                    if missing_start is not None:
                        missing_ranges.append((missing_start, missing_end))
                        missing_start = None
                        missing_end = None
            else:
                # Sammle fehlende Schiffe in Bereichen
                if missing_start is None:
                    missing_start = row_num
                missing_end = row_num
            
            row_num += 1
        
        # Beende letzten fehlenden Bereich falls vorhanden
        if missing_start is not None:
            missing_ranges.append((missing_start, missing_end))
        
        db.disconnect()
        
        # Ausgabe Zusammenfassung
        log_info("")
        log_info("="*70)
        log_info("Zusammenfassung:")
        log_info(f"  ✓ {count_skipped} Schiffe mit vollständigen Daten übersprungen")
        log_info(f"  ✓ {count_updated} Schiffe aktualisiert")
        if count_no_changes > 0:
            log_info(f"  → {count_no_changes} Schiffe ohne neue Daten")
        
        # Zeige fehlende Bereiche
        if missing_ranges:
            log_warning(f"  ⚠️  {len(missing_ranges)} Bereich(e) nicht in Datenbank gefunden:")
            for start, end in missing_ranges:
                if start == end:
                    log_warning(f"     • Zeile {start}")
                else:
                    log_warning(f"     • Zeile {start}-{end}")
        
        log_info("="*70)
        log_info("")
        
        # Führe Batch-Update aus
        if updates:
            log_info(f"Führe Batch-Update aus ({len(updates)} Bereiche)...")
            worksheet.batch_update(updates)
            log_info(f"✓ Update abgeschlossen: {len(updates)} Zellbereiche aktualisiert")
        else:
            log_info("✓ Keine Updates nötig - alle Daten sind aktuell")
        
    except Exception as e:
        log_error(f"✗ Fehler beim Aktualisieren: {e}")
        import traceback
        log_error(traceback.format_exc())

def update_single_ship_in_sheet(vessel_name: str, vessel_data: Dict, worksheet):
    """
    Aktualisiert ein einzelnes Schiff im Google Sheet
    
    Args:
        vessel_name: Name des Schiffs
        vessel_data: Dictionary mit Schiffsdaten
        worksheet: Google Sheets Worksheet-Objekt
    """
    try:
        # Finde die Zeile mit diesem Schiffsnamen
        all_values = worksheet.get_all_values()
        
        for row_idx, row in enumerate(all_values[1:], start=2):  # Überspringe Header
            if not row or not row[0].strip():
                continue
            
            if row[0].strip() == vessel_name:
                # Gefunden! Aktualisiere diese Zeile
                # Erweitere Row auf 9 Spalten falls nötig
                while len(row) < 9:
                    row.append('')
                
                # Hole existierende Werte
                existing_link = row[8].strip() if len(row) > 8 else ''
                
                # Bereite Update-Daten vor (nur wenn leer)
                # Spalte B (Typ) wird NICHT geschrieben
                mmsi = vessel_data.get('mmsi_nummer', '')
                imo = vessel_data.get('imo_nummer', '')
                baujahr = vessel_data.get('baujahr', '')
                laenge = vessel_data.get('laenge', '')
                breite = vessel_data.get('breite', '')
                vf_link = vessel_data.get('vesselfinder_link', '')
                
                # Schreibe Daten (Spalten C-G, ohne B/Typ)
                update_data = [
                    str(mmsi) if mmsi else '',
                    str(imo) if imo else '',
                    str(baujahr) if baujahr else '',
                    str(laenge) if laenge else '',
                    str(breite) if breite else ''
                ]
                
                # Update Spalten C-G (ohne B) - neue API: values first, dann range_name
                worksheet.update(values=[update_data], range_name=f'C{row_idx}:G{row_idx}')
                
                # Update Spalte I (Link) nur wenn leer
                if not existing_link and vf_link:
                    worksheet.update(values=[[str(vf_link)]], range_name=f'I{row_idx}')
                
                log_info(f"    ✓ Sheet aktualisiert: Zeile {row_idx}")
                return True
        
        log_warning(f"    ⚠️  Schiff nicht im Sheet gefunden: {vessel_name}")
        return False
        
    except Exception as e:
        log_error(f"    ✗ Fehler beim Sheet-Update: {e}")
        return False

def mark_vessel_as_no_data(vessel_name: str, worksheet):
    """
    Markiert ein Schiff mit "Keine Daten" oder "Keine Daten 2" in Spalte C.
    Wenn bereits "Keine Daten" drin steht, wird es zu "Keine Daten 2" geändert.
    Wenn leer, wird "Keine Daten" geschrieben.
    
    Args:
        vessel_name: Name des Schiffs
        worksheet: Google Sheets Worksheet-Objekt
    """
    try:
        # Finde die Zeile mit diesem Schiffsnamen
        all_values = worksheet.get_all_values()
        
        for row_idx, row in enumerate(all_values[1:], start=2):
            if not row or not row[0].strip():
                continue
            
            if row[0].strip() == vessel_name:
                # Erweitere Row auf 9 Spalten falls nötig
                while len(row) < 9:
                    row.append('')
                
                # Prüfe aktuellen Wert in Spalte C
                current_value = row[2].strip() if len(row) > 2 else ''
                
                # Wenn bereits "Keine Daten" → schreibe "Keine Daten 2"
                if current_value == "Keine Daten":
                    worksheet.update(values=[["Keine Daten 2"]], range_name=f'C{row_idx}')
                    log_info(f"    ✓ 'Keine Daten 2' in Spalte C geschrieben (Zeile {row_idx})")
                # Wenn leer oder etwas anderes → schreibe "Keine Daten"
                else:
                    worksheet.update(values=[["Keine Daten"]], range_name=f'C{row_idx}')
                    log_info(f"    ✓ 'Keine Daten' in Spalte C geschrieben (Zeile {row_idx})")
                return True
        
        return False
        
    except Exception as e:
        log_error(f"    ✗ Fehler beim Markieren: {e}")
        return False

def get_vessels_without_data_from_sheet(gs_connector):
    """
    Holt AKTUELL alle Schiffe aus dem Sheet, die noch Daten brauchen
    
    Args:
        gs_connector: GoogleSheetsConnector-Instanz
        
    Returns:
        Liste von Schiffsnamen ohne Daten
    """
    try:
        worksheet = gs_connector.sh.worksheet("Schiffsdaten HHLA")
        all_data = worksheet.get_all_values()
        
        if len(all_data) < 2:
            return []
        
        vessels_without_data = []
        
        for row_idx, row in enumerate(all_data[1:], start=2):
            if not row or not row[0].strip():
                continue
            
            vessel_name = row[0].strip()
            
            # Erweitere Row auf 9 Spalten falls nötig
            while len(row) < 9:
                row.append('')
            
            # Prüfe ob wichtige Daten fehlen
            has_mmsi = row[2].strip() if len(row) > 2 else ''
            has_imo = row[3].strip() if len(row) > 3 else ''
            has_laenge = row[5].strip() if len(row) > 5 else ''
            
            # Wenn "Keine Daten" oder "Keine Daten 2" → nicht nochmal versuchen
            if has_mmsi == "Keine Daten" or has_mmsi == "Keine Daten 2":
                continue
            
            # Wenn mindestens eines fehlt → braucht Daten
            if not all([has_imo, has_laenge]):
                vessels_without_data.append(vessel_name)
        
        return vessels_without_data
        
    except Exception as e:
        log_error(f"Fehler beim Lesen der Schiffe ohne Daten: {e}")
        return []

def sync_database_with_sheet(db: SchiffsDatenbank):
    """
    Synchronisiert die Datenbank mit dem Google Sheet.
    Importiert manuell eingetragene Daten aus dem Sheet in die Datenbank.
    """
    if not SHEETS_AVAILABLE:
        return
    
    log_info("🔄 Synchronisiere Datenbank mit Google Sheet...")
    
    try:
        gs = GoogleSheetsConnector(SERVICE_ACCOUNT_FILE, SPREADSHEET_URL)
        gs.connect()
        
        worksheet = gs.sh.worksheet("Schiffsdaten HHLA")
        all_data = worksheet.get_all_values()
        
        if len(all_data) < 2:
            log_info("  → Keine Daten im Sheet")
            return
        
        db.connect()
        imported_count = 0
        updated_count = 0
        
        for row_idx, row in enumerate(all_data[1:], start=2):
            if not row or not row[0].strip():
                continue
            
            vessel_name = row[0].strip()
            
            # Erweitere auf 9 Spalten
            while len(row) < 9:
                row.append('')
            
            # Lese Daten aus Sheet (ohne Spalte B/Typ)
            mmsi = row[2].strip() if len(row) > 2 else ''
            imo = row[3].strip() if len(row) > 3 else ''
            baujahr_str = row[4].strip() if len(row) > 4 else ''
            laenge_str = row[5].strip() if len(row) > 5 else ''
            breite_str = row[6].strip() if len(row) > 6 else ''
            link = row[8].strip() if len(row) > 8 else ''
            
            # Überspringe "Keine Daten" Einträge
            if mmsi == "Keine Daten":
                continue
            
            # Prüfe ob Sheet überhaupt irgendwelche Daten hat
            if not any([mmsi, imo, laenge_str, breite_str, baujahr_str, link]):
                continue  # Komplett leer, überspringe
            
            # Konvertiere zu Zahlen
            try:
                baujahr = int(baujahr_str) if baujahr_str else None
            except:
                baujahr = None
            
            try:
                laenge = float(laenge_str) if laenge_str else None
            except:
                laenge = None
            
            try:
                breite = float(breite_str) if breite_str else None
            except:
                breite = None
            
            # Prüfe ob Schiff in DB existiert
            db.cursor.execute("SELECT id, mmsi_nummer, imo_nummer FROM schiffe WHERE name = ?", (vessel_name,))
            result = db.cursor.fetchone()
            
            if result:
                # Update wenn Sheet neuere Daten hat
                ship_id, db_mmsi, db_imo = result
                if not db_mmsi or not db_imo:
                    db.add_ship(
                        name=vessel_name,
                        mmsi_nummer=mmsi,
                        imo_nummer=imo,
                        baujahr=baujahr,
                        laenge=laenge,
                        breite=breite,
                        vesselfinder_link=link
                    )
                    updated_count += 1
            else:
                # Neu in DB einfügen
                db.add_ship(
                    name=vessel_name,
                    mmsi_nummer=mmsi,
                    imo_nummer=imo,
                    baujahr=baujahr,
                    laenge=laenge,
                    breite=breite,
                    vesselfinder_link=link
                )
                imported_count += 1
        
        db.conn.commit()
        db.disconnect()
        
        if imported_count > 0 or updated_count > 0:
            log_info(f"  ✓ {imported_count} neue Schiffe importiert, {updated_count} aktualisiert")
        else:
            log_info(f"  ✓ Datenbank ist aktuell")
        
    except Exception as e:
        log_error(f"  ✗ Fehler beim Sync: {e}")

def sync_schiffsdaten(db: SchiffsDatenbank):
    """
    Synchronisiert Schiffe aus Segelliste mit Schiffsdaten HHLA (wie Google Apps Script).
    - Liest Schiffsnamen aus Segelliste Spalte E
    - Vergleicht mit Schiffsdaten HHLA Spalte A
    - Fügt neue Schiffe alphabetisch sortiert hinzu
    - Schreibt Schiffstyp aus Segelliste Spalte N in Schiffsdaten HHLA Spalte B
    - Entfernt Duplikate
    """
    if not SHEETS_AVAILABLE:
        log_error("✗ Google Sheets-Bibliotheken nicht verfügbar")
        return
    
    log_header("Synchronisiere Schiffsdaten: Segelliste → Schiffsdaten HHLA")
    
    try:
        gs = GoogleSheetsConnector(SERVICE_ACCOUNT_FILE, SPREADSHEET_URL)
        gs.connect()
        
        # Lese Segelliste
        segelliste_ws = gs.sh.worksheet("Segelliste")
        segelliste_data = segelliste_ws.get_all_values()
        
        if len(segelliste_data) < 2:
            log_warning("  ⚠️  Keine Daten in Segelliste gefunden")
            return
        
        # Map für Schiffsname -> Schiffstyp aus Segelliste (Spalte E=Index 4, Spalte N=Index 13)
        segelliste_map = {}
        for i in range(1, len(segelliste_data)):  # Header überspringen
            if len(segelliste_data[i]) > 13:
                ship_name = segelliste_data[i][4].strip() if len(segelliste_data[i]) > 4 else ''
                ship_type = segelliste_data[i][13].strip() if len(segelliste_data[i]) > 13 else ''
                if ship_name:
                    name_upper = ship_name.upper()
                    if name_upper not in segelliste_map or not segelliste_map[name_upper]:
                        segelliste_map[name_upper] = ship_type
        
        log_info(f"  ✓ {len(segelliste_map)} Schiffe in Segelliste gefunden")
        
        # Lese Schiffsdaten HHLA
        try:
            hhla_ws = gs.sh.worksheet("Schiffsdaten HHLA")
        except gspread.WorksheetNotFound:
            # Erstelle neues Blatt
            hhla_ws = gs.sh.add_worksheet(title="Schiffsdaten HHLA", rows="1000", cols="9")
            headers = [['Schiffsname', 'Schiffstyp', 'MMSI-Nummer', 'IMO-Nummer', 
                       'Baujahr', 'Länge (m)', 'Breite (m)', '', 'VesselFinder-Link']]
            hhla_ws.update('A1:I1', headers)
            hhla_ws.format('A1:I1', {'textFormat': {'bold': True}})
            log_info("  ✓ Neues Blatt 'Schiffsdaten HHLA' erstellt")
        
        hhla_data = hhla_ws.get_all_values()
        
        # Map für vorhandene Schiffe
        existing_ships = {}
        duplicate_rows = []
        
        for i in range(1, len(hhla_data)):  # Header überspringen
            if len(hhla_data[i]) > 0 and hhla_data[i][0].strip():
                name_upper = hhla_data[i][0].strip().upper()
                if name_upper in existing_ships:
                    duplicate_rows.append(i + 1)  # 1-basierte Zeilennummer
                    log_info(f"  ⚠️  Duplikat gefunden: {name_upper} in Zeile {i + 1}")
                else:
                    # Erweitere auf 9 Spalten
                    row_data = hhla_data[i] + [''] * (9 - len(hhla_data[i]))
                    existing_ships[name_upper] = {
                        'data': row_data[:9],
                        'row': i + 1
                    }
        
        # Lösche Duplikate (von hinten nach vorne)
        if duplicate_rows:
            duplicate_rows.sort(reverse=True)
            for row_num in duplicate_rows:
                hhla_ws.delete_rows(row_num)
            log_info(f"  ✓ {len(duplicate_rows)} Duplikate gelöscht")
            # Daten neu lesen
            hhla_data = hhla_ws.get_all_values()
            existing_ships = {}
            for i in range(1, len(hhla_data)):
                if len(hhla_data[i]) > 0 and hhla_data[i][0].strip():
                    name_upper = hhla_data[i][0].strip().upper()
                    row_data = hhla_data[i] + [''] * (9 - len(hhla_data[i]))
                    existing_ships[name_upper] = {
                        'data': row_data[:9],
                        'row': i + 1
                    }
        
        log_info(f"  ✓ {len(existing_ships)} Schiffe in Schiffsdaten HHLA gefunden")
        
        # Finde neue Schiffe und Updates
        new_ships = []
        updates = []
        
        for name_upper, ship_type in segelliste_map.items():
            if name_upper in existing_ships:
                # Prüfe ob Schiffstyp aktualisiert werden muss
                current_type = existing_ships[name_upper]['data'][1].strip() if len(existing_ships[name_upper]['data']) > 1 else ''
                if ship_type and ship_type != current_type:
                    updates.append({
                        'name': name_upper,
                        'type': ship_type,
                        'row': existing_ships[name_upper]['row']
                    })
            else:
                # Neues Schiff
                new_ships.append({
                    'name': name_upper,
                    'type': ship_type
                })
        
        log_info(f"  ✓ {len(new_ships)} neue Schiffe gefunden")
        log_info(f"  ✓ {len(updates)} Schiffstyp-Updates gefunden")
        
        # Erstelle sortierte Liste aller Schiffe
        all_ships = []
        added_names = set()
        
        # Bestehende Schiffe
        for name_upper, ship_info in existing_ships.items():
            if name_upper not in added_names:
                all_ships.append({
                    'name': name_upper,
                    'data': ship_info['data'],
                    'row': ship_info['row']
                })
                added_names.add(name_upper)
        
        # Neue Schiffe
        for new_ship in new_ships:
            if new_ship['name'] not in added_names:
                all_ships.append({
                    'name': new_ship['name'],
                    'data': [
                        new_ship['name'],  # A: Schiffsname
                        new_ship['type'],  # B: Schiffstyp
                        '',  # C: MMSI-Nummer
                        '',  # D: IMO-Nummer
                        '',  # E: Baujahr
                        '',  # F: Länge (m)
                        '',  # G: Breite (m)
                        '',  # H: (leer)
                        ''   # I: VesselFinder-Link
                    ],
                    'row': None
                })
                added_names.add(new_ship['name'])
        
        # Alphabetisch sortieren
        all_ships.sort(key=lambda x: x['name'])
        
        # Updates anwenden
        updates_map = {u['name']: u['type'] for u in updates}
        for ship in all_ships:
            if ship['name'] in updates_map:
                ship['data'][1] = updates_map[ship['name']]
        
        # Neue Zeilen einfügen (von hinten nach vorne)
        insert_positions = []
        for i, ship in enumerate(all_ships):
            if ship['row'] is None:
                insert_positions.append(i + 2)  # Zielzeile (1-basiert, +1 für Header)
        
        if insert_positions:
            insert_positions.sort(reverse=True)
            for pos in insert_positions:
                hhla_ws.insert_row([''] * 9, pos)
            log_info(f"  ✓ {len(insert_positions)} neue Zeilen eingefügt")
        
        # Schreibe alle Daten auf einmal
        sorted_data = [ship['data'] for ship in all_ships]
        if sorted_data:
            last_row = len(hhla_data)
            if last_row > 1:
                # Lösche alte Daten (nur Inhalt)
                hhla_ws.batch_clear([f'A2:I{last_row}'])
            
            # Schreibe neue Daten
            hhla_ws.update(f'A2:I{len(sorted_data) + 1}', sorted_data)
            log_info(f"  ✓ {len(sorted_data)} Schiffe (alphabetisch sortiert) geschrieben")
            
            # Lösche überflüssige Zeilen
            new_last_row = len(sorted_data) + 1
            if last_row > new_last_row:
                hhla_ws.delete_rows(new_last_row + 1, last_row - new_last_row)
        
        # Prüfe Schiffe mit "Keine Daten" in Spalte C und suche sie nochmal
        log_info("  🔍 Prüfe Schiffe mit 'Keine Daten' in Spalte C...")
        ships_to_research = []
        
        for i, ship in enumerate(all_ships):
            if len(ship['data']) > 2 and ship['data'][2].strip() == "Keine Daten":
                ships_to_research.append({
                    'name': ship['name'],
                    'row': i + 2,  # Zeile im Sheet (1-basiert, +1 für Header)
                    'data': ship['data']
                })
        
        if ships_to_research:
            log_info(f"  ✓ {len(ships_to_research)} Schiffe mit 'Keine Daten' gefunden - suche nochmal...")
            
            if SELENIUM_AVAILABLE:
                scraper = VesselFinderScraper(headless=True, take_screenshots=False)
                
                for ship_info in ships_to_research:
                    vessel_name = ship_info['name']
                    row_num = ship_info['row']
                    
                    log_info(f"    🔍 Suche erneut: {vessel_name} (Zeile {row_num})")
                    
                    try:
                        # Suche Schiff auf VesselFinder
                        vessel_data = scraper.search_vessel(vessel_name)
                        
                        if vessel_data and vessel_data.get('mmsi'):
                            # Daten gefunden - aktualisiere Sheet
                            log_info(f"      ✓ Daten gefunden für {vessel_name}")
                            
                            # Aktualisiere die Daten
                            ship_info['data'][2] = vessel_data.get('mmsi', '')  # C: MMSI
                            ship_info['data'][3] = vessel_data.get('imo', '')  # D: IMO
                            ship_info['data'][4] = str(vessel_data.get('baujahr', '')) if vessel_data.get('baujahr') else ''  # E: Baujahr
                            ship_info['data'][5] = str(vessel_data.get('laenge', '')) if vessel_data.get('laenge') else ''  # F: Länge
                            ship_info['data'][6] = str(vessel_data.get('breite', '')) if vessel_data.get('breite') else ''  # G: Breite
                            ship_info['data'][8] = vessel_data.get('link', '')  # I: VesselFinder-Link
                            
                            # Schreibe aktualisierte Daten ins Sheet
                            hhla_ws.update(f'A{row_num}:I{row_num}', [ship_info['data']])
                            log_info(f"      ✓ Daten für {vessel_name} aktualisiert")
                            
                            # Warte zwischen Anfragen
                            time.sleep(3)
                        else:
                            # Keine Daten gefunden - schreibe "Keine Daten 2"
                            log_warning(f"      ✗ Keine Daten gefunden für {vessel_name} - schreibe 'Keine Daten 2'")
                            ship_info['data'][2] = "Keine Daten 2"
                            hhla_ws.update(f'C{row_num}', [["Keine Daten 2"]])
                            log_info(f"      ✓ 'Keine Daten 2' für {vessel_name} geschrieben")
                            
                    except Exception as e:
                        log_error(f"      ✗ Fehler beim Suchen von {vessel_name}: {e}")
                        # Schreibe "Keine Daten 2" bei Fehler
                        ship_info['data'][2] = "Keine Daten 2"
                        hhla_ws.update(f'C{row_num}', [["Keine Daten 2"]])
                        log_info(f"      ✓ 'Keine Daten 2' für {vessel_name} geschrieben (Fehler)")
                    
                    # Warte zwischen Anfragen
                    time.sleep(3)
                
                # Schließe Browser
                scraper.cleanup()
                log_info(f"  ✓ {len(ships_to_research)} Schiffe erneut durchsucht")
            else:
                log_warning("  ⚠️  Selenium nicht verfügbar - kann Schiffe nicht erneut suchen")
        else:
            log_info("  ✓ Keine Schiffe mit 'Keine Daten' gefunden")
        
        log_info("  ✓ Synchronisation abgeschlossen")
        
    except Exception as e:
        log_error(f"  ✗ Fehler bei Synchronisation: {e}")
        import traceback
        traceback.print_exc()

def search_keine_daten(db: SchiffsDatenbank):
    """
    Sucht alle Schiffe mit "Keine Daten" in Spalte C nochmal über VesselFinder.
    """
    if not SHEETS_AVAILABLE:
        log_error("✗ Google Sheets-Bibliotheken nicht verfügbar")
        return
    
    if not SELENIUM_AVAILABLE:
        log_error("✗ Selenium nicht verfügbar. Installiere mit: pip install selenium webdriver-manager")
        return
    
    log_header("Suche Schiffe mit 'Keine Daten' erneut")
    
    try:
        gs = GoogleSheetsConnector(SERVICE_ACCOUNT_FILE, SPREADSHEET_URL)
        gs.connect()
        
        # Lese Schiffsdaten HHLA
        try:
            hhla_ws = gs.sh.worksheet("Schiffsdaten HHLA")
        except gspread.WorksheetNotFound:
            log_error("✗ Blatt 'Schiffsdaten HHLA' nicht gefunden")
            return
        
        hhla_data = hhla_ws.get_all_values()
        
        if len(hhla_data) < 2:
            log_warning("  ⚠️  Keine Daten im Sheet gefunden")
            return
        
        # Finde Schiffe mit "Keine Daten" in Spalte C
        ships_to_research = []
        
        for i in range(1, len(hhla_data)):  # Header überspringen
            if len(hhla_data[i]) > 2:
                ship_name = hhla_data[i][0].strip() if len(hhla_data[i]) > 0 else ''
                mmsi = hhla_data[i][2].strip() if len(hhla_data[i]) > 2 else ''
                
                if ship_name and mmsi == "Keine Daten":
                    # Erweitere auf 9 Spalten
                    row_data = hhla_data[i] + [''] * (9 - len(hhla_data[i]))
                    ships_to_research.append({
                        'name': ship_name,
                        'row': i + 1,  # Zeile im Sheet (1-basiert)
                        'data': row_data[:9]
                    })
        
        if not ships_to_research:
            log_info("  ✓ Keine Schiffe mit 'Keine Daten' gefunden")
            return
        
        log_info(f"  ✓ {len(ships_to_research)} Schiffe mit 'Keine Daten' gefunden")
        log_info("  🔍 Suche diese Schiffe nochmal über VesselFinder...")
        
        scraper = VesselFinderScraper(headless=True, take_screenshots=False)
        
        found_count = 0
        not_found_count = 0
        
        for ship_info in ships_to_research:
            vessel_name = ship_info['name']
            row_num = ship_info['row']
            
            log_info(f"    🔍 Suche: {vessel_name} (Zeile {row_num})")
            
            try:
                # Suche Schiff auf VesselFinder
                vessel_data = scraper.search_vessel(vessel_name)
                
                if vessel_data and vessel_data.get('mmsi'):
                    # Daten gefunden - aktualisiere Sheet
                    log_info(f"      ✓ Daten gefunden für {vessel_name}")
                    
                    # Aktualisiere die Daten
                    ship_info['data'][2] = vessel_data.get('mmsi', '')  # C: MMSI
                    ship_info['data'][3] = vessel_data.get('imo', '')  # D: IMO
                    ship_info['data'][4] = str(vessel_data.get('baujahr', '')) if vessel_data.get('baujahr') else ''  # E: Baujahr
                    ship_info['data'][5] = str(vessel_data.get('laenge', '')) if vessel_data.get('laenge') else ''  # F: Länge
                    ship_info['data'][6] = str(vessel_data.get('breite', '')) if vessel_data.get('breite') else ''  # G: Breite
                    ship_info['data'][8] = vessel_data.get('link', '')  # I: VesselFinder-Link
                    
                    # Schreibe aktualisierte Daten ins Sheet
                    hhla_ws.update(f'A{row_num}:I{row_num}', [ship_info['data']])
                    log_info(f"      ✓ Daten für {vessel_name} aktualisiert")
                    found_count += 1
                    
                else:
                    # Keine Daten gefunden - schreibe "Keine Daten 2"
                    log_warning(f"      ✗ Keine Daten gefunden für {vessel_name} - schreibe 'Keine Daten 2'")
                    ship_info['data'][2] = "Keine Daten 2"
                    hhla_ws.update(f'C{row_num}', [["Keine Daten 2"]])
                    log_info(f"      ✓ 'Keine Daten 2' für {vessel_name} geschrieben")
                    not_found_count += 1
                    
            except Exception as e:
                log_error(f"      ✗ Fehler beim Suchen von {vessel_name}: {e}")
                # Schreibe "Keine Daten 2" bei Fehler
                ship_info['data'][2] = "Keine Daten 2"
                hhla_ws.update(f'C{row_num}', [["Keine Daten 2"]])
                log_info(f"      ✓ 'Keine Daten 2' für {vessel_name} geschrieben (Fehler)")
                not_found_count += 1
            
            # Warte zwischen Anfragen
            time.sleep(3)
        
        # Schließe Browser
        scraper.cleanup()
        
        log_info(f"  ✓ Suche abgeschlossen:")
        log_info(f"    → {found_count} Schiffe mit Daten gefunden")
        log_info(f"    → {not_found_count} Schiffe ohne Daten (→ 'Keine Daten 2')")
        
    except Exception as e:
        log_error(f"  ✗ Fehler bei Suche: {e}")
        import traceback
        traceback.print_exc()

def import_from_vesselfinder(db: SchiffsDatenbank, vessel_names: List[str] = None, 
                              from_sheet: bool = False, delay: float = 5.0,
                              max_consecutive_errors: int = 25, headless: bool = True,
                              max_ships: int = None, skip_ships: int = 0,
                              live_update: bool = False):
    """
    Importiert Schiffsdaten von shipfinder.com
    
    Args:
        db: Datenbank-Instanz
        vessel_names: Liste von Schiffsnamen (optional)
        from_sheet: Wenn True, liest Namen aus Google Sheet "Schiffsdaten HHLA"
        delay: Wartezeit zwischen Anfragen in Sekunden (um Server nicht zu überlasten)
        max_consecutive_errors: Maximale Anzahl aufeinanderfolgender Fehler vor Abbruch (Standard: 25)
        headless: Wenn False, wird Browser sichtbar gestartet (Standard: False für bessere Kompatibilität)
        max_ships: Maximale Anzahl zu verarbeitender Schiffe (None = alle)
        skip_ships: Anzahl der zu überspringenden Schiffe am Anfang (Standard: 0)
        live_update: Wenn True, wird jedes Schiff sofort ins Sheet geschrieben (Standard: False)
    """
    if not SELENIUM_AVAILABLE:
        log_error("✗ Selenium nicht verfügbar. Installiere mit: pip install selenium webdriver-manager")
        return
    
    log_header("Import von shipfinder.com")
    
    # Für Live-Update: Sheet-Verbindung offen halten
    gs_worksheet = None
    gs_conn = None
    if live_update and SHEETS_AVAILABLE:
        try:
            log_info("Öffne Google Sheet für Live-Updates...")
            gs_conn = GoogleSheetsConnector(SERVICE_ACCOUNT_FILE, SPREADSHEET_URL)
            gs_conn.connect()
            gs_worksheet = gs_conn.sh.worksheet("Schiffsdaten HHLA")
            log_info("  ✓ Sheet bereit für Live-Updates")
        except Exception as e:
            log_warning(f"  ⚠️  Konnte Sheet nicht öffnen: {e}")
            log_warning(f"  ⚠️  Live-Updates deaktiviert")
            gs_worksheet = None
            gs_conn = None
    
    # Hole Schiffsnamen
    if from_sheet:
        if not SHEETS_AVAILABLE:
            log_error("✗ Google Sheets-Funktionen nicht verfügbar")
            return
        
        log_info("Lese Schiffsnamen aus Google Sheet 'Schiffsdaten HHLA'...")
        try:
            gs = GoogleSheetsConnector(SERVICE_ACCOUNT_FILE, SPREADSHEET_URL)
            gs.connect()
            
            try:
                worksheet = gs.sh.worksheet("Schiffsdaten HHLA")
                
                # Lese alle Daten (nicht nur Spalte A)
                all_data = worksheet.get_all_values()
                
                if len(all_data) < 2:
                    print("✗ Keine Daten im Sheet gefunden")
                    return
                
                # Sammle alle Schiffe, die KEINE vollständigen Daten haben
                vessels_without_data = []
                vessels_with_data = []
                
                for row_idx, row in enumerate(all_data[1:], start=2):  # Überspringe Header
                    if not row or not row[0].strip():
                        continue
                    
                    vessel_name = row[0].strip()
                    
                    # Erweitere Row auf 9 Spalten falls nötig
                    while len(row) < 9:
                        row.append('')
                    
                    # Prüfe ob wichtige Daten fehlen (Spalten C-G, ohne B/Typ)
                    # C=MMSI, D=IMO, E=Jahr, F=Länge, G=Breite
                    has_mmsi = row[2].strip() if len(row) > 2 else ''
                    has_imo = row[3].strip() if len(row) > 3 else ''
                    has_jahr = row[4].strip() if len(row) > 4 else ''
                    has_laenge = row[5].strip() if len(row) > 5 else ''
                    has_breite = row[6].strip() if len(row) > 6 else ''
                    
                    # Wenn "Keine Daten" oder "Keine Daten 2" → überspringe (wurde schon 3x versucht)
                    if has_mmsi == "Keine Daten" or has_mmsi == "Keine Daten 2":
                        continue
                    
                    # Wenn MINDESTENS ein wichtiges Feld leer ist, braucht das Schiff Daten
                    if not all([has_imo, has_laenge]):
                        vessels_without_data.append(vessel_name)
                    else:
                        vessels_with_data.append(vessel_name)
                
                print(f"✓ {len(all_data)-1} Schiffe insgesamt im Sheet")
                print(f"  → {len(vessels_with_data)} Schiffe haben bereits Daten")
                print(f"  → {len(vessels_without_data)} Schiffe brauchen noch Daten")
                
                # Verwende nur Schiffe ohne Daten
                all_vessel_names = vessels_without_data
                
                if not all_vessel_names:
                    print("✓ Alle Schiffe haben bereits Daten - nichts zu tun!")
                    return
                
                # Überspringe die ersten skip_ships Schiffe (aus der Liste der Schiffe ohne Daten)
                if skip_ships > 0:
                    vessel_names = all_vessel_names[skip_ships:]
                    print(f"  → Überspringe die ersten {skip_ships} Schiffe (ohne Daten)")
                else:
                    vessel_names = all_vessel_names
                
                # Begrenze auf max_ships, falls angegeben
                if max_ships and max_ships > 0:
                    vessel_names = vessel_names[:max_ships]
                    start_index = skip_ships + 1
                    end_index = skip_ships + len(vessel_names)
                    print(f"  → Verarbeite Schiffe {start_index}-{end_index} aus den Schiffen ohne Daten ({len(vessel_names)} Schiffe)")
                else:
                    if skip_ships > 0:
                        print(f"  → Verarbeite alle ab Schiff {skip_ships + 1} (ohne Daten)")
                
            except gspread.WorksheetNotFound:
                print("✗ Blatt 'Schiffsdaten HHLA' nicht gefunden")
                return
                
        except Exception as e:
            print(f"✗ Fehler beim Lesen des Sheets: {e}")
            return
    
    elif not vessel_names:
        print("✗ Keine Schiffsnamen angegeben. Verwende --from-sheet oder gib Namen an.")
        return
    else:
        # Nur für manuell angegebene Schiffe (--vessels): Überspringe und begrenze
        original_count = len(vessel_names)
        
        if skip_ships > 0:
            vessel_names = vessel_names[skip_ships:]
            log_info(f"⚠️  Überspringe die ersten {skip_ships} Schiffe")
        
        if max_ships and max_ships > 0:
            vessel_names = vessel_names[:max_ships]
            start_index = skip_ships + 1
            end_index = skip_ships + len(vessel_names)
            log_info(f"⚠️  Verarbeite Schiffe {start_index}-{end_index} von insgesamt {original_count}")
    
    if not vessel_names:
        print("Keine Schiffsnamen zum Verarbeiten")
        return
    
    log_info(f"Verarbeite {len(vessel_names)} Schiffe...")
    if max_ships and max_ships > 0:
        log_info(f"⚠️  Begrenzt auf die ersten {max_ships} Schiffe")
    log_info(f"Wartezeit zwischen Anfragen: {delay}s")
    log_info(f"Automatischer Abbruch nach {max_consecutive_errors} aufeinanderfolgenden Fehlern")
    log_info(f"Je Schiff: 3 Versuche\n")
    
    # Starte Scraper
    success_count = 0
    error_count = 0
    consecutive_errors = 0  # Zähler für aufeinanderfolgende Fehler
    successful_ships = []  # Liste der erfolgreichen Schiffe mit Details
    failed_ships = []  # Liste der fehlgeschlagenen Schiffe
    
    try:
        # Screenshots nur bei Fehlern (deaktiviert für normale Schiffe)
        take_screenshots = False
        log_info(f"Browser-Modus: {'Headless (unsichtbar)' if headless else 'Sichtbar'}")
        with VesselFinderScraper(headless=headless, take_screenshots=take_screenshots) as scraper:
            
            # Bei live_update: Endlos-Schleife, prüft immer welche Schiffe noch fehlen
            if live_update and gs_worksheet and from_sheet:
                log_info("🔄 Live-Modus: Prüfe kontinuierlich welche Schiffe Daten brauchen")
                log_info("   Strg+C zum Beenden\n")
                
                processed_in_this_run = set()  # Schiffe die in diesem Durchlauf verarbeitet wurden
                total_processed = 0
                
                while True:
                    # Hole AKTUELL die Schiffe ohne Daten aus dem Sheet
                    current_vessels_without_data = get_vessels_without_data_from_sheet(gs_conn)
                    
                    # Filtere: Nur Schiffe die noch nicht in diesem Durchlauf verarbeitet wurden
                    vessels_to_process = [v for v in current_vessels_without_data if v not in processed_in_this_run]
                    
                    if not vessels_to_process:
                        log_info("\n✅ Alle Schiffe haben Daten! Fertig.")
                        break
                    
                    # Nimm das erste Schiff
                    vessel_name = vessels_to_process[0]
                    total_processed += 1
                    
                    log_info(f"[{total_processed}] {vessel_name} ({len(vessels_to_process)} noch ohne Daten)")
                    
                    # 3 Versuche pro Schiff
                    vessel_data = None
                    has_important_data = False
                    
                    for attempt in range(1, 4):  # 3 Versuche
                        try:
                            # Hole Daten von VesselFinder
                            vessel_data = scraper.search_vessel(vessel_name)
                            
                            # Prüfe ob WICHTIGE Daten vorhanden sind (IMO oder Länge)
                            if vessel_data and (vessel_data.get('imo_nummer') or vessel_data.get('laenge')):
                                has_important_data = True
                                
                                # Erfolgreich! Speichere in Datenbank
                                db.add_ship(
                                    name=vessel_data.get('name') or vessel_name,
                                    laenge=vessel_data.get('laenge'),
                                    breite=vessel_data.get('breite'),
                                    imo_nummer=vessel_data.get('imo_nummer'),
                                    mmsi_nummer=vessel_data.get('mmsi_nummer'),
                                    baujahr=vessel_data.get('baujahr'),
                                    typ=vessel_data.get('typ'),
                                    flagge=vessel_data.get('flagge'),
                                    vesselfinder_link=vessel_data.get('vesselfinder_link')
                                )
                                success_count += 1
                                consecutive_errors = 0
                                processed_in_this_run.add(vessel_name)
                                
                                # Speichere Details für Zusammenfassung
                                ship_details = {
                                    'name': vessel_name,
                                    'imo': vessel_data.get('imo_nummer', ''),
                                    'mmsi': vessel_data.get('mmsi_nummer', ''),
                                    'laenge': vessel_data.get('laenge', ''),
                                    'breite': vessel_data.get('breite', '')
                                }
                                successful_ships.append(ship_details)
                                
                                # Zeige gefundene Daten besser formatiert
                                log_info(f"    ✓ Daten gefunden:")
                                if ship_details['imo']:
                                    log_info(f"        ✓ IMO: {ship_details['imo']}")
                                if ship_details['mmsi']:
                                    log_info(f"        ✓ MMSI: {ship_details['mmsi']}")
                                if ship_details['laenge']:
                                    log_info(f"        ✓ Länge: {ship_details['laenge']}m")
                                if ship_details['breite']:
                                    log_info(f"        ✓ Breite: {ship_details['breite']}m")
                                
                                # Schreibe sofort ins Sheet
                                log_info(f"    → Schreibe ins Google Sheet...")
                                update_single_ship_in_sheet(vessel_name, vessel_data, gs_worksheet)
                                break  # Erfolgreich, keine weiteren Versuche nötig
                            else:
                                # Keine wichtigen Daten gefunden
                                log_warning(f"    ⚠️  Keine Daten {attempt}")
                                vessel_data = None  # Reset für nächsten Versuch
                                
                                # Warte vor nächstem Versuch (außer beim letzten)
                                if attempt < 3:
                                    time.sleep(2)
                        
                        except Exception as e:
                            log_warning(f"    ⚠️  Fehler bei Versuch {attempt}: {e}")
                            if attempt < 3:
                                time.sleep(2)
                    
                    # Nach 3 Versuchen ohne wichtige Daten
                    if not has_important_data:
                        error_count += 1
                        consecutive_errors += 1
                        processed_in_this_run.add(vessel_name)  # Als verarbeitet markieren
                        failed_ships.append(vessel_name)
                        log_error(f"    ✗ Schiff nach 3 Versuchen übersprungen")
                        
                        # Schreibe "Keine Daten" in Spalte C
                        log_info(f"    → Schreibe 'Keine Daten' in Spalte C...")
                        mark_vessel_as_no_data(vessel_name, gs_worksheet)
                        
                        # Prüfe Abbruchbedingung
                        if consecutive_errors >= max_consecutive_errors:
                            log_error(f"\n⚠️  ABBRUCH: {max_consecutive_errors} Schiffe hintereinander nicht gefunden!")
                            break
                    
                    # Wartezeit zwischen Schiffen
                    time.sleep(delay)
                
            else:
                # Normale Verarbeitung ohne live_update
                for i, vessel_name in enumerate(vessel_names, 1):
                    log_info(f"[{i}/{len(vessel_names)}] {vessel_name}")
                    
                    try:
                        # Hole Daten von VesselFinder
                        vessel_data = scraper.search_vessel(vessel_name)
                        
                        if vessel_data and (vessel_data.get('imo_nummer') or vessel_data.get('laenge')):
                            # Speichere in Datenbank
                            db.add_ship(
                                name=vessel_data.get('name') or vessel_name,
                                laenge=vessel_data.get('laenge'),
                                breite=vessel_data.get('breite'),
                                imo_nummer=vessel_data.get('imo_nummer'),
                                mmsi_nummer=vessel_data.get('mmsi_nummer'),
                                baujahr=vessel_data.get('baujahr'),
                                typ=vessel_data.get('typ'),
                                flagge=vessel_data.get('flagge'),
                                vesselfinder_link=vessel_data.get('vesselfinder_link')
                            )
                            success_count += 1
                            consecutive_errors = 0  # Zurücksetzen bei Erfolg
                            
                            # Speichere Details für Zusammenfassung
                            ship_details = {
                                'name': vessel_name,
                                'imo': vessel_data.get('imo_nummer', ''),
                                'mmsi': vessel_data.get('mmsi_nummer', ''),
                                'laenge': vessel_data.get('laenge', ''),
                                'breite': vessel_data.get('breite', '')
                            }
                            successful_ships.append(ship_details)
                            
                            # Zeige gefundene Daten besser formatiert
                            log_info(f"    ✓ Daten gefunden:")
                            if ship_details['imo']:
                                log_info(f"        ✓ IMO: {ship_details['imo']}")
                            if ship_details['mmsi']:
                                log_info(f"        ✓ MMSI: {ship_details['mmsi']}")
                            if ship_details['laenge']:
                                log_info(f"        ✓ Länge: {ship_details['laenge']}m")
                            if ship_details['breite']:
                                log_info(f"        ✓ Breite: {ship_details['breite']}m")
                            
                            # Live-Update: Schreibe sofort ins Sheet
                            if gs_worksheet:
                                log_info(f"    → Schreibe ins Google Sheet...")
                                update_single_ship_in_sheet(vessel_name, vessel_data, gs_worksheet)
                        else:
                            error_count += 1
                            consecutive_errors += 1
                            failed_ships.append(vessel_name)
                            log_warning(f"    Aufeinanderfolgende Fehler: {consecutive_errors}/{max_consecutive_errors}")
                            
                            # Prüfe Abbruchbedingung
                            if consecutive_errors >= max_consecutive_errors:
                                log_error(f"\n⚠️  ABBRUCH: {max_consecutive_errors} Schiffe hintereinander nicht gefunden!")
                                log_error(f"    Möglicherweise gibt es ein Problem mit der Website oder Verbindung.")
                                log_error(f"    Bisher erfolgreich: {success_count} von {i} Schiffen")
                                break
                        
                        # Wartezeit zwischen Anfragen
                        if i < len(vessel_names):
                            time.sleep(delay)
                            
                    except Exception as e:
                        log_error(f"    ✗ Fehler: {e}")
                        error_count += 1
                        consecutive_errors += 1
                        failed_ships.append(vessel_name)
                        
                        # Prüfe Abbruchbedingung auch bei Exceptions
                        if consecutive_errors >= max_consecutive_errors:
                            log_error(f"\n⚠️  ABBRUCH: {max_consecutive_errors} Fehler hintereinander!")
                            log_error(f"    Es gibt möglicherweise ein technisches Problem.")
                            log_error(f"    Bisher erfolgreich: {success_count} von {i} Schiffen")
                            break
                        
                        continue
        
        log_info("")
        log_info("="*70)
        if consecutive_errors >= max_consecutive_errors:
            log_warning(f"Import vorzeitig abgebrochen nach {max_consecutive_errors} aufeinanderfolgenden Fehlern")
        else:
            log_info("Import abgeschlossen")
        log_info("")
        log_info(f"  ✓ Erfolgreich: {success_count} Schiffe")
        log_info(f"  ✗ Fehler: {error_count} Schiffe")
        log_info(f"  📊 Verarbeitet: {success_count + error_count} von {len(vessel_names)} Schiffen")
        if consecutive_errors >= max_consecutive_errors:
            log_warning(f"  ⚠️  Verbleibend: {len(vessel_names) - (success_count + error_count)} Schiffe nicht verarbeitet")
        log_info("")
        log_info("-"*70)
        
        # Zeige erfolgreiche Schiffe mit Details
        if successful_ships:
            log_info(f"✓ SCHIFFE MIT DATEN GEFUNDEN ({len(successful_ships)}):")
            log_info("-"*70)
            for ship in successful_ships:
                details = []
                if ship['imo']:
                    details.append(f"IMO: {ship['imo']}")
                if ship['mmsi']:
                    details.append(f"MMSI: {ship['mmsi']}")
                if ship['laenge']:
                    details.append(f"Länge: {ship['laenge']}m")
                if ship['breite']:
                    details.append(f"Breite: {ship['breite']}m")
                log_info(f"  • {ship['name']}")
                if details:
                    log_info(f"    → {', '.join(details)}")
            log_info("")
        
        # Zeige fehlgeschlagene Schiffe
        if failed_ships:
            log_info(f"✗ SCHIFFE OHNE DATEN ({len(failed_ships)}):")
            log_info("-"*70)
            for ship_name in failed_ships:
                log_info(f"  • {ship_name}")
            log_info("")
        
        log_info("="*70)
        
        # Speichere Import-Historie
        db.connect()
        db.cursor.execute("""
            INSERT INTO import_historie (quelle, anzahl_datensaetze, status, bemerkung)
            VALUES (?, ?, ?, ?)
        """, ('VesselFinder.com', success_count, 
              'teilweise' if error_count > 0 else 'erfolg',
              f'{success_count} erfolgreich, {error_count} Fehler'))
        db.conn.commit()
        db.disconnect()
        
    except Exception as e:
        print(f"\n✗ Kritischer Fehler beim Import: {e}")
        import traceback
        traceback.print_exc()

def show_all_ships(db: SchiffsDatenbank):
    """
    Zeigt alle Schiffe aus der Datenbank an
    """
    print("\n=== Alle Schiffe ===")
    
    ships = db.get_all_ships()
    
    if not ships:
        print("Keine Schiffe in der Datenbank gefunden")
        return
    
    print(f"\nGefunden: {len(ships)} Schiffe\n")
    print(f"{'ID':<5} {'Name':<40} {'Länge':<10} {'Liegeort':<20} {'Status':<10}")
    print("-" * 90)
    
    for ship in ships:
        id_str = str(ship.get('id', ''))
        name = str(ship.get('name', ''))[:40]
        laenge = f"{ship.get('laenge', '')} m" if ship.get('laenge') else '-'
        liegeort = str(ship.get('liegeort', '') or '-')[:20]
        status = str(ship.get('status', '') or '-')[:10]
        
        print(f"{id_str:<5} {name:<40} {laenge:<10} {liegeort:<20} {status:<10}")

def show_statistics(db: SchiffsDatenbank):
    """
    Zeigt Statistiken über die Datenbank an
    """
    print("\n=== Datenbank-Statistiken ===")
    
    stats = db.get_statistics()
    
    print(f"\nGesamtanzahl Schiffe: {stats['total_ships']}")
    
    if stats.get('avg_length'):
        print(f"Durchschnittliche Länge: {stats['avg_length']} m")
    
    if stats.get('ships_by_location'):
        print("\nSchiffe nach Liegeort:")
        for location, count in stats['ships_by_location'].items():
            print(f"  {location}: {count} Schiffe")
    
    if stats.get('last_import'):
        imp = stats['last_import']
        print(f"\nLetzter Import:")
        print(f"  Zeitpunkt: {imp['time']}")
        print(f"  Quelle: {imp['source']}")
        print(f"  Datensätze: {imp['count']}")

def interactive_add_ship(db: SchiffsDatenbank):
    """
    Interaktiver Modus zum Hinzufügen eines neuen Schiffs
    """
    print("\n=== Neues Schiff hinzufügen ===\n")
    
    name = input("Schiffsname (erforderlich): ").strip()
    if not name:
        print("✗ Name ist erforderlich")
        return
    
    laenge_str = input("Länge in Metern (optional): ").strip()
    laenge = None
    if laenge_str:
        try:
            laenge = float(laenge_str.replace(",", "."))
        except ValueError:
            print("WARNUNG: Ungültige Längenangabe, wird übersprungen")
    
    breite_str = input("Breite in Metern (optional): ").strip()
    breite = None
    if breite_str:
        try:
            breite = float(breite_str.replace(",", "."))
        except ValueError:
            print("WARNUNG: Ungültige Breitenangabe, wird übersprungen")
    
    liegeort = input("Liegeort (optional): ").strip() or None
    typ = input("Schiffstyp (optional): ").strip() or None
    flagge = input("Flagge (optional): ").strip() or None
    
    try:
        ship_id = db.add_ship(
            name=name,
            laenge=laenge,
            breite=breite,
            liegeort=liegeort,
            typ=typ,
            flagge=flagge
        )
        print(f"\n✓ Schiff erfolgreich hinzugefügt (ID: {ship_id})")
    except Exception as e:
        print(f"\n✗ Fehler beim Hinzufügen: {e}")

# ========================= API-KEY PRÜFUNG =========================
def check_api_key(provided_key: Optional[str]) -> bool:
    """
    Prüft ob der bereitgestellte API-Key gültig ist.
    
    Args:
        provided_key: Der bereitgestellte API-Key
        
    Returns:
        True wenn Key gültig oder kein Key erforderlich, False sonst
    """
    if not provided_key:
        return True  # Kein Key erforderlich für lokale Nutzung
    
    return provided_key == SCHIFFS_DATENBANK_API_KEY

# ========================= HAUPTPROGRAMM =========================
def main():
    parser = argparse.ArgumentParser(
        description="Schiffsdatenbank - Verwaltung und Google Sheets Integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele (kurz):
  python Schiffs_Datenbank.py --init                    # Datenbank initialisieren
  python Schiffs_Datenbank.py --sync                   # Schiffe synchronisieren (Segelliste → HHLA)
  python Schiffs_Datenbank.py --import                 # Daten von VesselFinder importieren (mit Live-Update)
  python Schiffs_Datenbank.py --import --max 5         # Erste 5 Schiffe importieren
  python Schiffs_Datenbank.py --keine-daten            # Schiffe mit "Keine Daten" nochmal suchen
  python Schiffs_Datenbank.py --show                   # Alle Schiffe anzeigen

Beispiele (lang):
  python Schiffs_Datenbank.py --sync-from-hhla         # Alle Daten aus Sheet in Datenbank importieren
  python Schiffs_Datenbank.py --import-from-vesselfinder --from-sheet --live-update
        """
    )
    
    # Kurze, deutsche Argumente
    parser.add_argument("--init", action="store_true",
                       help="Datenbank initialisieren (Tabellen erstellen)")
    parser.add_argument("--sync", action="store_true",
                       help="Schiffe synchronisieren (Segelliste → Schiffsdaten HHLA)")
    parser.add_argument("--import", dest="import_short", action="store_true",
                       help="Daten von VesselFinder importieren (mit Live-Update)")
    parser.add_argument("--max", type=int, default=None, dest="max_ships_short",
                       help="Maximale Anzahl zu verarbeitender Schiffe (mit --import)")
    parser.add_argument("--keine-daten", dest="keine_daten", action="store_true",
                       help="Schiffe mit 'Keine Daten' in Spalte C nochmal suchen")
    parser.add_argument("--show", action="store_true",
                       help="Alle Schiffe anzeigen")
    
    # Lange Argumente (für Kompatibilität)
    parser.add_argument("--import-from-sheets", action="store_true",
                       help="Daten aus Google Sheets importieren")
    parser.add_argument("--sync-from-hhla", action="store_true",
                       help="Alle Daten aus Sheet 'Schiffsdaten HHLA' in Datenbank importieren")
    parser.add_argument("--import-from-vesselfinder", action="store_true",
                       help="Schiffsdaten von VesselFinder.com importieren")
    parser.add_argument("--from-sheet", action="store_true",
                       help="Schiffsnamen aus Sheet 'Schiffsdaten HHLA' lesen (mit --import-from-vesselfinder)")
    parser.add_argument("--vessels", nargs="+", metavar="NAME",
                       help="Schiffsnamen für VesselFinder-Import (alternativ zu --from-sheet)")
    parser.add_argument("--delay", type=float, default=3.0,
                       help="Wartezeit zwischen VesselFinder-Anfragen in Sekunden (Standard: 3.0)")
    parser.add_argument("--max-errors", type=int, default=25,
                       help="Maximale aufeinanderfolgende Fehler vor Abbruch (Standard: 25)")
    parser.add_argument("--max-ships", type=int, default=None,
                       help="Maximale Anzahl zu verarbeitender Schiffe (Standard: alle)")
    parser.add_argument("--skip", type=int, default=0,
                       help="Anzahl der zu überspringenden Schiffe am Anfang (Standard: 0)")
    parser.add_argument("--visible", action="store_true",
                       help="Browser sichtbar starten (empfohlen gegen Bot-Blockierung)")
    parser.add_argument("--live-update", action="store_true",
                       help="Jedes Schiff sofort ins Google Sheet schreiben (live sehen)")
    parser.add_argument("--export-to-sheets", action="store_true",
                       help="Daten zu Google Sheets exportieren")
    parser.add_argument("--update-hhla-sheet", action="store_true",
                       help="Sheet 'Schiffsdaten HHLA' mit Datenbank-Daten aktualisieren")
    parser.add_argument("--show-all", action="store_true",
                       help="Alle Schiffe anzeigen")
    parser.add_argument("--search", type=str, metavar="BEGRIFF",
                       help="Nach Schiff suchen")
    parser.add_argument("--add-ship", action="store_true",
                       help="Neues Schiff interaktiv hinzufügen")
    parser.add_argument("--stats", action="store_true",
                       help="Statistiken anzeigen")
    parser.add_argument("--db-path", type=str, default=DB_PATH,
                       help=f"Pfad zur Datenbankdatei (Standard: {DB_PATH})")
    parser.add_argument("--api-key", type=str, default=None,
                       help="API-Key für Authentifizierung (erforderlich bei API-Aufrufen)")
    
    args = parser.parse_args()
    
    # API-Key-Prüfung (optional - nur wenn --api-key angegeben)
    if args.api_key:
        if not check_api_key(args.api_key):
            print("✗ Fehler: Ungültiger API-Key")
            sys.exit(1)
        log_info("✓ API-Key validiert")
    
    # Wenn keine Argumente, zeige Infotext
    if len(sys.argv) == 1:
        print("\n" + "="*70)
        print("  SCHIFFSDATENBANK - Keine Daten angegeben")
        print("="*70)
        print("\n📋 Verfügbare Befehle:")
        print("  --init              Datenbank initialisieren")
        print("  --sync              Schiffe synchronisieren (Segelliste → HHLA)")
        print("  --import            Daten von VesselFinder importieren")
        print("  --import --max 5    Erste 5 Schiffe importieren")
        print("  --keine-daten       Schiffe mit 'Keine Daten' nochmal suchen")
        print("  --show              Alle Schiffe anzeigen")
        print("\n💡 Beispiel:")
        print("  python3 Schiffs_Datenbank.py --sync")
        print("  python3 Schiffs_Datenbank.py --import")
        print("\n" + "="*70)
        print("Für alle Optionen: python3 Schiffs_Datenbank.py --help")
        print("="*70 + "\n")
        sys.exit(0)
    
    # Erstelle Datenbank-Objekt
    db = SchiffsDatenbank(args.db_path)
    
    # Führe gewünschte Aktion aus
    try:
        if args.init:
            db.init_database()
        
        # Kurze Argumente
        if args.sync:
            sync_schiffsdaten(db)
        
        if args.import_short:
            # Kurze Version: --import = --import-from-vesselfinder --from-sheet --live-update
            sync_database_with_sheet(db)
            use_headless = not args.visible
            max_ships = args.max_ships_short or args.max_ships
            import_from_vesselfinder(db, from_sheet=True, delay=args.delay,
                                    max_consecutive_errors=args.max_errors,
                                    headless=use_headless,
                                    max_ships=max_ships,
                                    skip_ships=args.skip,
                                    live_update=True)
        
        if args.keine_daten:
            search_keine_daten(db)
        
        if args.show:
            show_all_ships(db)
        
        # Lange Argumente (für Kompatibilität)
        if args.import_from_sheets:
            import_from_sheets(db)
        
        if args.sync_from_hhla:
            log_header("Sync: Sheet → Datenbank")
            sync_database_with_sheet(db)
        
        if args.import_from_vesselfinder:
            # Vor dem Import: Synchronisiere Datenbank mit Sheet (für manuell eingetragene Daten)
            if args.from_sheet or args.live_update:
                sync_database_with_sheet(db)
            
            # Headless = False wenn --visible gesetzt, sonst True (aber wir setzen jetzt False als Standard)
            use_headless = not args.visible  # Wenn --visible gesetzt, dann headless=False
            
            if args.from_sheet:
                import_from_vesselfinder(db, from_sheet=True, delay=args.delay, 
                                        max_consecutive_errors=args.max_errors,
                                        headless=use_headless,
                                        max_ships=args.max_ships,
                                        skip_ships=args.skip,
                                        live_update=args.live_update)
            elif args.vessels:
                import_from_vesselfinder(db, vessel_names=args.vessels, delay=args.delay,
                                        max_consecutive_errors=args.max_errors,
                                        headless=use_headless,
                                        max_ships=args.max_ships,
                                        skip_ships=args.skip,
                                        live_update=args.live_update)
            else:
                log_error("✗ Bitte entweder --from-sheet oder --vessels angeben")
                log_info("Beispiel: python Schiffs_Datenbank.py --import-from-vesselfinder --from-sheet --visible")
                log_info("oder: python Schiffs_Datenbank.py --import-from-vesselfinder --vessels \"COSCO SHIPPING SOLAR\" --visible")
        
        if args.export_to_sheets:
            export_to_sheets(db)
        
        if args.update_hhla_sheet:
            update_hhla_sheet_with_data(db)
        
        if args.show_all:
            show_all_ships(db)
        elif args.show:
            # Wird bereits oben behandelt, aber für Kompatibilität
            pass
        
        if args.search:
            print(f"\n=== Suche nach '{args.search}' ===")
            ships = db.search_ship(args.search)
            if ships:
                print(f"\nGefunden: {len(ships)} Schiffe\n")
                print(f"{'ID':<5} {'Name':<40} {'Länge':<10} {'Liegeort':<20}")
                print("-" * 80)
                for ship in ships:
                    id_str = str(ship.get('id', ''))
                    name = str(ship.get('name', ''))[:40]
                    laenge = f"{ship.get('laenge', '')} m" if ship.get('laenge') else '-'
                    liegeort = str(ship.get('liegeort', '') or '-')[:20]
                    print(f"{id_str:<5} {name:<40} {laenge:<10} {liegeort:<20}")
            else:
                print("Keine Schiffe gefunden")
        
        if args.add_ship:
            interactive_add_ship(db)
        
        if args.stats:
            show_statistics(db)
            
    except KeyboardInterrupt:
        print("\n\nUnterbrochen durch Benutzer")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Fehler: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

