#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dienstplan-Importer
Datei: dienstplan_html_Nester_monat.py

Enthält:
- Standard-Input-HTML: dienstplanNestermonat.html
- Jahres-Korrektur für "nächsten Monat" (Monat kleiner als aktueller -> Jahr+1)
- Robustere Parser- und Google-Sheets-Logik (wie vorher besprochen)
"""
import os
import re
import time
import logging
from datetime import datetime
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials

# ---------- Konfiguration (anpassen / Umgebungsvariablen möglich) ----------
HTML_FILE = os.getenv("DIENSTPLAN_HTML_FILE", "/root/Skrip/Downloads/dienstplanNestermonat.html")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "/root/Skrip/segelliste-83c2a17a5e89.json")
SPREADSHEET_URL = os.getenv("SPREADSHEET_URL", "https://docs.google.com/spreadsheets/d/1Q_Dvufm0LCUxYtktMtM18Xz30sXQxCnGfI9SSDFPUNw/edit")
TABNAME = os.getenv("SPREADSHEET_TABNAME", "Dienstplan")

# Logging konfigurieren
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("dienstplan_import")

# Deutsche Wochentage / Monate
TAGE_DE = {
    0: "Montag",
    1: "Dienstag",
    2: "Mittwoch",
    3: "Donnerstag",
    4: "Freitag",
    5: "Samstag",
    6: "Sonntag"
}
MONATE_DE = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12
}
MONATSNAMEN_DE = [
    "", "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember"
]

# ---------- Hilfsfunktionen ----------
def normalize_month_name(s: str) -> str:
    if not s:
        return ""
    s = s.strip().lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return s

def parse_tagdatum(tagdatum_str):
    """Gibt (year, month, day) zurück oder (9999,99,99) bei Fehler."""
    if not tagdatum_str:
        return (9999, 99, 99)
    m = re.match(r"\w+\s+(\d{1,2})\.?\s*([A-Za-zäöüÄÖÜß]+)\s+(\d{4})", tagdatum_str.strip())
    if m:
        day = int(m.group(1))
        month_raw = normalize_month_name(m.group(2))
        month = MONATE_DE.get(month_raw, 1)
        year = int(m.group(3))
        return (year, month, day)
    return (9999, 99, 99)

def extract_datum(tag_datum):
    """Wandelt 'Montag 4. Mai 2025' -> '04.05.2025'. Falls nicht möglich, original zurück."""
    if not tag_datum:
        return ""
    m = re.match(r"\w+\s+(\d{1,2})\.?\s*([A-Za-zäöüÄÖÜß]+)\s+(\d{4})", tag_datum.strip())
    if m:
        day = int(m.group(1))
        monat_raw = normalize_month_name(m.group(2))
        monat = MONATE_DE.get(monat_raw, 0)
        year = int(m.group(3))
        if monat > 0:
            return f"{day:02d}.{monat:02d}.{year}"
    return tag_datum

def tagdatum_sortkey(tagdatum_str):
    return parse_tagdatum(tagdatum_str)

# ---------- HTML Parsing ----------
def get_day_and_hidden_date(day_name_p, day_box):
    """
    Ermittelt ein Datum für eine Tages-Box.
    Wenn ein explizites 'date-number' Feld vorhanden ist, wird dieses geparst.
    Wenn der erkannte Monat kleiner ist als der aktuelle Monat, wird das Jahr inkrementiert (nächster Jahreswechsel).
    """
    tag = day_name_p.get_text(strip=True) if day_name_p else ""
    now = datetime.now()
    year = now.year

    date_number_p = day_box.find("p", class_="date-number")
    datum = date_number_p.get_text(strip=True) if date_number_p else ""

    m = re.match(r"(\d{1,2})\.\s*([A-Za-zäöüÄÖÜß]+)", datum)
    if m:
        day_num = int(m.group(1))
        monat_raw = normalize_month_name(m.group(2))
        monat_nr = MONATE_DE.get(monat_raw, 0)
        if monat_nr > 0:
            # Jahr anpassen, falls Monat im nächsten Jahr liegt (z. B. jetzt Dez, Plandaten: Jan)
            if monat_nr < now.month:
                year = now.year + 1
            try:
                dt = datetime(year, monat_nr, day_num)
                wochentag = TAGE_DE[dt.weekday()]
            except Exception:
                wochentag = "?"
            return f"{wochentag} {day_num}. {MONATSNAMEN_DE[monat_nr]} {year}"
    # Fallback: tag + eventuell vorhandenes datum
    # Falls datum nur "4. Januar" ohne Jahr vorhanden ist, versuchen wir dieselbe Heuristik:
    m2 = re.match(r"(\d{1,2})\.\s*([A-Za-zäöüÄÖÜß]+)", tag)
    if not date_number_p and m2:
        day_num = int(m2.group(1))
        monat_raw = normalize_month_name(m2.group(2))
        monat_nr = MONATE_DE.get(monat_raw, 0)
        if monat_nr > 0:
            if monat_nr < now.month:
                year = now.year + 1
            try:
                dt = datetime(year, monat_nr, day_num)
                wochentag = TAGE_DE[dt.weekday()]
            except Exception:
                wochentag = "?"
            return f"{wochentag} {day_num}. {MONATSNAMEN_DE[monat_nr]} {year}"

    return f"{tag} {datum} {year}".strip()

def parse_html_for_shifts(html):
    """
    Erwartet das HTML des Dienstplan-Exports und gibt eine Liste von Einträgen:
    [woche, tag_datum, zeit, name, bereich]
    """
    soup = BeautifulSoup(html, "html.parser")
    alle_schichten = []

    wochen_container = soup.find_all("div", class_="container")
    if not wochen_container:
        log.warning("Keine 'container' Elemente im HTML gefunden.")
    for woche_con in wochen_container:
        week_header = woche_con.find("div", class_="week-number") or woche_con.find("div", class_="week-header")
        if week_header:
            woche_raw = week_header.get_text(strip=True)
            match = re.search(r"(\d+)", woche_raw)
            woche = f"Woche {match.group(1)}" if match else woche_raw
        else:
            woche = ""

        # Erzeuge Mapping von Index->Datum aus der "top-row"
        days = []
        top_row = woche_con.find("div", class_="top-row")
        if not top_row:
            continue
        day_boxes = top_row.find_all("div", class_="day-des")
        for box in day_boxes:
            day_name_p = box.find("p", class_="day-name")
            tag_datum = get_day_and_hidden_date(day_name_p, box) if day_name_p else ""
            days.append(tag_datum)

        # Jetzt die Inhalte der Tages-Spalten
        week_table = woche_con.find("div", class_="week-table")
        if not week_table:
            continue
        day_contents = week_table.find_all("div", class_="day-content")
        for idx, day in enumerate(day_contents):
            tag_datum = days[idx] if idx < len(days) else ""
            time_blocks = day.find_all("div", class_="time-block")
            shift_containers = day.find_all("div", class_="shift-container")
            shift_container_idx = 0
            for t in time_blocks:
                zeit = t.get_text(strip=True).replace('\n', ' ')
                shift_container = None
                if shift_container_idx < len(shift_containers):
                    shift_container = shift_containers[shift_container_idx]
                    shift_container_idx += 1
                if shift_container:
                    for li in shift_container.find_all("li", class_="shift"):
                        tooltip = li.get("title") or li.get("data-tooltip") or ""
                        name_node = li.select_one(".shift-name p")
                        name = name_node.get_text(strip=True) if name_node else ""
                        bereich = li.get("data-area") or ""
                        if not bereich and tooltip:
                            parts = tooltip.split("|")
                            if len(parts) > 1:
                                bereich = parts[-1].strip()
                        alle_schichten.append([woche, tag_datum, zeit, name, bereich])
    return alle_schichten

# ---------- Google Sheets Hilfsfunktionen ----------
def remove_duplicates_in_sheet(ws, start_row=4):
    """
    Entfernt Duplikate ab start_row (1-indexed). Vergleicht (Datum im Format dd.mm.yyyy, Zeit, Bereich).
    Gibt Anzahl gelöschter Zeilen zurück.
    """
    all_rows = ws.get_all_values()[start_row-1:]
    seen = set()
    rows_to_delete = []
    for idx, row in enumerate(all_rows):
        if len(row) < 5:
            continue
        datum_key = extract_datum(row[1])
        key = (datum_key, row[2], row[4])
        if key in seen:
            rows_to_delete.append(start_row + idx)
        else:
            seen.add(key)
    for zeile in reversed(rows_to_delete):
        try:
            ws.delete_rows(zeile)
            time.sleep(1)
        except Exception as e:
            log.exception("Fehler beim Löschen Zeile %s: %s", zeile, e)
    return len(rows_to_delete)

def wochen_spalte_aktualisieren(ws, start_row=4):
    alle_zeilen = ws.get_all_values()[start_row-1:]
    wochen_liste = []
    for row in alle_zeilen:
        if len(row) > 1 and row[1].strip():
            m = re.match(r'\w+ (\d{1,2})\.?\s*([A-Za-zäöüÄÖÜß]+)\s+(\d{4})', row[1].strip())
            if m:
                tag = int(m.group(1))
                monat_raw = normalize_month_name(m.group(2))
                monat = MONATE_DE.get(monat_raw, 0)
                jahr = int(m.group(3))
                if monat > 0:
                    try:
                        dt = datetime(jahr, monat, tag)
                        kw = dt.isocalendar()[1]
                        wochen_liste.append([f"Woche {kw}"])
                    except Exception:
                        wochen_liste.append([""])
                else:
                    wochen_liste.append([""])
            else:
                wochen_liste.append([""])
        else:
            wochen_liste.append([""])
    if wochen_liste:
        end = start_row + len(wochen_liste) - 1
        ws.update(range_name=f"A{start_row}:A{end}", values=wochen_liste)

def batch_update_column_d(spreadsheet, ws_title, d_updates, block_size=100, pause=0.6):
    if not d_updates:
        return
    for i in range(0, len(d_updates), block_size):
        block = d_updates[i:i+block_size]
        data = []
        for zeilennr, name in block:
            data.append({
                "range": f"{ws_title}!D{zeilennr}",
                "majorDimension": "ROWS",
                "values": [[name]]
            })
        body = {"valueInputOption": "USER_ENTERED", "data": data}
        try:
            spreadsheet.values_batch_update(body)
        except Exception as e:
            log.exception("Fehler bei batch_update_column_d: %s", e)
        time.sleep(pause)

def sortiere_tabelle_nach_datum_zeit(ws, start_row=4):
    alle = ws.get_all_values()[start_row-1:]
    if not alle:
        return
    parsed = []
    for idx, row in enumerate(alle):
        while len(row) < 5:
            row.append("")
        raw_datum = row[1].strip()
        raw_zeit = row[2].strip()
        dt_key = None
        m = re.match(r'\w+\s+(\d{1,2})\.?\s*([A-Za-zäöüÄÖÜß]+)\s+(\d{4})', raw_datum)
        if m:
            day = int(m.group(1))
            month_raw = normalize_month_name(m.group(2))
            month = MONATE_DE.get(month_raw, 0)
            year = int(m.group(3))
            if month:
                try:
                    dt_key = datetime(year, month, day)
                except Exception:
                    dt_key = None
        time_key = (0, 0)
        m2 = re.match(r'(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})', raw_zeit)
        if m2:
            try:
                hour = int(m2.group(1))
                minute = int(m2.group(2))
                time_key = (hour, minute)
            except Exception:
                time_key = (0, 0)
        if dt_key is None:
            dt_key = datetime(9999, 12, 31)
        parsed.append((dt_key, time_key, row))
    parsed.sort(key=lambda x: (x[0], x[1]))
    sorted_rows = [p[2] for p in parsed]
    end_row = start_row + len(sorted_rows) - 1
    try:
        ws.update(range_name=f"A{start_row}:E{end_row}", values=sorted_rows)
    except Exception as e:
        log.exception("Fehler beim Schreiben sortierter Daten: %s", e)

# ---------- Hauptfunktion zum Schreiben ----------
def write_schichten_to_sheet(schichten_rows, start_row=3):
    log.info("Starte Dienstplan-Import")
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    try:
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
        gc = gspread.authorize(credentials)
        sh = gc.open_by_url(SPREADSHEET_URL)
        ws = sh.worksheet(TABNAME)
    except Exception as e:
        log.exception("Fehler bei Google-Authentifizierung / Öffnen der Tabelle: %s", e)
        raise

    try:
        ws.update(range_name="A3:E3", values=[["Woche", "Tag", "Zeit", "Name", "Bereich"]])
    except Exception:
        log.exception("Konnte Header nicht schreiben, setze fort...")

    schichten_rows.sort(key=lambda x: (x[0], tagdatum_sortkey(x[1]), x[2]))

    existing = ws.get_all_values()[3:]
    existing_map = {}
    for i, row in enumerate(existing):
        if len(row) >= 5:
            datum_key = extract_datum(row[1])
            key = (datum_key, row[2], row[4])
            name = row[3]
            zeilennr = 4 + i
            existing_map[key] = (name, zeilennr)

    neu_uebertragen = []
    korrigiert = []
    d_updates = []

    for entry in schichten_rows:
        datum_key = extract_datum(entry[1])
        key = (datum_key, entry[2], entry[4])
        name_neu = entry[3]
        if key in existing_map:
            ist_name, zeilennr = existing_map[key]
            if ist_name != name_neu:
                d_updates.append((zeilennr, name_neu))
                korrigiert.append(entry)
        else:
            neu_uebertragen.append(entry)

    if neu_uebertragen:
        try:
            ws.append_rows([e for e in neu_uebertragen], value_input_option="USER_ENTERED", table_range="A4:E")
            log.info("Neue Schichten eingetragen: %d", len(neu_uebertragen))
        except Exception as e:
            log.exception("Fehler beim Append neuer Zeilen: %s", e)

    num_dupes_removed = remove_duplicates_in_sheet(ws, start_row=4)
    wochen_spalte_aktualisieren(ws, start_row=4)
    sortiere_tabelle_nach_datum_zeit(ws, start_row=4)
    try:
        batch_update_column_d(sh, ws.title, d_updates)
    except Exception:
        log.exception("Fehler beim Batch-Update von Spalte D")
    zeitpunkt = datetime.now().strftime("Daten-Aktualisierung %d.%m.%Y %H:%M:%S")
    try:
        ws.update(range_name="A1", values=[[zeitpunkt]])
    except Exception:
        log.exception("Konnte Zeitpunkt nicht schreiben.")
    log.info("Zusammenfassung: neue=%d, korrigiert=%d, duplikate_entfernt=%d",
             len(neu_uebertragen), len(korrigiert), num_dupes_removed)
    if korrigiert:
        for sch in korrigiert:
            log.info("Korrigiert: %s | %s | %s | %s", sch[0], sch[1], sch[2], sch[3])

# ---------- CLI / Main ----------
def main():
    if not os.path.exists(HTML_FILE):
        log.error("HTML-Datei nicht gefunden: %s", HTML_FILE)
        return
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    schichten = parse_html_for_shifts(html)
    log.info("Gefundene Schichten im HTML: %d", len(schichten))
    write_schichten_to_sheet(schichten)

if __name__ == "__main__":
    main()