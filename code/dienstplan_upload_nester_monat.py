import os
import time
import shutil
import tempfile
import zoneinfo
from datetime import datetime
from tqdm import tqdm

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image, ImageDraw

def print_status(msg):
    print(f"[STATUS] {msg}")

# ==== KONFIGURATION ====
SMARTPLAN_URL = "https://auth.smartplanapp.io/login/"
SMARTPLAN_MAIL = os.environ.get("SMARTPLAN_MAIL")
SMARTPLAN_PASS = os.environ.get("SMARTPLAN_PASS")

LOG_DIR = "/root/Skrip/logs"
DOWNLOAD_DIR = "/root/Skrip/Downloads"
LOG_FILE = os.path.join(LOG_DIR, "dienstplan_log.txt")
# Geänderter Dateiname: speichert nun direkt als dienstplanNestermonat.html
HTML_FILE = os.path.join(DOWNLOAD_DIR, "dienstplanNestermonat.html")

def log_action(message):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        tz = zoneinfo.ZoneInfo("Europe/Berlin")
        timestamp = datetime.now(tz).strftime("%Y-%m-%d_%H-%M-%S %Z")
    except Exception:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S UTC")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

def screenshot(driver, step, schritt_nummer=None, x=None, y=None, phase=None, markiere_kreuz=False):
    os.makedirs("fotos", exist_ok=True)
    parts = []
    if schritt_nummer is not None:
        parts.append(f"{schritt_nummer:02d}")
    parts.append(step)
    if phase:
        parts.append(phase)
    if x is not None and y is not None:
        parts.append(f"x{x}_y{y}")
    filename = "_".join(parts) + ".png"
    path = os.path.join("fotos", filename)
    driver.save_screenshot(path)
    if markiere_kreuz and x is not None and y is not None:
        try:
            img = Image.open(path)
            draw = ImageDraw.Draw(img)
            cross_size = 12
            draw.line([(x-cross_size, y), (x+cross_size, y)], fill="red", width=3)
            draw.line([(x, y-cross_size), (x, y+cross_size)], fill="red", width=3)
            img.save(path)
        except Exception as e:
            print(f"Konnte Kreuz nicht einzeichnen: {e}")
    print(f"Screenshot {path} gespeichert.")

def wait_post_login(driver, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if "login" not in driver.current_url:
                return True
            if driver.find_elements(By.CSS_SELECTOR, "a.title-date-con.u-flex.u-flexCol"):
                return True
            if not driver.find_elements(By.CSS_SELECTOR, "form.login"):
                return True
        except StaleElementReferenceException:
            pass
        time.sleep(0.5)
    return False

def klick_mit_kordinaten(driver, x, y, step, schritt_nummer=None):
    screenshot(driver, step, schritt_nummer, x, y, phase="vorher", markiere_kreuz=True)
    try:
        ActionChains(driver).move_by_offset(x, y).click().perform()
        log_action(f"Klick auf Koordinaten ({x},{y}) durchgeführt ({step}, Schritt {schritt_nummer})")
        print_status(f"Schritt {schritt_nummer}: Klick auf Koordinaten ({x},{y}) durchgeführt")
    except Exception as e:
        log_action(f"FEHLER beim Klick auf Koordinaten ({x},{y}): {repr(e)}")
        print_status(f"FEHLER beim Klick auf Koordinaten ({x},{y}): {repr(e)}")
    screenshot(driver, step, schritt_nummer, x, y, phase="nachher", markiere_kreuz=True)

def klick_per_selector(driver, selector, schritt_nummer=None, schrittname="klick_auf_button"):
    screenshot(driver, schrittname, schritt_nummer, phase="vorher")
    try:
        element = driver.find_element(By.CSS_SELECTOR, selector)
        rect = element.rect
        x = int(rect['x'] + rect['width']//2)
        y = int(rect['y'] + rect['height']//2)
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.2)
        element.click()
        log_action(f"Klick auf Button ({selector}) durchgeführt ({schrittname}, Schritt {schritt_nummer})")
        screenshot(driver, schrittname, schritt_nummer, x, y, phase="nachher", markiere_kreuz=True)
        print_status(f"Schritt {schritt_nummer}: Klick auf Button ({selector}) durchgeführt")
        return True
    except Exception as e:
        log_action(f"FEHLER beim Klick auf Button ({selector}): {repr(e)}")
        print_status(f"FEHLER beim Klick auf Button ({selector}): {repr(e)}")
        screenshot(driver, schrittname+"_fehler", schritt_nummer, phase="nachher")
        return False

def get_html_source(driver):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    html = driver.page_source
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print_status(f"HTML-Datei gespeichert: {HTML_FILE}")
    return html

def download_dienstplan():
    schritte = [
        "Starte Browser (Chrome Headless mit temporärem Profil)",
        "Gehe zur Login-Seite",
        "Fülle Login-Daten aus",
        "Klicke auf Login-Button",
        "Warte auf eingeloggt",
        "Klicke auf Koordinaten (450,250)",
        "Warte 3 Sekunden, dann Screenshot",
        "Button-Klick per Selektor",
        "Nach Button-Klick / Fallback",
        "Nach oben scrollen / Fallback",
        "Dienstplan laden"
    ]
    with tqdm(total=len(schritte), desc="Dienstplan-Fortschritt", ncols=80) as pbar:
        log_action("[Schritt 1] Starte Browser...")
        print_status(schritte[0])
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        temp_profile = tempfile.mkdtemp()
        options.add_argument(f"--user-data-dir={temp_profile}")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        pbar.update(1)
        try:
            driver.set_window_size(1920, 1080)

            log_action("[Schritt 1] Gehe zur Login-Seite...")
            print_status(schritte[1])
            driver.get(SMARTPLAN_URL)
            time.sleep(1.5)
            screenshot(driver, "loginpage", 1)
            pbar.update(1)

            log_action("[Schritt 2] Fülle Login-Daten aus...")
            print_status(schritte[2])
            wait = WebDriverWait(driver, 25)
            email_input = wait.until(EC.presence_of_element_located((By.ID, "id_login_user_email")))
            email_input.clear()
            email_input.send_keys(SMARTPLAN_MAIL)
            pw_input = driver.find_element(By.ID, "id_login_user_password")
            pw_input.clear()
            pw_input.send_keys(SMARTPLAN_PASS)
            screenshot(driver, "login_filled", 2)
            pbar.update(1)

            log_action("[Schritt 3] Klicke auf Login-Button...")
            print_status(schritte[3])
            login_div = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.login_email")))
            screenshot(driver, "login_button_vorher", 3)
            login_div.click()
            screenshot(driver, "login_button_nachher", 3)
            log_action("[Schritt 3] Login erfolgreich.")
            pbar.update(1)

            log_action("[Schritt 4] Warte auf eingeloggt...")
            print_status(schritte[4])
            if not wait_post_login(driver, 30):
                screenshot(driver, "post_login_failed", 4)
                log_action("[Schritt 4] FEHLER: Nach Login keine Weiterleitung!")
                print_status("FEHLER: Nach Login keine Weiterleitung!")
                raise Exception("Post-Login fehlgeschlagen")
            time.sleep(1)
            screenshot(driver, "post_login_ok", 4)
            pbar.update(1)

            log_action("[Schritt 5] Klicke auf Koordinaten (450,250)...")
            print_status(schritte[5])
            klick_mit_kordinaten(driver, 450, 250, "klick_auf_koordinaten", 5)
            pbar.update(1)

            log_action("[Schritt 6] Warte 3 Sekunden, dann Screenshot.")
            print_status(schritte[6])
            time.sleep(3)
            screenshot(driver, "abschluss", 6)
            log_action("[Schritt 6] Schritt abgeschlossen.")
            pbar.update(1)

            schritt = 7
            print_status(schritte[7])
            selector = "a.view_full_week.btn-block.btn-block--shadow.small.view-whole-plan"
            log_action(f"[Schritt {schritt}] Versuche Klick auf Button per Selektor...")
            button_clicked = klick_per_selector(driver, selector, schritt, "klick_auf_button")
            time.sleep(1)
            pbar.update(1)

            if not button_clicked:
                schritt = 8
                print_status(schritte[8])
                log_action(f"[Schritt {schritt}] Button-Klick ging nicht, 3 Sekunden warten und Screenshot.")
                time.sleep(3)
                screenshot(driver, "warten", schritt)
                pbar.update(1)

                schritt = 9
                print_status(schritte[9])
                log_action(f"[Schritt {schritt}] Klicke auf Koordinaten (1550,235)...")
                klick_mit_kordinaten(driver, 1550, 235, "klick_auf_koordinaten", schritt)
                time.sleep(3)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                screenshot(driver, "scroll_nach_unten", schritt)
                print_status("== Skript ENDE nach allen Schritten (Fallback-Pfad) ==")
                log_action("Script gestoppt nach allen Schritten (Fallback-Pfad).")
                pbar.update(1)
            else:
                schritt = 8
                print_status(schritte[8])
                log_action(f"[Schritt {schritt}] Button-Klick erfolgreich, 3 Sekunden warten, dann Screenshot.")
                time.sleep(3)
                screenshot(driver, "nach_button_klick", schritt)
                pbar.update(1)

                schritt = 9
                print_status(schritte[9])
                log_action(f"[Schritt {schritt}] 3 Sekunden warten, dann ganz nach oben scrollen.")
                time.sleep(3)
                driver.execute_script("window.scrollTo(0,0);")
                screenshot(driver, "scroll_nach_oben", schritt)
                pbar.update(1)

                schritt = 10
                print_status(schritte[10])
                log_action(f"[Schritt {schritt}] Versuche die Dienstplan-Daten vollständig zu laden...")
                try:
                    wait = WebDriverWait(driver, 20)
                    dienstplan_selector = "div.roster-con"
                    dienstplan_element = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, dienstplan_selector))
                    )
                    if driver.find_elements(By.CSS_SELECTOR, "div.week-table"):
                        log_action(f"[Schritt {schritt}] DIENSTPLAN-SCHICHTEN GEFUNDEN und geladen!")
                        print_status(f"Schritt {schritt}: DIENSTPLAN-SCHICHTEN GEFUNDEN!")
                    else:
                        log_action(f"[Schritt {schritt}] 'roster-con' gefunden, aber keine Schichtdaten im HTML.")
                        print_status(f"Schritt {schritt}: 'roster-con' gefunden, aber keine Schichtdaten im HTML.")
                except Exception as e:
                    log_action(f"[Schritt {schritt}] Dienstplan-Element NICHT gefunden: {e}")
                    print_status(f"Schritt {schritt}: Dienstplan-Element NICHT gefunden!")
                screenshot(driver, "dienstplan_geladen", schritt)
                pbar.update(1)

                get_html_source(driver)
                print_status("== Skript ENDE nach HTML-Download (Analyse bitte mit separatem Skript) ==")
                log_action("Script gestoppt nach HTML-Download (keine weitere Auswertung).")
        finally:
            driver.quit()
            print_status("Browser wurde geschlossen.")
            try:
                shutil.rmtree(temp_profile)
            except Exception:
                pass

if __name__ == "__main__":
    try:
        print_status("Starte Dienstplan-Automation ...")
        download_dienstplan()
        print_status("Fertig!")
    except Exception as e:
        log_action(f"FEHLER: {repr(e)}")
        print_status(f"FEHLER: {repr(e)}")