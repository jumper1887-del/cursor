import glob
import os
import time
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# ======= Einstellungen =======
download_dir = r"C:\Users\Mirko\Documents\Scripts"
service_account_file = r"C:\Users\Mirko\Documents\Scripts\service_account.json"
spreadsheet_url = "https://docs.google.com/spreadsheets/d/1Q_Dvufm0LCUxYtktMtM18Xz30sXQxCnGfI9SSDFPUNw/edit"

local_filename = os.path.join(download_dir, "segelliste.xlsx")

try:
    # ======= Alte Segellisten löschen =======
    list_of_files = glob.glob(os.path.join(download_dir, "Schiffsabfertigung_Segelliste_*.xlsx"))
    for file in list_of_files:
        os.remove(file)
        print(f"Gelöscht: {file}")

    # ======= Chrome starten =======
    options = Options()
    options.add_argument("--start-maximized")
    prefs = {"download.default_directory": download_dir}
    options.add_experimental_option("prefs", prefs)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # ======= Seite öffnen =======
    driver.get("https://coast.hhla.de/report?id=Standard-Report-Segelliste")
    time.sleep(5)

    # ======= Excel-Button anklicken =======
    excel_button = driver.find_element("xpath", '//button[contains(text(), "Excel")]')
    excel_button.click()

    # ======= Warten, bis Download fertig ist =======
    time.sleep(10)  # ggf. anpassen

    # ======= Neueste Excel-Datei finden =======
    list_of_files = glob.glob(os.path.join(download_dir, "Schiffsabfertigung_Segelliste_*.xlsx"))
    latest_file = max(list_of_files, key=os.path.getctime)
    print(f"Neueste Datei: {latest_file}")

    # ======= Schreibschutz entfernen =======
    os.chmod(latest_file, 0o666)
    print(f"Schreibschutz entfernt: {latest_file}")

    # ======= Excel-Datei ins Google Sheet laden =======
    df = pd.read_excel(latest_file)
    df = df.fillna("")  # NaN durch leere Strings ersetzen

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_file(service_account_file, scopes=scopes)
    gc = gspread.authorize(credentials)
    sh = gc.open_by_url(spreadsheet_url)
    sheet = sh.sheet1

    # Tabellenblatt umbenennen
    sheet.update_title("Segelliste")

    # Zellen A1:C1 zusammenführen für langen Dateinamen
    sheet.merge_cells('A1:C1')

    # Dateiname in A1 einfügen
    sheet.update('A1', [[os.path.basename(latest_file)]])

    # Daten ab A2 einfügen
    sheet.update('A2', [df.columns.values.tolist()] + df.values.tolist())
    print("Google Sheet aktualisiert mit Dateiname in A1.")

    # ======= Datei umbenennen =======
    if os.path.exists(local_filename):
        os.remove(local_filename)  # alte segelliste.xlsx löschen
    os.rename(latest_file, local_filename)
    print(f"Datei umbenannt in: {local_filename}")

finally:
    # ======= Browser schließen =======
    driver.quit()
    print("Browser geschlossen.")
