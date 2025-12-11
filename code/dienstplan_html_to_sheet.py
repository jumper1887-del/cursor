# Dieses Skript liest die gespeicherte HTML-Datei (dienstplan.html) aus /root/Skrip/Downloads und schreibt alle Schichten aus dem Oktober in eine Google-Tabelle.

import re
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# === KONFIGURATION ===
HTML_FILE = "/root/Skrip/Downloads/dienstplan.html"
SERVICE_ACCOUNT_FILE = "/root/Skrip/segelliste-83c2a17a5e89.json"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1Q_Dvufm0LCUxYtktMtM18Xz30sXQxCnGfI9SSDFPUNw/edit"
TABNAME = "Dienstplan"

def parse_html_for_shifts(html):
    soup = BeautifulSoup(html, "html.parser")
    alle_schichten = []

    # Woche extrahieren (z.B. "Woche 40")
    week_header = soup.select_one(".week-number p,.week-number")
    woche = week_header.get_text(strip=True) if week_header else ""

    # Alle Wochentage-Boxen
    day_boxes = soup.select(".top-row .day-des")
    days = []
    for box in day_boxes:
        try:
            tag = box.select_one("p.day-name").get_text(strip=True)
            datum = box.select_one("p.date-number").get_text(strip=True)
        except Exception:
            tag = ""
            datum = ""
        days.append({"tag": tag, "datum": datum})

    # Alle day-content-Boxen
    week_table = soup.select_one("div.week-table")
    if not week_table:
        print("Keine Wochen-Tabelle gefunden!")
        return []
    day_contents = week_table.select("div.day-content")

    for idx, day in enumerate(day_contents):
        tag = days[idx]["tag"] if idx < len(days) else ""
        datum = days[idx]["datum"] if idx < len(days) else ""
        # Nur Oktober
        found_oktober = False
        if "Oktober" in datum or "October" in datum:
            found_oktober = True
        else:
            if re.search(r"\bOktober\b", datum) or re.search(r"\bOctober\b", datum):
                found_oktober = True
            if re.search(r"10\.", datum) or re.search(r"2025-10-", datum):
                found_oktober = True
        if not found_oktober:
            continue

        time_blocks = day.select(".time-block")
        shift_containers = day.select(".shift-container")
        shift_container_idx = 0
        for t in time_blocks:
            zeit = t.get_text(strip=True).replace('\n', ' ')
            shift_container = None
            if shift_container_idx < len(shift_containers):
                shift_container = shift_containers[shift_container_idx]
                shift_container_idx += 1
            if shift_container:
                for li in shift_container.select("li.shift"):
                    tooltip = li.get("title") or li.get("data-tooltip") or ""
                    try:
                        name = li.select_one(".shift-name p").get_text(strip=True)
                    except Exception:
                        name = ""
                    alle_schichten.append([woche, tag, datum, zeit, name, tooltip])
    return alle_schichten

def write_schichten_to_sheet(schichten_rows, start_row=3, col=1):
    print("Schreibe Schicht-Details als Zeilen in die Tabelle ...")
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    gc = gspread.authorize(credentials)
    sh = gc.open_by_url(SPREADSHEET_URL)
    ws = sh.worksheet(TABNAME)
    headers = [["Woche", "Tag", "Datum", "Zeit", "Name", "Bereich"]]
    ws.update(values=headers, range_name=gspread.utils.rowcol_to_a1(start_row, col) + ":" + gspread.utils.rowcol_to_a1(start_row, col+5))
    end_row = start_row + len(schichten_rows)
    if schichten_rows:
        ws.update(values=schichten_rows, range_name=gspread.utils.rowcol_to_a1(start_row+1, col) + ":" + gspread.utils.rowcol_to_a1(end_row, col+5))
        print(f"{len(schichten_rows)} Schicht-Zeilen geschrieben.")
    else:
        print("Keine Schicht-Zeilen zum Schreiben gefunden.")

if __name__ == "__main__":
    print("Lese dienstplan.html aus /root/Skrip/Downloads und schreibe alle Oktoberschichten in die Google-Tabelle ...")
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    schichten = parse_html_for_shifts(html)
    write_schichten_to_sheet(schichten)
    print("Fertig!")