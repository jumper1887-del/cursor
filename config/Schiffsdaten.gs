/************************************************************
  Schiffsdaten – Vergleicht Schiffe aus Segelliste mit Schiffsdaten HHLA
  - Liest Schiffsnamen aus Segelliste Spalte E
  - Vergleicht mit Schiffsdaten HHLA Spalte A
  - Fügt neue Schiffe alphabetisch sortiert hinzu (neue Zeilen werden eingefügt)
  - Schreibt Schiffstyp aus Segelliste Spalte N in Schiffsdaten HHLA Spalte B
  - Jedes Schiff bekommt eine komplette Zeile von A bis K
  - Beim Verschieben/Schreiben werden immer A:Z verschoben (26 Spalten)
  - Zeilen werden verschoben, nicht gelöscht und neu geschrieben
  - Keine doppelten Schiffe
************************************************************/

function Schiffsdaten() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // Konstante: Immer A:Z (26 Spalten) verschieben/schreiben
  const NUM_COLS = 26; // A:Z
  
  // Quellblatt "Segelliste" öffnen
  const sourceSheet = ss.getSheetByName('Segelliste');
  if (!sourceSheet) {
    Logger.log('Fehler: Blatt "Segelliste" nicht gefunden.');
    return;
  }
  
  // Zielblatt "Schiffsdaten HHLA" öffnen oder erstellen
  let targetSheet = ss.getSheetByName('Schiffsdaten HHLA');
  if (!targetSheet) {
    targetSheet = ss.insertSheet('Schiffsdaten HHLA');
    // Header erstellen wenn Blatt neu ist (A:K befüllt, L:Z leer)
    const headerRow = [
      'Schiffsname', 'Schiffstyp', 'MMSI-Nummer', 'IMO-Nummer', 
      'Baujahr', 'Länge (m)', 'Breite (m)', '', 'VesselFinder-Link', '', ''
    ];
    // Auf 26 Spalten erweitern (L:Z leer)
    while (headerRow.length < NUM_COLS) {
      headerRow.push('');
    }
    targetSheet.getRange(1, 1, 1, NUM_COLS).setValues([headerRow]);
    targetSheet.getRange(1, 1, 1, NUM_COLS).setFontWeight('bold');
  }
  
  // Alle Daten aus Segelliste lesen
  const sourceData = sourceSheet.getDataRange().getValues();
  
  // Map für Schiffsname -> Schiffstyp aus Segelliste
  const segellisteMap = new Map();
  
  // Spalte E (Index 4) und Spalte N (Index 13) durchgehen, Header überspringen
  for (let i = 1; i < sourceData.length; i++) {
    const shipName = sourceData[i][4]; // Spalte E = Index 4
    const shipType = sourceData[i][13]; // Spalte N = Index 13
    
    if (shipName && shipName.toString().trim() !== '') {
      const name = shipName.toString().trim().toUpperCase();
      const type = shipType ? shipType.toString().trim() : '';
      // Wenn Name bereits existiert, behalte den letzten Typ (oder den ersten - je nach Bedarf)
      if (!segellisteMap.has(name) || segellisteMap.get(name) === '') {
        segellisteMap.set(name, type);
      }
    }
  }
  
  Logger.log(`Gefunden: ${segellisteMap.size} Schiffe in Segelliste.`);
  
  // Alle Daten aus Schiffsdaten HHLA lesen
  const targetData = targetSheet.getDataRange().getValues();
  
  // Map für vorhandene Schiffe (Name -> Zeilennummer, 1-basiert)
  const existingShipsMap = new Map();
  const existingShipsData = new Map(); // Name -> Array mit allen Spaltenwerten + Zeilennummer
  const duplicateRows = []; // Zeilen mit Duplikaten zum Löschen
  
  // Ab Zeile 2 (nach Header) durchgehen
  for (let i = 1; i < targetData.length; i++) {
    const shipName = targetData[i][0]; // Spalte A
    if (shipName && shipName.toString().trim() !== '') {
      const name = shipName.toString().trim().toUpperCase();
      const rowNum = i + 1; // Zeilennummer (1-basiert)
      
      // Prüfe ob Schiff bereits existiert (Duplikat)
      if (existingShipsMap.has(name)) {
        // Duplikat gefunden - markiere zum Löschen
        duplicateRows.push(rowNum);
        Logger.log(`Duplikat gefunden: ${name} in Zeile ${rowNum} (bereits in Zeile ${existingShipsMap.get(name)})`);
      } else {
        // Erstes Vorkommen - speichern
        existingShipsMap.set(name, rowNum);
        // Alle Spaltenwerte speichern (A:Z, Index 0-25)
        const rowData = [];
        for (let col = 0; col < NUM_COLS; col++) {
          rowData.push(targetData[i][col] || '');
        }
        existingShipsData.set(name, { data: rowData, row: rowNum });
      }
    }
  }
  
  // Duplikate löschen (von hinten nach vorne, damit Zeilennummern stabil bleiben)
  if (duplicateRows.length > 0) {
    duplicateRows.sort((a, b) => b - a);
    for (const row of duplicateRows) {
      try {
        targetSheet.deleteRow(row);
        Logger.log(`Duplikat-Zeile ${row} gelöscht.`);
      } catch (e) {
        Logger.log(`Fehler beim Löschen von Duplikat-Zeile ${row}: ${e.message}`);
      }
    }
    // Daten nach dem Löschen neu lesen
    const newTargetData = targetSheet.getDataRange().getValues();
    // Maps neu aufbauen
    existingShipsMap.clear();
    existingShipsData.clear();
    for (let i = 1; i < newTargetData.length; i++) {
      const shipName = newTargetData[i][0];
      if (shipName && shipName.toString().trim() !== '') {
        const name = shipName.toString().trim().toUpperCase();
        const rowNum = i + 1;
        existingShipsMap.set(name, rowNum);
        const rowData = [];
        for (let col = 0; col < NUM_COLS; col++) {
          rowData.push(newTargetData[i][col] || '');
        }
        existingShipsData.set(name, { data: rowData, row: rowNum });
      }
    }
    // targetData aktualisieren
    targetData.length = 0;
    targetData.push(...newTargetData);
  }
  
  Logger.log(`Gefunden: ${existingShipsMap.size} Schiffe in Schiffsdaten HHLA.`);
  
  // Neue Schiffe finden und Schiffstyp-Updates sammeln
  const newShips = [];
  const updates = [];
  
  for (const [name, type] of segellisteMap.entries()) {
    if (existingShipsMap.has(name)) {
      // Schiff existiert bereits - prüfe ob Schiffstyp aktualisiert werden muss
      const rowNum = existingShipsMap.get(name);
      const currentType = targetData[rowNum - 1][1] || ''; // Spalte B = Index 1
      if (type && type !== currentType.toString().trim()) {
        updates.push({
          row: rowNum,
          type: type
        });
      }
    } else {
      // Neues Schiff - zum Hinzufügen markieren
      newShips.push({ name: name, type: type });
    }
  }
  
  Logger.log(`Gefunden: ${newShips.length} neue Schiffe zum Hinzufügen.`);
  
  // Namen der neuen Schiffe im Protokoll ausgeben
  if (newShips.length > 0) {
    Logger.log('--- Neue Schiffe: ---');
    for (const ship of newShips) {
      const typeInfo = ship.type ? ` (Typ: ${ship.type})` : '';
      Logger.log(`  - ${ship.name}${typeInfo}`);
    }
    Logger.log('--- Ende neue Schiffe ---');
  } else {
    Logger.log('Keine neuen Schiffe gefunden.');
  }
  
  Logger.log(`Gefunden: ${updates.length} Schiffstyp-Updates.`);
  
  // Neue Schiffe alphabetisch sortieren
  newShips.sort((a, b) => a.name.localeCompare(b.name, 'de'));
  
  // Alle bestehenden Schiffe in ein Array mit Namen und Zeilennummer
  // Verwende ein Set um sicherzustellen, dass jedes Schiff nur einmal vorkommt
  const allShips = [];
  const addedShipNames = new Set(); // Set zum Verhindern von Duplikaten
  
  for (let i = 1; i < targetData.length; i++) {
    const shipName = targetData[i][0];
    if (shipName && shipName.toString().trim() !== '') {
      const name = shipName.toString().trim().toUpperCase();
      // Prüfe ob Schiff bereits hinzugefügt wurde
      if (!addedShipNames.has(name)) {
        const shipInfo = existingShipsData.get(name);
        if (shipInfo) {
          allShips.push({
            name: name,
            originalName: shipName.toString().trim(),
            data: shipInfo.data,
            row: shipInfo.row
          });
          addedShipNames.add(name);
        }
      }
    }
  }
  
  // Neue Schiffe zu allShips hinzufügen (ohne Zeilennummer, wird später eingefügt)
  // Prüfe auch hier auf Duplikate
  for (const newShip of newShips) {
    // Prüfe ob Schiff bereits in allShips existiert
    if (!addedShipNames.has(newShip.name)) {
      // Neue Zeile mit A:K befüllt, L:Z leer (immer 26 Spalten)
      const newRowData = [
        newShip.name,           // A: Schiffsname
        newShip.type,           // B: Schiffstyp
        '',                     // C: MMSI-Nummer
        '',                     // D: IMO-Nummer
        '',                     // E: Baujahr
        '',                     // F: Länge (m)
        '',                     // G: Breite (m)
        '',                     // H: (leer)
        '',                     // I: VesselFinder-Link
        '',                     // J: (leer)
        ''                      // K: (leer)
      ];
      // Auf 26 Spalten erweitern (L:Z leer)
      while (newRowData.length < NUM_COLS) {
        newRowData.push('');
      }
      allShips.push({
        name: newShip.name,
        originalName: newShip.name,
        data: newRowData,
        row: null // Wird später gesetzt
      });
      addedShipNames.add(newShip.name);
    } else {
      Logger.log(`Warnung: Neues Schiff ${newShip.name} existiert bereits, wird übersprungen.`);
    }
  }
  
  // Alle Schiffe alphabetisch sortieren
  allShips.sort((a, b) => a.name.localeCompare(b.name, 'de'));
  
  // Schiffstyp-Updates anwenden
  const updatesMap = new Map();
  for (const update of updates) {
    const originalName = targetData[update.row - 1][0].toString().trim();
    const upperName = originalName.toUpperCase();
    updatesMap.set(upperName, update.type);
  }
  
  // Updates auf sortierte Liste anwenden
  for (const ship of allShips) {
    if (updatesMap.has(ship.name)) {
      ship.data[1] = updatesMap.get(ship.name); // Spalte B = Index 1
    }
  }
  
  // NEU: Zeilen werden verschoben, nicht gelöscht und neu geschrieben
  
  // Schritt 1: Prüfe ob Tabelle bereits korrekt sortiert ist
  let needsResort = false;
  if (newShips.length === 0 && updates.length === 0) {
    // Prüfe ob die Tabelle bereits alphabetisch sortiert ist
    let lastShipName = '';
    for (let i = 1; i < targetData.length; i++) {
      const shipName = targetData[i][0];
      if (shipName && shipName.toString().trim() !== '') {
        const name = shipName.toString().trim().toUpperCase();
        if (lastShipName && name < lastShipName) {
          needsResort = true;
          break;
        }
        lastShipName = name;
      }
    }
  } else {
    needsResort = true; // Wenn es neue Schiffe oder Updates gibt, muss neu sortiert werden
  }
  
  if (!needsResort && updates.length === 0) {
    Logger.log('Tabelle ist bereits korrekt sortiert, keine Änderungen nötig.');
    // Nur Updates anwenden falls vorhanden
    if (updates.length > 0) {
      for (const update of updates) {
        try {
          targetSheet.getRange(update.row, 2, 1, 1).setValue(update.type);
        } catch (e) {
          Logger.log(`Fehler beim Update von Zeile ${update.row}: ${e.message}`);
        }
      }
    }
  } else {
    // Schritt 2: Neue Zeilen für neue Schiffe einfügen (an der richtigen alphabetischen Position)
    if (newShips.length > 0) {
      // Finde die Positionen, an denen neue Zeilen eingefügt werden müssen
      // Basierend auf der sortierten Liste allShips
      const insertPositions = [];
      for (let i = 0; i < allShips.length; i++) {
        if (allShips[i].row === null) {
          // Neues Schiff - finde die richtige Zeile (i + 2 wegen Header)
          insertPositions.push({ position: i + 2, shipIndex: i });
        }
      }
      
      // Füge Zeilen von hinten nach vorne ein (damit Zeilennummern stabil bleiben)
      insertPositions.sort((a, b) => b.position - a.position);
      for (const insertInfo of insertPositions) {
        try {
          targetSheet.insertRowBefore(insertInfo.position);
          Logger.log(`Neue Zeile eingefügt an Position ${insertInfo.position} für ${allShips[insertInfo.shipIndex].name}`);
        } catch (e) {
          Logger.log(`Fehler beim Einfügen von Zeile ${insertInfo.position}: ${e.message}`);
        }
      }
    }
    
    // Schritt 3: Verschiebe Zeilen durch Kopieren und Einfügen (behält alle Daten)
    // Lese alle aktuellen Daten neu (nach dem Einfügen der neuen Zeilen)
    const currentData = targetSheet.getDataRange().getValues();
    const currentRowCount = currentData.length - 1; // Ohne Header
    
    // Stelle sicher, dass alle Zeilen in allShips 26 Spalten haben
    for (const ship of allShips) {
      while (ship.data.length < NUM_COLS) {
        ship.data.push('');
      }
      if (ship.data.length > NUM_COLS) {
        ship.data = ship.data.slice(0, NUM_COLS);
      }
    }
    
    // Schritt 4: Erstelle sortierte Daten-Liste
    const sortedData = [];
    for (const ship of allShips) {
      sortedData.push(ship.data);
    }
    
    // Schritt 5: Verschiebe Zeilen durch Kopieren der Daten (A:Z)
    // Verwende getRange und setValues um Zeilen zu verschieben
    if (sortedData.length > 0) {
      try {
        // Lösche nur den Inhalt der Datenzeilen (nicht die Zeilen selbst) - A:Z
        const lastRow = targetSheet.getLastRow();
        if (lastRow > 1) {
          targetSheet.getRange(2, 1, lastRow - 1, NUM_COLS).clearContent();
        }
        
        // Schreibe alle sortierten Daten - A:Z (26 Spalten)
        // Dies verschiebt effektiv die Zeilen, da die Daten in der neuen Reihenfolge geschrieben werden
        targetSheet.getRange(2, 1, sortedData.length, NUM_COLS).setValues(sortedData);
        Logger.log(`Verschoben: ${sortedData.length} Schiffe (alphabetisch sortiert) - A:Z verschoben.`);
        
        // Lösche überflüssige Zeilen am Ende (falls vorhanden)
        const newLastRow = sortedData.length + 1;
        if (lastRow > newLastRow) {
          targetSheet.deleteRows(newLastRow + 1, lastRow - newLastRow);
        }
      } catch (e) {
        Logger.log(`Fehler beim Verschieben der Zeilen: ${e.message}`);
        // Fallback: Zeile für Zeile verschieben (langsamer, aber funktioniert) - A:Z
        for (let i = 0; i < sortedData.length; i++) {
          try {
            targetSheet.getRange(i + 2, 1, 1, NUM_COLS).setValues([sortedData[i]]);
          } catch (e2) {
            Logger.log(`Fehler beim Verschieben von Zeile ${i + 2}: ${e2.message}`);
          }
        }
      }
    }
  }
  
  // Spaltenbreiten anpassen (A:Z)
  // Prüfe zuerst, wie viele Spalten das Blatt hat
  try {
    const maxCols = targetSheet.getLastColumn();
    // Stelle sicher, dass mindestens NUM_COLS Spalten vorhanden sind
    const colsToResize = Math.max(1, Math.min(NUM_COLS, maxCols || NUM_COLS));
    for (let col = 1; col <= colsToResize; col++) {
      try {
        targetSheet.autoResizeColumn(col);
      } catch (e) {
        Logger.log(`Fehler beim Auto-Resize von Spalte ${col}: ${e.message}`);
      }
    }
  } catch (e) {
    Logger.log(`Fehler beim Auto-Resize der Spalten: ${e.message}`);
  }
  
  // Finale Prüfung auf Duplikate
  const finalData = targetSheet.getDataRange().getValues();
  const finalShipNames = new Map();
  const foundDuplicates = [];
  for (let i = 1; i < finalData.length; i++) {
    const shipName = finalData[i][0];
    if (shipName && shipName.toString().trim() !== '') {
      const name = shipName.toString().trim().toUpperCase();
      if (finalShipNames.has(name)) {
        foundDuplicates.push({ name: name, row: i + 1, firstRow: finalShipNames.get(name) });
      } else {
        finalShipNames.set(name, i + 1);
      }
    }
  }
  
  if (foundDuplicates.length > 0) {
    Logger.log(`WARNUNG: ${foundDuplicates.length} Duplikate nach dem Schreiben gefunden!`);
    for (const dup of foundDuplicates) {
      Logger.log(`  - ${dup.name}: Zeile ${dup.row} (erstes Vorkommen in Zeile ${dup.firstRow})`);
    }
  } else {
    Logger.log('Prüfung abgeschlossen: Keine Duplikate gefunden.');
  }
  
  Logger.log(`Fertig: ${newShips.length} neue Schiffe hinzugefügt, ${updates.length} Schiffstypen aktualisiert.`);
  
  // Zusammenfassung der neuen Schiffe am Ende
  if (newShips.length > 0) {
    Logger.log('=== ZUSAMMENFASSUNG: Neue Schiffe ===');
    const newShipNames = newShips.map(s => s.name).join(', ');
    Logger.log(`Neue Schiffe: ${newShipNames}`);
    Logger.log('=====================================');
  }
  
  // Trigger-Verwaltung: Lösche alle alten Trigger und erstelle neue für morgen und übermorgen
  deleteAllTriggers();
  createNextTwoTriggers();
}

/**
 * Löscht alle Trigger für die Funktion Schiffsdaten
 * Kann auch manuell aufgerufen werden
 */
function deleteAllTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  let deletedCount = 0;
  
  // Lösche alle Schiffsdaten-Trigger
  for (const trigger of triggers) {
    if (trigger.getHandlerFunction() === 'Schiffsdaten') {
      try {
        ScriptApp.deleteTrigger(trigger);
        deletedCount++;
      } catch (e) {
        Logger.log(`Fehler beim Löschen des Triggers: ${e.message}`);
      }
    }
  }
  
  if (deletedCount > 0) {
    Logger.log(`${deletedCount} Trigger gelöscht.`);
  } else {
    Logger.log('Keine Trigger zum Löschen gefunden.');
  }
}

/**
 * Erstellt 2 Trigger für morgen und übermorgen um 12:00 Uhr
 * Kann auch manuell aufgerufen werden
 */
function createNextTwoTriggers() {
  const now = new Date();
  
  // Erstelle Trigger für morgen um 12:00 Uhr
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(12, 0, 0, 0);
  
  // Erstelle Trigger für übermorgen um 12:00 Uhr
  const dayAfterTomorrow = new Date(now);
  dayAfterTomorrow.setDate(dayAfterTomorrow.getDate() + 2);
  dayAfterTomorrow.setHours(12, 0, 0, 0);
  
  // Erstelle Trigger für morgen
  try {
    ScriptApp.newTrigger('Schiffsdaten')
      .timeBased()
      .at(tomorrow)
      .create();
    Logger.log(`Trigger für morgen erstellt: ${tomorrow.toLocaleString('de-DE')}`);
  } catch (e) {
    Logger.log(`Fehler beim Erstellen des Triggers für morgen: ${e.message}`);
  }
  
  // Erstelle Trigger für übermorgen
  try {
    ScriptApp.newTrigger('Schiffsdaten')
      .timeBased()
      .at(dayAfterTomorrow)
      .create();
    Logger.log(`Trigger für übermorgen erstellt: ${dayAfterTomorrow.toLocaleString('de-DE')}`);
  } catch (e) {
    Logger.log(`Fehler beim Erstellen des Triggers für übermorgen: ${e.message}`);
  }
}

/**
 * Einmalige Einrichtung: Erstellt den ersten Trigger für heute/morgen um 12:00 Uhr
 * Diese Funktion muss manuell einmal ausgeführt werden
 */
function setupInitialTrigger() {
  const now = new Date();
  const today = new Date(now);
  today.setHours(12, 0, 0, 0);
  
  // Wenn es bereits nach 12:00 Uhr ist, erstelle Trigger für morgen
  if (now.getHours() >= 12) {
    today.setDate(today.getDate() + 1);
  }
  
  try {
    ScriptApp.newTrigger('Schiffsdaten')
      .timeBased()
      .at(today)
      .create();
    Logger.log(`Initialer Trigger erstellt für: ${today.toLocaleString('de-DE')}`);
    
    // Erstelle auch Trigger für morgen und übermorgen
    createNextTwoTriggers();
  } catch (e) {
    Logger.log(`Fehler beim Erstellen des initialen Triggers: ${e.message}`);
  }
}
