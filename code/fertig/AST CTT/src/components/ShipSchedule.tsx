import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RefreshCcw } from 'lucide-react'; // Nur RefreshCcw importieren
import ShipList from './ShipList';
import { format } from 'date-fns';
import { de } from 'date-fns/locale';
import { parseGermanDateTime, isFuture } from '@/utils/date-helpers';

interface ShipScheduleProps {
  addMessage: (type: 'error' | 'success' | 'info', content: string) => void;
}

const findNextEvent = (
  data: string[][],
  eventColumnIndex: number,
  hasHeaderRow: boolean
): Date | null => {
  let nextEvent: Date | null = null;
  const startIndex = hasHeaderRow ? 1 : 0;

  for (let i = startIndex; i < data.length; i++) {
    const row = data[i];
    // Only consider rows that have a ship name (first column is not empty)
    if (row[0] && row[0].trim() !== '' && row.length > eventColumnIndex) {
      const eventString = row[eventColumnIndex];
      const parsedDate = parseGermanDateTime(eventString);

      if (parsedDate && isFuture(parsedDate)) {
        if (!nextEvent || parsedDate.getTime() < nextEvent.getTime()) {
          nextEvent = parsedDate;
        }
      }
    }
  }
  return nextEvent;
};

const ShipSchedule: React.FC<ShipScheduleProps> = ({ addMessage }) => {
  const sheetId = '1Q_Dvufm0LCUxYtktMtM18Xz30sXQxCnGfI9SSDFPUNw';
  const shipsOnSiteRange = 'CTT!A2:E14'; 
  const incomingShipsRange = 'CTT!A15:F29';
  const archiveSheetRange = 'CTT!A31';
  const archivedShipsListRange = 'CTT!A31:E45';
  const lastUpdatedRange = 'CTT!G1:I1';
  const segellisteRange = 'Segelliste!A:N'; // Bereich für die Segelliste
  const edgeFunctionUrl = `https://jjbxfpfczkdiwhihhsdu.supabase.co/functions/v1/google-sheets-api`;

  const [shipsOnSiteData, setShipsOnSiteData] = useState<string[][] | null>(null);
  const [incomingShipsData, setIncomingShipsData] = useState<string[][] | null>(null);
  const [archivedShipsData, setArchivedShipsData] = useState<string[][] | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [seagoingVessels, setSeagoingVessels] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [nextArrivalTime, setNextArrivalTime] = useState<string>('Keine');
  const [nextDepartureTime, setNextDepartureTime] = useState<string>('Keine');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(edgeFunctionUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: 'fetch_data',
          sheetId: sheetId,
          ranges: [shipsOnSiteRange, incomingShipsRange, archivedShipsListRange, lastUpdatedRange, segellisteRange],
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        const errorDetails = data.error || 'Unbekannter Fehler beim Abrufen der Google Sheet-Daten.';
        const detailedError = `HTTP Status: ${response.status}\nNachricht: ${errorDetails}`;
        throw new Error(detailedError);
      }

      if (data && Array.isArray(data) && data.length === 5) {
        const fetchedShipsOnSiteData = data[0];
        const fetchedIncomingShipsData = data[1];
        const fetchedArchivedShipsData = data[2];
        const fetchedLastUpdatedData = data[3];
        const fetchedSegellisteData = data[4];

        setShipsOnSiteData(fetchedShipsOnSiteData);
        
        let processedIncomingShips: string[][] = [];
        if (fetchedIncomingShipsData.length > 0) {
          const incomingHeader = fetchedIncomingShipsData[0];
          const incomingRows = fetchedIncomingShipsData.slice(1)
            .filter(row => row[0] && row[0].trim() !== '')
            .map(row => {
              const newRow = [...row];
              while (newRow.length < 6) {
                newRow.push('');
              }
              return newRow;
            });
          processedIncomingShips = [incomingHeader, ...incomingRows];
        }
        setIncomingShipsData(processedIncomingShips);

        const processedArchivedShips = fetchedArchivedShipsData
          .filter(row => row[0] && row[0].trim() !== '')
          .map(row => {
            const newRow = [...row];
            while (newRow.length < 5) {
              newRow.push('');
            }
            return newRow;
          });
        setArchivedShipsData(processedArchivedShips);

        if (fetchedLastUpdatedData && fetchedLastUpdatedData.length > 0 && fetchedLastUpdatedData[0].length > 0) {
          setLastUpdated(fetchedLastUpdatedData[0][0]);
        } else {
          setLastUpdated('');
        }

        const newSeagoingVessels = new Set<string>();
        if (fetchedSegellisteData && fetchedSegellisteData.length > 0) {
          for (let i = 1; i < fetchedSegellisteData.length; i++) {
            const row = fetchedSegellisteData[i];
            // Konvertiere Schiffsnamen zu Kleinbuchstaben für konsistenten Vergleich
            if (row[0] && row[0].trim() !== '' && row[13] && row[13].trim() !== '') {
              newSeagoingVessels.add(row[0].trim().toLowerCase());
            }
          }
        }
        setSeagoingVessels(newSeagoingVessels);
        console.log('Seagoing Vessels Set (lowercase):', newSeagoingVessels); // Debugging-Ausgabe

        addMessage('success', 'Google Sheet-Daten erfolgreich abgerufen!');

        const nextArrivalOnSite = findNextEvent(fetchedShipsOnSiteData, 1, false);
        const nextArrivalIncoming = findNextEvent(processedIncomingShips, 1, true); 

        let overallNextArrival: Date | null = null;
        if (nextArrivalOnSite && (!overallNextArrival || nextArrivalOnSite.getTime() < overallNextArrival.getTime())) {
          overallNextArrival = nextArrivalOnSite;
        }
        if (nextArrivalIncoming && (!overallNextArrival || nextArrivalIncoming.getTime() < overallNextArrival.getTime())) {
          overallNextArrival = nextArrivalIncoming;
        }
        setNextArrivalTime(overallNextArrival ? format(overallNextArrival, 'dd.MM.yyyy HH:mm', { locale: de }) : 'Keine');

        const nextDepartureOnSite = findNextEvent(fetchedShipsOnSiteData, 3, false);
        const nextDepartureIncoming = findNextEvent(processedIncomingShips, 3, true); 

        let overallNextDeparture: Date | null = null;
        if (nextDepartureOnSite && (!overallNextDeparture || nextDepartureOnSite.getTime() < overallNextDeparture.getTime())) {
          overallNextDeparture = nextDepartureOnSite;
        }
        if (nextDepartureIncoming && (!overallNextArrival || nextDepartureIncoming.getTime() < overallNextDeparture.getTime())) {
          overallNextDeparture = nextDepartureIncoming;
        }
        setNextDepartureTime(overallNextDeparture ? format(overallNextDeparture, 'dd.MM.yyyy HH:mm', { locale: de }) : 'Keine');

      } else {
        throw new Error('Unerwartetes Datenformat von Google Sheets erhalten.');
      }
    } catch (error: any) {
      console.error('Fehler beim Abrufen der Tabellendaten:', error);
      const detailedErrorMessage = `Fehler beim Abrufen der Google Sheet-Daten:\n${error.message || 'Ein unbekannter Fehler ist aufgetreten.'}`;
      addMessage('error', detailedErrorMessage);
    } finally {
      setLoading(false);
    }
  }, [addMessage, edgeFunctionUrl, sheetId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Die handlePrint-Funktion wird nicht mehr benötigt, da der Button entfernt wird.

  const handleCellEdit = async (
    rowIndex: number,
    colIndex: number,
    newValue: string,
    dataType: 'shipsOnSite' | 'incomingShips'
  ) => {
    let currentData: string[][] | null;
    let sheetName: string; 
    let actualSheetRowOffset: number; 

    if (dataType === 'shipsOnSite') {
      currentData = shipsOnSiteData;
      sheetName = 'CTT';
      actualSheetRowOffset = 2; 
    } else { // incomingShips
      currentData = incomingShipsData;
      sheetName = 'CTT';
      actualSheetRowOffset = 16; 
    }

    if (!currentData || !currentData[rowIndex]) {
      addMessage('error', 'Fehler: Daten für die Bearbeitung nicht gefunden.');
      return;
    }

    const originalRow = currentData[rowIndex];
    const updatedRow = [...originalRow];
    updatedRow[colIndex] = newValue;

    // Update local state immediately for responsiveness
    if (dataType === 'shipsOnSite') {
      setShipsOnSiteData(prevData => {
        if (!prevData) return null;
        const newData = [...prevData];
        newData[rowIndex] = updatedRow;
        return newData;
      });
    } else {
      setIncomingShipsData(prevData => {
        if (!prevData) return null;
        const newData = [...prevData];
        newData[rowIndex] = updatedRow;
        return newData;
      });
    }

    const actualSheetRow = rowIndex + actualSheetRowOffset;
    const columnLetter = String.fromCharCode(65 + colIndex);
    const cellToUpdate = `${columnLetter}${actualSheetRow}`;
    const fullRangeToUpdate = `${sheetName}!${cellToUpdate}`;

    try {
      // 1. Update the cell in Google Sheets
      const updateResponse = await fetch(edgeFunctionUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: 'update_cell',
          sheetId: sheetId,
          range: fullRangeToUpdate,
          values: [[newValue]],
        }),
      });

      if (!updateResponse.ok) {
        const errorData = await updateResponse.json();
        throw new Error(errorData.error || 'Fehler beim Aktualisieren der Zelle in Google Sheets.');
      }

      addMessage('success', `Zelle in Google Sheets aktualisiert: ${fullRangeToUpdate} auf "${newValue}"`);

      // Logic for moving incoming ship to on-site if 'Tats. Ankunft' is set
      if (dataType === 'incomingShips' && colIndex === 2 && newValue) { 
        const rowToMove = updatedRow; 

        let targetOnSiteRowIndex = -1;
        if (shipsOnSiteData) {
            for (let i = 0; i < shipsOnSiteData.length; i++) {
                if (!shipsOnSiteData[i][0]) {
                    targetOnSiteRowIndex = i;
                    break;
                }
            }
        }

        if (targetOnSiteRowIndex !== -1) {
            const actualTargetSheetRow = targetOnSiteRowIndex + 2;
            const targetRange = `CTT!A${actualTargetSheetRow}:E${actualTargetSheetRow}`;

            const updateOnSiteResponse = await fetch(edgeFunctionUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    action: 'update_cell', 
                    sheetId: sheetId,
                    range: targetRange,
                    values: [rowToMove.slice(0, 5)], // Nur die ersten 5 Spalten kopieren (A-E)
                }),
            });

            if (!updateOnSiteResponse.ok) {
                const errorData = await updateOnSiteResponse.json();
                throw new Error(errorData.error || 'Fehler beim Kopieren des Schiffs zu "Schiff (vor Ort)".');
            }
            addMessage('success', `Schiff "${rowToMove[0]}" erfolgreich zu "Schiff (vor Ort)" kopiert (Zeile ${actualTargetSheetRow}).`);

            setShipsOnSiteData(prevData => {
                if (!prevData) return null;
                const newData = [...prevData];
                newData[targetOnSiteRowIndex] = rowToMove.slice(0, 5); // Nur die ersten 5 Spalten aktualisieren
                return newData;
            });

        } else {
            addMessage('error', 'Fehler: Kein freier Platz in der Liste "Schiff (vor Ort)" gefunden (A2:E14 ist voll).');
        }
      }
      
      // Logic for archiving ships on site if 'Tats. Abfahrt' is set
      if (dataType === 'shipsOnSite' && colIndex === 4 && newValue) { 
        const rowToArchive = updatedRow;

        const appendResponse = await fetch(edgeFunctionUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            action: 'append_row',
            sheetId: sheetId,
            range: archiveSheetRange,
            values: [rowToArchive],
          }),
        });

        if (!appendResponse.ok) {
          const errorData = await appendResponse.json();
          throw new Error(errorData.error || 'Fehler beim Archivieren der Zeile in Google Sheets.');
        }
        addMessage('success', `Schiffszeile erfolgreich im Archiv gespeichert: ${rowToArchive[0]}`);

        const emptyRow = ['', '', '', '', '']; 
        const clearRange = `CTT!A${actualSheetRow}:E${actualSheetRow}`;

        const clearResponse = await fetch(edgeFunctionUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                action: 'update_cell',
                sheetId: sheetId,
                range: clearRange,
                values: [emptyRow],
            }),
        });

        if (!clearResponse.ok) {
            const errorData = await clearResponse.json();
            throw new Error(errorData.error || 'Fehler beim Leeren der Zeile in "Schiff (vor Ort)".');
        }
        addMessage('success', `Zeile ${actualSheetRow} in "Schiff (vor Ort)" geleert.`);

        setShipsOnSiteData(prevData => {
            if (!prevData) return null;
            const newData = [...prevData];
            newData[rowIndex] = emptyRow;
            return newData;
        });
      }
      
      // Re-fetch all data to ensure UI is in sync with Google Sheets after any operation
      fetchData();

    } catch (error: any) {
      console.error('Fehler bei der Google Sheets-Operation:', error);
      addMessage('error', `Fehler bei der Datenaktualisierung: ${error.message}`);
      // Revert local state if backend update failed
      if (dataType === 'shipsOnSite') {
        setShipsOnSiteData(prevData => {
          if (!prevData) return null;
          const newData = [...prevData];
          newData[rowIndex] = originalRow;
          return newData;
        });
      } else {
        setIncomingShipsData(prevData => {
          if (!prevData) return null;
          const newData = [...prevData];
          newData[rowIndex] = originalRow;
          return newData;
        });
      }
    }
  };

  return (
    <Card className="w-full max-w-4xl mx-auto mt-8">
      <CardHeader className="relative">
        <div className="flex flex-col items-center justify-center w-full">
          <CardTitle className="text-center">Schiffsfahrplan</CardTitle>
          {lastUpdated && (
            <span className="text-xs text-muted-foreground mt-1">
              {lastUpdated}
            </span>
          )}
        </div>
        <CardDescription className="text-center">
          Schiffsdaten werden direkt von Google Sheets abgerufen.
        </CardDescription>
        <div className="absolute top-4 right-4 flex space-x-2">
          {/* Drucker-Button entfernt */}
          <Button variant="outline" size="icon" onClick={fetchData} disabled={loading} title="Daten aktualisieren">
            <RefreshCcw className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {loading ? (
          <p className="text-center text-muted-foreground">Lade Schiffsdaten...</p>
        ) : (
          <div className="space-y-8">
            <ShipList
              title="Schiff (vor Ort)"
              data={shipsOnSiteData || []}
              customHeaders={["Schiff", "Gepl. Ankunft", "Tats. Ankunft", "Gepl. Abfahrt", "Tats. Abfahrt"]}
              summaryCardsData={[
                { title: "Gesamt", value: "5" },
                { title: "Anker", value: "2" },
                { title: "Kai", value: "3" },
                { title: "Nächste Ankunft", value: nextArrivalTime },
                { title: "Nächste Abfahrt", value: nextDepartureTime },
              ]}
              onCellEdit={(rowIndex, colIndex, newValue) => handleCellEdit(rowIndex, colIndex, newValue, 'shipsOnSite')}
              editableColumns={{ 4: 'datetime' }} 
              seagoingVessels={seagoingVessels}
            />
            <ShipList
              title="Schiff (kommend)"
              data={incomingShipsData || []}
              onCellEdit={(rowIndex, colIndex, newValue) => handleCellEdit(rowIndex, colIndex, newValue, 'incomingShips')}
              editableColumns={{ 2: 'datetime' }} 
              seagoingVessels={seagoingVessels}
            />
            {archivedShipsData && archivedShipsData.length > 0 && (
              <ShipList
                title="Schiff (weg in Schicht)"
                data={archivedShipsData}
                customHeaders={["Schiff (weg in Schicht)", "Gepl. Ankunft", "Datum & Uhrzeit", "Gepl. Abfahrt", "Tats. Abfahrt"]}
                seagoingVessels={seagoingVessels}
              />
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ShipSchedule;