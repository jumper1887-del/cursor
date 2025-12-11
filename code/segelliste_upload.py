#!/usr/bin/env python3
import os
import sys
import time
import glob
import traceback
import shutil
import logging
from datetime import datetime, timedelta

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# ============================================================
# KONFIGURATION
# ============================================================
DOWNLOAD_DIR = "/root/Skrip/Downloads"
SERVICE_ACCOUNT_FILE = "/root/Skrip/segelliste-83c2a17a5e89.json"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1Q_Dvufm0LCUxYtktMtM18Xz30sXQxCnGfI9SSDFPUNw/edit"
LOCAL_FILENAME = os.path.join(DOWNLOAD_DIR, "segelliste.xlsx")

KEEP_TIMESTAMP_FILES = 1              # Anzahl Timestamp-Excel-Dateien behalten
HEADLESS = True                       # Headless-Browsermodus
LOG_DIR = "/root/Skrip/logs"
PY_LOG_PREFIX = "segelliste_upload_py_"
LOG_RETENTION_DAYS = 30               # Alte Python-Logs löschen nach X Tagen

# Terminal Progress (rein optisch)
RESET = '\033[0m'
PROGRESS_TEXT_BG = '\033[48;2;57;255;20m'
PROGRESS_TEXT_FG = '\033[30m'
BAR_DONE = '\033[38;2;0;255;0m'
BAR_TODO = '\033[38;2;0;120;255m'
PERCENT_FG = '\033[38;2;250;240;20m'


# ============================================================
# LOGGING SETUP
# ============================================================
def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    logfile = os.path.join(LOG_DIR, f"{PY_LOG_PREFIX}{today}.log")

    # Symlink auf aktuelles Log
    current_link = os.path.join(LOG_DIR, f"{PY_LOG_PREFIX}current.log")
    try:
        if os.path.islink(current_link) or os.path.exists(current_link):
            os.remove(current_link)
        os.symlink(logfile, current_link)
    except Exception:
        pass

    # Alte Logs löschen
    cutoff = datetime.utcnow() - timedelta(days=LOG_RETENTION_DAYS)
    for f in glob.glob(os.path.join(LOG_DIR, f"{PY_LOG_PREFIX}*.log")):
        try:
            mtime = datetime.utcfromtimestamp(os.path.getmtime(f))
            if mtime < cutoff:
                os.remove(f)
                print(f"[CLEANUP_LOG] Entfernt altes Python-Log: {f}")
        except Exception:
            pass

    logger = logging.getLogger("segelliste_upload")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(logfile, encoding="utf-8")
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger

logger = setup_logging()

def log(msg, level="info"):
    if level == "error":
        logger.error(msg)
    elif level == "warning":
        logger.warning(msg)
    else:
        logger.info(msg)


# ============================================================
# HILFSFUNKTIONEN
# ============================================================
def print_progress_bar(percent, length=60):
    percent = max(0, min(100, percent))
    done = int(length * percent // 100)
    bar = f"{BAR_DONE}{'#' * done}{RESET}{BAR_TODO}{'.' * (length - done)}{RESET}"
    progress_text = f"{PROGRESS_TEXT_BG}{PROGRESS_TEXT_FG} Progress {RESET}"
    percent_str = f"{PERCENT_FG}{percent:3.0f}%{RESET}"
    sys.stdout.write(f"\r{progress_text} [{percent_str}] [{bar}]")
    sys.stdout.flush()


def cleanup_old_timestamp_files():
    pattern1 = os.path.join(DOWNLOAD_DIR, "Schiffsabfertigung_Segelliste_*.xlsx")
    pattern2 = os.path.join(DOWNLOAD_DIR, "Vessel_Operations_Sailing_list_*.xlsx")
    files = sorted(glob.glob(pattern1) + glob.glob(pattern2), key=os.path.getctime, reverse=True)
    if KEEP_TIMESTAMP_FILES < len(files):
        log(f"Behalte {KEEP_TIMESTAMP_FILES} Datei(en), lösche {len(files) - KEEP_TIMESTAMP_FILES} ältere.")
    for f in files[KEEP_TIMESTAMP_FILES:]:
        try:
            os.remove(f)
            log(f"Gelöscht (alt): {f}")
        except Exception as e:
            log(f"Fehler beim Löschen {f}: {e}", level="warning")


def setup_driver():
    options = Options()
    options.binary_location = "/usr/bin/google-chrome"
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    prefs = {"download.default_directory": DOWNLOAD_DIR}
    options.add_experimental_option("prefs", prefs)
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def download_report():
    driver = setup_driver()
    timestamp_file = None
    try:
        url = "https://coast.hhla.de/report?id=Standard-Report-Segelliste"
        log(f"Öffne Seite: {url}")
        driver.get(url)
        time.sleep(6)

        log("Suche Excel-Button...")
        try:
            excel_button = driver.find_element(By.XPATH, '//button[contains(text(), "Excel-Export")]')
        except Exception:
            excel_button = driver.find_element(By.XPATH, '//button[contains(text(), "Excel")]')

        driver.execute_script("arguments[0].click();", excel_button)
        log("Warte auf Download...")

        pattern1 = os.path.join(DOWNLOAD_DIR, "Schiffsabfertigung_Segelliste_*.xlsx")
        pattern2 = os.path.join(DOWNLOAD_DIR, "Vessel_Operations_Sailing_list_*.xlsx")
        timeout = 120
        start = time.time()

        while time.time() - start < timeout:
            elapsed = time.time() - start
            print_progress_bar((elapsed / timeout) * 100)
            files = glob.glob(pattern1) + glob.glob(pattern2)
            if files:
                newest = max(files, key=os.path.getctime)
                if not newest.endswith(".crdownload"):
                    timestamp_file = newest
                    break
            time.sleep(1)
        print()

        if not timestamp_file:
            raise FileNotFoundError("Download nicht abgeschlossen (kein fertiges XLSX gefunden).")

        log(f"Neue Timestamp-Datei: {timestamp_file}")

        # Feste Datei segelliste.xlsx aktualisieren
        if os.path.exists(LOCAL_FILENAME):
            os.remove(LOCAL_FILENAME)
        shutil.copy2(timestamp_file, LOCAL_FILENAME)
        log(f"Kopiert: {timestamp_file} -> {LOCAL_FILENAME}")

        return LOCAL_FILENAME, timestamp_file

    finally:
        try:
            driver.quit()
        except Exception:
            pass


def update_google_sheets(original_filename, segelliste_path):
    log(f"Lese Excel: {segelliste_path}")
    df = pd.read_excel(segelliste_path, dtype=str).fillna("")
    row_count = len(df)
    col_count = len(df.columns)
    log(f"Excel geladen – Zeilen: {row_count}, Spalten: {col_count}")

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    gc = gspread.authorize(credentials)
    sh = gc.open_by_url(SPREADSHEET_URL)

    # Blatt Segelliste
    try:
        seg = sh.worksheet("Segelliste")
    except gspread.WorksheetNotFound:
        seg = sh.add_worksheet(title="Segelliste", rows="2000", cols="40")
        log("Blatt 'Segelliste' neu angelegt.")

    seg.clear()
    seg.update(values=[[os.path.basename(original_filename)]], range_name="A1")
    seg.update(values=[df.columns.tolist()] + df.values.tolist(), range_name="A2")
    log("Google Sheet 'Segelliste' aktualisiert.")

    if col_count < 5:
        log("Warnung: Erwartete Spalten für Schiffslänge nicht vollständig (mindestens 5).", level="warning")

    liegeort = df.iloc[:, 2] if col_count > 2 else pd.Series([])
    ship_names = df.iloc[:, 4] if col_count > 4 else pd.Series([])
    ship_lengths = df.iloc[:, 3] if col_count > 3 else pd.Series([])

    data = pd.DataFrame({'Name': ship_names, 'Länge': ship_lengths, 'Liegeort': liegeort})
    data_ctt = data[data['Liegeort'].str.contains('CTT', na=False)]
    data_ctt = data_ctt.dropna(subset=['Name']).drop_duplicates(subset=['Name'])
    values = [['Name', 'Länge']] + data_ctt[['Name', 'Länge']].values.tolist()

    try:
        sl = sh.worksheet("Schiffslänge")
    except gspread.WorksheetNotFound:
        sl = sh.add_worksheet(title="Schiffslänge", rows="1000", cols="5")
        log("Blatt 'Schiffslänge' neu angelegt.")

    sl.clear()
    sl.update(values=values, range_name="A1")
    log(f"Google Sheet 'Schiffslänge' aktualisiert. Einträge: {len(values) - 1}")


def main():
    start_ts = time.time()
    log("=== Start segelliste_upload.py ===")
    log(f"Download-Verzeichnis: {DOWNLOAD_DIR}")
    log(f"Headless-Modus: {'Ja' if HEADLESS else 'Nein'}")
    log(f"Behalte Timestamp-Dateien: {KEEP_TIMESTAMP_FILES}")

    cleanup_old_timestamp_files()
    segelliste_path, original_filename = download_report()
    update_google_sheets(original_filename, segelliste_path)

    duration = time.time() - start_ts
    log(f"=== Fertig ohne Fehler (Dauer: {duration:.2f}s) ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        tb = traceback.format_exc()
        log(f"FEHLER: {e}", level="error")
        log(tb, level="error")
        sys.exit(1)