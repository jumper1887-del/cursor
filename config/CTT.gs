/************************************************************
  CTT – Aufbereitung der Segelliste für Terminal CTT
  Verbesserte Version mit:
    - Spalten-Konstanten
    - Zusätzlichen Kommentaren
    - Trigger-Funktion für automatische Ausführung
************************************************************/

function CTT() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sourceSheet = ss.getSheetByName('Segelliste');
  if (!sourceSheet) {
    Logger.log('Abbruch: Blatt "Segelliste" nicht gefunden.');
    return;
  }

  const targetSheet = ss.getSheetByName('CTT') || ss.insertSheet('CTT');
  targetSheet.clear();

  // Alle Daten aus "Segelliste"
  const data = sourceSheet.getDataRange().getValues();
  if (data.length < 2) {
    Logger.log('Keine Daten (nur Header?)');
    return;
  }

  const now = new Date();
  const excludeKeywords = ['kahn', 'Kahn'];

  /******************** SPALTEN-DEFINITIONEN *************************
    Passe diese Konstanten an, falls sich die Spalten-Reihenfolge ändert.
    INDEXE = 0-basiert!
  ********************************************************************/
  const COL_PLANNED_ARRIVAL   = 0;   // "Gepl. Ankunft"
  const COL_ACTUAL_ARRIVAL    = 1;   // "Tats. Ankunft"
  const COL_BERTH_OR_LOCATION = 2;   // "Liegeort" (== 'CTT')
  const COL_SHIP_NAME         = 4;   // "Schiff"
  const COL_PLANNED_DEPARTURE = 11;  // "Gepl. Abfahrt"
  const COL_ACTUAL_DEPARTURE  = 12;  // "Tats. Abfahrt"
  const COL_NOTE              = 13;  // Bemerkung / Notiz?

  // Aus "Schiffslänge": Spalte A = Name (0), Spalte C = Länge (2)
  const sizeSheet = ss.getSheetByName('Schiffslänge');
  const shipSizes = {};
  if (sizeSheet) {
    const sizeData = sizeSheet.getDataRange().getValues();
    for (let r = 1; r < sizeData.length; r++) {
      const n = sizeData[r][0];
      const len = sizeData[r][2];
      if (n) shipSizes[n] = len;
    }
  }

  // Datumsparser
  function parseDateTime(value) {
    if (value instanceof Date && !isNaN(value)) return value;
    if (value == null || value === '') return null;

    const s = value.toString().trim();
    const parts = s.split(' ');
    if (parts.length >= 2) {
      const dateParts = parts[0].split('.');
      const timeParts = parts[1].split(':');
      if (dateParts.length === 3 && timeParts.length >= 2) {
        return new Date(
          parseInt(dateParts[2], 10),
          parseInt(dateParts[1], 10) - 1,
          parseInt(dateParts[0], 10),
          parseInt(timeParts[0], 10),
          parseInt(timeParts[1], 10)
        );
      }
    }
    const d = new Date(s);
    return isNaN(d) ? null : d;
  }

  // Schichtlogik
  function getShiftWindow(now) {
    const day   = now.getDay();
    const year  = now.getFullYear();
    const month = now.getMonth();
    const date  = now.getDate();
    let start, end;
    const hour = now.getHours();

    // Mo–Fr
    if (day >= 1 && day <= 5) {
      if (hour >= 6 && hour < 14) {
        start = new Date(year, month, date, 6, 0);
        end   = new Date(year, month, date, 15, 0);
      } else if (hour >= 14 && hour < 22) {
        start = new Date(year, month, date, 14, 0);
        end   = new Date(year, month, date, 23, 0);
      } else {
        // Nacht: 22–07 (Tageswechsel beachten)
        start = hour >= 22
          ? new Date(year, month, date, 22, 0)
          : new Date(year, month, date - 1, 22, 0);
        end   = hour >= 22
          ? new Date(year, month, date + 1, 7, 0)
          : new Date(year, month, date, 7, 0);
      }
    } else {
      // Sa/So
      start = new Date(year, month, date, 6, 0);
      end   = new Date(year, month, date, 19, 0);
    }
    return { start, end };
  }

  const window = getShiftWindow(now);

  // Ergebnis-Container
  const here   = [];
  const coming = [];
  const gone   = [];

  // Hauptschleife (ohne Header)
  for (let i = 1; i < data.length; i++) {
    const row = data[i];

    // Filter Liegeort
    if (row[COL_BERTH_OR_LOCATION] !== 'CTT') continue;

    const shipName         = row[COL_SHIP_NAME] || '-';
    const plannedArrival   = parseDateTime(row[COL_PLANNED_ARRIVAL])   || '-';
    const actualArrival    = parseDateTime(row[COL_ACTUAL_ARRIVAL])    || '-';
    const plannedDeparture = parseDateTime(row[COL_PLANNED_DEPARTURE]) || '-';
    const actualDeparture  = parseDateTime(row[COL_ACTUAL_DEPARTURE])  || '-';
    const note             = row[COL_NOTE];

    // Ausschluss nach (Notiz-)Keywords
    if (note && excludeKeywords.some(k => note.toString().toLowerCase().includes(k.toLowerCase()))) continue;

    // Ohne geplante Abfahrt kein sinnvoller Zeitrahmen
    if (plannedDeparture === '-') continue;

    const shipSize = shipSizes[shipName] || '-';

    // Vor Ort
    if (actualArrival !== '-' &&
        actualArrival <= now &&
        plannedDeparture >= now) {
      here.push([shipName, plannedArrival, actualArrival, plannedDeparture, actualDeparture, shipSize]);
    }

    // Kommend (geplant im Schichtfenster + (noch) nicht angekommen)
    if (plannedArrival !== '-' &&
        plannedArrival >= window.start &&
        plannedArrival <= window.end &&
        (actualArrival === '-' || actualArrival > now)) {
      coming.push([shipName, plannedArrival, actualArrival, plannedDeparture, actualDeparture, shipSize]);
    }

    // Weg in Schicht (± 1 Stunde)
    if (actualDeparture !== '-') {
      const windowStartMinus1 = new Date(window.start.getTime() - 60 * 60 * 1000);
      const windowEndPlus1    = new Date(window.end.getTime()   + 60 * 60 * 1000);
      if (actualDeparture >= windowStartMinus1 && actualDeparture <= windowEndPlus1) {
        gone.push([shipName, plannedArrival, actualArrival, plannedDeparture, actualDeparture, shipSize]);
      }
    }
  }

  /*************** AUSGABE ins CTT-Blatt ***************/
  // Abschnitt 1: Vor Ort
  targetSheet.getRange(1, 1, 1, 6).setValues([[
    'Schiff (vor Ort)', 'Gepl. Ankunft', 'Tats. Ankunft', 'Gepl. Abfahrt', 'Tats. Abfahrt', 'Länge'
  ]]).setFontWeight('bold').setFontSize(13).setBackground('#F4F4F4');

  if (here.length > 0) {
    targetSheet.getRange(2, 1, here.length, 6).setValues(here);
  }

  // Abschnitt 2: Kommend
  const COMING_HEADER_ROW = 15;
  targetSheet.getRange(COMING_HEADER_ROW, 1, 1, 6).setValues([[
    'Schiff (kommend)', 'Gepl. Ankunft', 'Tats. Ankunft', 'Gepl. Abfahrt', 'Tats. Abfahrt', 'Länge'
  ]]).setFontWeight('bold').setFontSize(13).setBackground('#F7F7F7');

  if (coming.length > 0) {
    targetSheet.getRange(COMING_HEADER_ROW + 1, 1, coming.length, 6).setValues(coming);
  }

  // Abschnitt 3: Weg in Schicht
  const GONE_HEADER_ROW = 30;
  targetSheet.getRange(GONE_HEADER_ROW, 1, 1, 6).setValues([[
    'Schiff (weg in Schicht)', 'Gepl. Ankunft', 'Tats. Ankunft', 'Gepl. Abfahrt', 'Tats. Abfahrt', 'Länge'
  ]]).setFontWeight('bold').setFontSize(13).setBackground('#EFEFEF');

  if (gone.length > 0) {
    targetSheet.getRange(GONE_HEADER_ROW + 1, 1, gone.length, 6).setValues(gone);
  }

  // Spalte F Inhalte (evtl. alte Reste) bereinigen
  if (targetSheet.getLastRow() > 1) {
    targetSheet.getRange(2, 6, targetSheet.getLastRow(), 1).clearContent();
  }

  // Datumsformat auf Spalten B–E anwenden (Zeilen 2..Ende)
  const lastRow = targetSheet.getLastRow();
  if (lastRow >= 2) {
    targetSheet
      .getRange(2, 2, lastRow - 1, 4)
      .setNumberFormat('dd.MM.yyyy HH:mm');
  }

  // Letzte Aktualisierung
  targetSheet.getRange('G1:I1').merge();
  targetSheet.getRange('G1')
    .setHorizontalAlignment('center')
    .setValue(
      'Letzte Aktualisierung: ' +
      Utilities.formatDate(now, Session.getScriptTimeZone(), 'dd.MM.yyyy HH:mm')
    );
}

/************************************************************
  Trigger-Funktion
  Führt CTT automatisch aus:
    - Alle 2 Stunden
    - Zusätzlich um 12:00 und 14:00
************************************************************/
function createTrigger() {
  // Alte Trigger für CTT löschen
  const allTriggers = ScriptApp.getProjectTriggers();
  for (let t of allTriggers) {
    if (t.getHandlerFunction() === 'CTT') {
      ScriptApp.deleteTrigger(t);
    }
  }

  // Alle 2 Stunden
  ScriptApp.newTrigger('CTT')
    .timeBased()
    .everyHours(2)
    .create();


}
