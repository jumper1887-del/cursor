import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RefreshCcw } from 'lucide-react';
import ShipList from './ShipList';
import ShipSummaryCard from './ShipSummaryCard';
import LiveMapBlock from './LiveMapBlock'; // Import the new LiveMapBlock component
import { format, addHours, isAfter } from 'date-fns';
import { de } from 'date-fns/locale';
import { parseGermanDateTime, isWeekend } from '@/utils/date-helpers';
import { cn } from '@/lib/utils';
import { TableColumn, TableRowData } from '@/types/table';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { useQuery, useQueryClient } from '@tanstack/react-query'; // Import useQuery and useQueryClient

interface ShipScheduleProps {
  addMessage: (type: 'error' | 'success' | 'info', content: string) => void;
  onLastUpdatedChange: (lastUpdated: string) => void;
}

// Define specific interfaces for each table's row data
interface ShipsOnSiteRowData extends TableRowData {
  Schiff: string;
  GeplAnkunft: string;
  TatsAnkunft: string;
  GeplAbkunft: string;
  TatsAbfahrt: string;
}

interface IncomingShipsRowData extends TableRowData {
  Schiff: string;
  GeplAnkunft: string;
  TatsAnkunft: string;
  GeplAbkunft: string;
  TatsAbfahrt: string;
  Bemerkung?: string; // Optional, da es generisch über TableRowData gehandhabt wird
}

interface ArchivedShipsRowData extends TableRowData {
  Schiff: string;
  GeplAnkunft: string;
  DatumUhrzeit: string; // This is 'Tats. Ankunft' from original, but renamed for clarity in archived
  GeplAbfahrt: string;
  TatsAbfahrt: string;
}

// Define a type for the combined fetched data
interface ShipScheduleData {
  shipsOnSite: ShipsOnSiteRowData[];
  incomingShips: IncomingShipsRowData[];
  archivedShips: ArchivedShipsRowData[];
  lastUpdated: string;
  cttH1Value: string;
  nextArrivalTime: string;
  nextDepartureTime: string;
}

const ShipSchedule: React.FC<ShipScheduleProps> = ({ addMessage, onLastUpdatedChange }) => {
  const queryClient = useQueryClient(); // Initialize useQueryClient
  const sheetId = '1Q_Dvufm0LCUxYtktMtM18Xz30sXQxCnGfI9SSDFPUNw';
  const shipsOnSiteRange = 'CTT!A2:E14'; 
  const incomingShipsRange = 'CTT!A16:F29'; // Column F still fetched for 'Bemerkung'
  const archiveSheetRange = 'CTT!A31';
  const archivedShipsListRange = 'CTT!A31:E45';
  const lastUpdatedDateRange = 'Segelliste!A1'; 
  const cttH1Range = 'CTT!H1'; // New range for CTT!H1
  const nextArrivalTimeRange = 'CTT!I7';
  const nextDepartureTimeRange = 'CTT!I11';
  const seagoingVesselFlagRange = 'CTT!A:N'; 
  const edgeFunctionUrl = `https://jjbxfpfczkdiwhihhsdu.supabase.co/functions/v1/google-sheets-api`;

  const [filterTimeRange, setFilterTimeRange] = useState<number | null>(24); // Default to 24 hours
  const [filterWeekend, setFilterWeekend] = useState<boolean>(false); // New state for weekend filter

  // Column definitions for each table
  const shipsOnSiteColumns: TableColumn<ShipsOnSiteRowData>[] = [
    { id: 'col1', header: 'Schiff', accessor: 'Schiff', isSortable: true },
    { id: 'col2', header: 'Gepl. Ankunft', accessor: 'GeplAnkunft', isSortable: true },
    { id: 'col3', header: 'Tats. Ankunft', accessor: 'TatsAnkunft', isSortable: true },
    { id: 'col4', header: 'Gepl. Abfahrt', accessor: 'GeplAbkunft', isSortable: true },
    { id: 'col5', header: 'Tats. Abfahrt', accessor: 'TatsAbfahrt', editable: 'datetime', isSortable: true },
  ];

  const incomingShipsColumns: TableColumn<IncomingShipsRowData>[] = [
    { id: 'col1', header: 'Schiff', accessor: 'Schiff', isSortable: true },
    { id: 'col2', header: 'Gepl. Ankunft', accessor: 'GeplAnkunft', isSortable: true },
    { id: 'col3', header: 'Tats. Ankunft', accessor: 'TatsAnkunft', editable: 'datetime', isSortable: true },
    { id: 'col4', header: 'Gepl. Abfahrt', accessor: 'GeplAbkunft', isSortable: true },
    { id: 'col5', header: 'Tats. Abfahrt', accessor: 'TatsAbfahrt', isSortable: true, hidden: true }, // Diese Spalte wird ausgeblendet
  ];

  const archivedShipsColumns: TableColumn<ArchivedShipsRowData>[] = [
    { id: 'col1', header: 'Schiff (weg in Schicht)', accessor: 'Schiff', isSortable: true },
    { id: 'col2', header: 'Gepl. Ankunft', accessor: 'GeplAnkunft', isSortable: true },
    { id: 'col3', header: 'Datum & Uhrzeit', accessor: 'DatumUhrzeit', isSortable: true },
    { id: 'col4', header: 'Gepl. Abfahrt', accessor: 'GeplAbkunft', isSortable: true },
    { id: 'col5', header: 'Tats. Abfahrt', accessor: 'TatsAbfahrt', isSortable: true },
  ];

  const mapRawDataToShipsOnSite = (rawData: string[][]): ShipsOnSiteRowData[] => {
    return rawData.map(row => ({
      Schiff: row[0] || '',
      GeplAnkunft: row[1] || '',
      TatsAnkunft: row[2] || '',
      GeplAbkunft: row[3] || '',
      TatsAbfahrt: row[4] || '',
    }));
  };

  const mapRawDataToIncomingShips = (rawData: string[][]): IncomingShipsRowData[] => {
    return rawData.map(row => ({
      Schiff: row[0] || '',
      GeplAnkunft: row[1] || '',
      TatsAnkunft: row[2] || '',
      GeplAbkunft: row[3] || '',
      TatsAbfahrt: row[4] || '',
      Bemerkung: row[5] || '', // Map Bemerkung to generic TableRowData
    }));
  };

  const mapRawDataToArchivedShips = (rawData: string[][]): ArchivedShipsRowData[] => {
    return rawData.map(row => ({
      Schiff: row[0] || '',
      GeplAnkunft: row[1] || '',
      DatumUhrzeit: row[2] || '',
      GeplAbfahrt: row[3] || '',
      TatsAbfahrt: row[4] || '',
    }));
  };

  const fetchShipScheduleData = useCallback(async (): Promise<ShipScheduleData> => {
    try {
      const response = await fetch(edgeFunctionUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: 'fetch_data',
          sheetId: sheetId,
          ranges: [
            shipsOnSiteRange,
            incomingShipsRange,
            archivedShipsListRange,
            lastUpdatedDateRange, 
            seagoingVesselFlagRange, 
            nextArrivalTimeRange,
            nextDepartureTimeRange,
            cttH1Range,
          ],
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        const errorDetails = data.error || 'Unbekannter Fehler beim Abrufen der Google Sheet-Daten.';
        const detailedError = `HTTP Status: ${response.status}\nNachricht: ${errorDetails}`;
        throw new Error(detailedError);
      }

      if (data && Array.isArray(data) && data.length === 8) {
        const fetchedShipsOnSiteData = data[0];
        const fetchedIncomingShipsData = data[1];
        const fetchedArchivedShipsData = data[2];
        const fetchedLastUpdatedDateTime = data[3]; 
        // data[4] is seagoingVesselFlagRange, not directly used here
        const fetchedNextArrivalTimeData = data[5];
        const fetchedNextDepartureTimeData = data[6];
        const fetchedCttH1Value = data[7];

        const shipsOnSite = mapRawDataToShipsOnSite(fetchedShipsOnSiteData);
        
        let processedIncomingShips: string[][] = [];
        if (fetchedIncomingShipsData.length > 0) {
          const incomingRows = fetchedIncomingShipsData
            .filter(row => row[0] && row[0].trim() !== '')
            .map(row => {
              const newRow = [...row];
              while (newRow.length < 6) {
                newRow.push('');
              }
              return newRow;
            });
          processedIncomingShips = incomingRows;
        }
        const incomingShips = mapRawDataToIncomingShips(processedIncomingShips);

        const processedArchivedShips = fetchedArchivedShipsData
          .filter(row => row[0] && row[0].trim() !== '')
          .map(row => {
            const newRow = [...row];
            while (newRow.length < 5) {
              newRow.push('');
            }
            return newRow;
          });
        const archivedShips = mapRawDataToArchivedShips(processedArchivedShips);

        let combinedLastUpdated = '';
        if (fetchedLastUpdatedDateTime && fetchedLastUpdatedDateTime.length > 0 && fetchedLastUpdatedDateTime[0].length > 0) {
          const rawDateTime = fetchedLastUpdatedDateTime[0][0];
          const parsedDate = parseGermanDateTime(rawDateTime);
          combinedLastUpdated = parsedDate ? format(parsedDate, 'dd.MM.yyyy HH:mm', { locale: de }) : '';
          onLastUpdatedChange(combinedLastUpdated);
        } else {
          onLastUpdatedChange('');
        }

        const cttH1 = (fetchedCttH1Value && fetchedCttH1Value.length > 0 && fetchedCttH1Value[0].length > 0) 
          ? fetchedCttH1Value[0][0] 
          : '';

        const nextArrival = (fetchedNextArrivalTimeData && fetchedNextArrivalTimeData.length > 0 && fetchedNextArrivalTimeData[0].length > 0)
          ? (parseGermanDateTime(fetchedNextArrivalTimeData[0][0]) ? format(parseGermanDateTime(fetchedNextArrivalTimeData[0][0])!, 'dd.MM.yyyy HH:mm', { locale: de }) : 'Keine')
          : 'Keine';

        const nextDeparture = (fetchedNextDepartureTimeData && fetchedNextDepartureTimeData.length > 0 && fetchedNextDepartureTimeData[0].length > 0)
          ? (parseGermanDateTime(fetchedNextDepartureTimeData[0][0]) ? format(parseGermanDateTime(fetchedNextDepartureTimeData[0][0])!, 'dd.MM.yyyy HH:mm', { locale: de }) : 'Keine')
          : 'Keine';

        addMessage('success', 'Google Sheet-Daten erfolgreich abgerufen!');
        return {
          shipsOnSite,
          incomingShips,
          archivedShips,
          lastUpdated: combinedLastUpdated,
          cttH1Value: cttH1,
          nextArrivalTime: nextArrival,
          nextDepartureTime: nextDeparture,
        };
      } else {
        throw new Error('Unerwartetes Datenformat von Google Sheets erhalten. Erwartete 8 Bereiche.');
      }
    } catch (error: any) {
      console.error('Fehler beim Abrufen der Tabellendaten:', error);
      const detailedErrorMessage = `Fehler beim Abrufen der Google Sheet-Daten:\n${error.message || 'Ein unbekannter Fehler ist aufgetreten.'}`;
      addMessage('error', detailedErrorMessage);
      throw error; // Re-throw to let useQuery handle the error state
    }
  }, [addMessage, edgeFunctionUrl, sheetId, lastUpdatedDateRange, nextArrivalTimeRange, nextDepartureTimeRange, onLastUpdatedChange, seagoingVesselFlagRange]);

  const { data, isLoading, isFetching, refetch } = useQuery<ShipScheduleData, Error>({
    queryKey: ['shipScheduleData'],
    queryFn: fetchShipScheduleData,
    staleTime: 5 * 60 * 1000, // Data is considered fresh for 5 minutes
    refetchOnWindowFocus: true, // Refetch when window regains focus
    refetchInterval: 10 * 60 * 1000, // Refetch every 10 minutes in the background
    onError: (error) => {
      addMessage('error', `Fehler beim Laden der Daten: ${error.message}`);
    },
    onSuccess: () => {
      // This is handled by fetchShipScheduleData directly
    }
  });

  const shipsOnSiteData = data?.shipsOnSite || [];
  const incomingShipsData = data?.incomingShips || [];
  const archivedShipsData = data?.archivedShips || [];
  const lastUpdated = data?.lastUpdated || '';
  const cttH1Value = data?.cttH1Value || '';
  const nextArrivalTime = data?.nextArrivalTime || 'Keine';
  const nextDepartureTime = data?.nextDepartureTime || 'Keine';

  const handleRefresh = () => {
    refetch();
  };

  // Filtered incoming ships data based on filterTimeRange and filterWeekend
  const filteredIncomingShips = useMemo(() => {
    if (!incomingShipsData) {
      return [];
    }

    let filteredData = incomingShipsData;

    // Apply time range filter
    if (filterTimeRange !== null) {
      const now = new Date();
      const cutoffTime = addHours(now, filterTimeRange);

      filteredData = filteredData.filter(ship => {
        const plannedArrival = parseGermanDateTime(ship.GeplAnkunft);
        return plannedArrival && isAfter(plannedArrival, now) && isAfter(cutoffTime, plannedArrival);
      });
    }

    // Apply weekend filter
    if (filterWeekend) {
      filteredData = filteredData.filter(ship => {
        const plannedArrival = parseGermanDateTime(ship.GeplAnkunft);
        return plannedArrival && isWeekend(plannedArrival);
      });
    }

    return filteredData;
  }, [incomingShipsData, filterTimeRange, filterWeekend]);


  const handleCellEdit = async (
    rowIndex: number,
    columnId: string,
    newValue: string,
    dataType: 'shipsOnSite' | 'incomingShips'
  ) => {
    let currentData: TableRowData[];
    let sheetName: string; 
    let actualSheetRowOffset: number;
    let colIndex: number;
    let columnsDef: TableColumn<any>[];

    if (dataType === 'shipsOnSite') {
      currentData = shipsOnSiteData;
      sheetName = 'CTT';
      actualSheetRowOffset = 2; 
      columnsDef = shipsOnSiteColumns;
    } else { // incomingShips
      currentData = incomingShipsData;
      sheetName = 'CTT';
      actualSheetRowOffset = 16; 
      columnsDef = incomingShipsColumns;
    }

    const column = columnsDef.find(col => col.id === columnId);
    if (!column) {
      addMessage('error', 'Fehler: Spaltendefinition nicht gefunden.');
      return;
    }
    colIndex = columnsDef.indexOf(column);

    if (!currentData || !currentData[rowIndex]) {
      addMessage('error', 'Fehler: Daten für die Bearbeitung nicht gefunden.');
      return;
    }

    const originalRow = { ...currentData[rowIndex] };
    // Optimistic update: Update local state immediately for responsiveness
    queryClient.setQueryData<ShipScheduleData>(['shipScheduleData'], (oldData) => {
      if (!oldData) return oldData;
      const updatedTableData = [...(dataType === 'shipsOnSite' ? oldData.shipsOnSite : oldData.incomingShips)];
      updatedTableData[rowIndex] = { ...updatedTableData[rowIndex], [column.accessor]: newValue };
      return {
        ...oldData,
        [dataType === 'shipsOnSite' ? 'shipsOnSite' : 'incomingShips']: updatedTableData,
      };
    });

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
      if (dataType === 'incomingShips' && column.accessor === 'TatsAnkunft' && newValue) { 
        const rowToMove = currentData[rowIndex]; // Use currentData[rowIndex] to get the full row including Bemerkung

        let targetOnSiteRowIndex = -1;
        if (shipsOnSiteData) {
            for (let i = 0; i < shipsOnSiteData.length; i++) {
                if (!shipsOnSiteData[i].Schiff) { // Check if 'Schiff' column is empty
                    targetOnSiteRowIndex = i;
                    break;
                }
            }
        }

        if (targetOnSiteRowIndex !== -1) {
            const actualTargetSheetRow = targetOnSiteRowIndex + 2;
            const targetRange = `CTT!A${actualTargetSheetRow}:E${actualTargetSheetRow}`; 

            console.log("Moving ship:", rowToMove.Schiff);
            console.log("GeplAnkunft:", rowToMove.GeplAnkunft);
            console.log("TatsAnkunft:", rowToMove.TatsAnkunft);
            console.log("GeplAbfahrt (from incoming):", rowToMove.GeplAbkunft); 
            console.log("TatsAbfahrt:", rowToMove.TatsAbfahrt);
            console.log("Bemerkung (from incoming):", rowToMove.Bemerkung); 

            const updateOnSiteResponse = await fetch(edgeFunctionUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    action: 'update_cell', 
                    sheetId: sheetId,
                    range: targetRange,
                    values: [[
                      rowToMove.Schiff, 
                      rowToMove.GeplAnkunft, 
                      rowToMove.TatsAnkunft, 
                      rowToMove.GeplAbkunft, 
                      rowToMove.TatsAbfahrt,
                    ]], 
                }),
            });

            if (!updateOnSiteResponse.ok) {
                const errorData = await updateOnSiteResponse.json();
                throw new Error(errorData.error || 'Fehler beim Kopieren des Schiffs zu "Schiff (vor Ort)".');
            }
            addMessage('success', `Schiff "${rowToMove.Schiff}" erfolgreich zu "Schiff (vor Ort)" kopiert (Zeile ${actualTargetSheetRow}).`);

            // Optimistic update for shipsOnSiteData after moving
            queryClient.setQueryData<ShipScheduleData>(['shipScheduleData'], (oldData) => {
              if (!oldData) return oldData;
              const newShipsOnSite = [...oldData.shipsOnSite];
              newShipsOnSite[targetOnSiteRowIndex] = {
                Schiff: rowToMove.Schiff, 
                GeplAnkunft: rowToMove.GeplAnkunft, 
                TatsAnkunft: rowToMove.TatsAnkunft, 
                GeplAbkunft: rowToMove.GeplAbkunft, 
                TatsAbfahrt: rowToMove.TatsAbfahrt,
              };
              return { ...oldData, shipsOnSite: newShipsOnSite };
            });

        } else {
            addMessage('error', 'Fehler: Kein freier Platz in der Liste "Schiff (vor Ort)" gefunden (A2:E14 ist voll).');
        }
      }
      
      // Logic for archiving ships on site if 'Tats. Abfahrt' is set
      if (dataType === 'shipsOnSite' && column.accessor === 'TatsAbfahrt' && newValue) { 
        const updatedRow = { ...currentData[rowIndex], [column.accessor]: newValue }; // Use updated value for archiving

        const appendResponse = await fetch(edgeFunctionUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            action: 'append_row',
            sheetId: sheetId,
            range: archiveSheetRange,
            values: [[
              updatedRow.Schiff, 
              updatedRow.GeplAnkunft, 
              updatedRow.TatsAnkunft, 
              updatedRow.GeplAbkunft, 
              updatedRow.TatsAbfahrt,
            ]],
          }),
        });

        if (!appendResponse.ok) {
          const errorData = await appendResponse.json();
          throw new Error(errorData.error || 'Fehler beim Archivieren der Zeile in Google Sheets.');
        }
        addMessage('success', `Schiffszeile erfolgreich im Archiv gespeichert: ${updatedRow.Schiff}`);

        const emptyRow = {
          Schiff: '',
          GeplAnkunft: '',
          TatsAnkunft: '',
          GeplAbkunft: '', 
          TatsAbfahrt: '',
        }; 
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
                values: [[
                  emptyRow.Schiff, 
                  emptyRow.GeplAnkunft, 
                  emptyRow.TatsAnkunft, 
                  emptyRow.GeplAbkunft, 
                  emptyRow.TatsAbfahrt,
                ]],
            }),
        });

        if (!clearResponse.ok) {
            const errorData = await clearResponse.json();
            throw new Error(errorData.error || 'Fehler beim Leeren der Zeile in "Schiff (vor Ort)".');
        }
      addMessage('success', `Zeile ${actualSheetRow} in "Schiff (vor Ort)" geleert.`);

        // Optimistic update for shipsOnSiteData after clearing
        queryClient.setQueryData<ShipScheduleData>(['shipScheduleData'], (oldData) => {
          if (!oldData) return oldData;
          const newShipsOnSite = [...oldData.shipsOnSite];
          newShipsOnSite[rowIndex] = emptyRow;
          return { ...oldData, shipsOnSite: newShipsOnSite };
        });
      }
      
      queryClient.invalidateQueries({ queryKey: ['shipScheduleData'] }); // Invalidate to refetch in background

    } catch (error: any) {
      console.error('Fehler bei der Google Sheets-Operation:', error);
      addMessage('error', `Fehler bei der Datenaktualisierung: ${error.message}`);
      // Rollback optimistic update if backend update failed
      queryClient.setQueryData<ShipScheduleData>(['shipScheduleData'], (oldData) => {
        if (!oldData) return oldData;
        const revertedTableData = [...(dataType === 'shipsOnSite' ? oldData.shipsOnSite : oldData.incomingShips)];
        revertedTableData[rowIndex] = originalRow;
        return {
          ...oldData,
          [dataType === 'shipsOnSite' ? 'shipsOnSite' : 'incomingShips']: revertedTableData,
        };
      });
    }
  };

  const totalShipsOnSite = shipsOnSiteData 
    ? shipsOnSiteData.filter(row => row.Schiff && row.Schiff.trim() !== '').length 
    : 0;

  return (
    <React.Fragment>
      <div 
        className="w-full max-w-4xl mx-auto mt-8 space-y-6 transition-all duration-300"
      >
        <Card className="relative">
          <CardHeader>
            <div className="flex flex-col items-center justify-center w-full">
              <CardTitle className="text-center">
                Schiffsfahrplan
              </CardTitle>
              {lastUpdated && (
                <CardDescription className="text-xs text-muted-foreground font-normal mt-1">
                  Zuletzt aktualisiert: {lastUpdated}
                </CardDescription>
              )}
              {cttH1Value && (
                <CardDescription className="text-xs text-muted-foreground font-normal mt-1">
                  {cttH1Value}
                </CardDescription>
              )}
            </div>
            <div className="absolute top-4 right-4 flex space-x-2">
              <Button variant="outline" size="icon" onClick={handleRefresh} disabled={isLoading || isFetching} title="Daten aktualisieren">
                <RefreshCcw className={cn("h-4 w-4", (isLoading || isFetching) && "animate-spin")} />
              </Button>
            </div>
          </CardHeader>
        </Card>

        <ShipSummaryCard
          title="" 
          summaryItems={[
            { title: "Gesamt", value: totalShipsOnSite.toString() },
            { title: "Anker", value: "2" }, 
            { title: "Kai", value: "3" },   
            { title: "Zusatzinfo 2", value: "Wert B" }, // Hier getauscht
            { title: "Nächste Ankunft", value: nextArrivalTime },
            { title: "Nächste Abfahrt", value: nextDepartureTime }, // Hier getauscht
          ]}
        />

        <ShipList
          title="Schiffe an der Kai" 
          columns={shipsOnSiteColumns}
          data={shipsOnSiteData}
          onCellEdit={(rowIndex, columnId, newValue) => handleCellEdit(rowIndex, columnId, newValue, 'shipsOnSite')}
        />

        <ShipList
          title="Ankommende Schiffe"
          columns={incomingShipsColumns}
          data={filteredIncomingShips}
          onCellEdit={(rowIndex, columnId, newValue) => handleCellEdit(rowIndex, columnId, newValue, 'incomingShips')}
          headerRightContent={
            <div className="flex items-center space-x-2">
              <Select 
                value={filterWeekend ? "weekend" : (filterTimeRange?.toString() || "null")} 
                onValueChange={(value) => {
                  if (value === "weekend") {
                    setFilterWeekend(true);
                    setFilterTimeRange(null); // Deaktiviert den Zeitfilter, wenn Wochenende ausgewählt ist
                  } else {
                    setFilterWeekend(false);
                    setFilterTimeRange(value === "null" ? null : Number(value));
                  }
                }}
              >
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="Filter Stunden" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="8">Nächste 8 Stunden</SelectItem>
                  <SelectItem value="16">Nächste 16 Stunden</SelectItem>
                  <SelectItem value="24">Nächste 24 Stunden</SelectItem>
                  <SelectItem value="weekend">Wochenende</SelectItem> {/* Neuer Filter */}
                  <SelectItem value="null">Alle anzeigen</SelectItem>
                </SelectContent>
              </Select>
            </div>
          }
        />

        <ShipList
          title="Abgehende Schiffe"
          columns={archivedShipsColumns}
          data={archivedShipsData}
        />

        {/* Live Map Block */}
        <LiveMapBlock 
          title="Live Karte" 
          height="2000" 
          latitude="53.53164823009202" 
          longitude="9.946495614952774" 
          zoom="14" 
          names={true}
          // mmsi="123456789" // Uncomment and set if tracking a single ship
          // imo="1234567" // Uncomment and set if tracking a single ship
          // show_track={true} // Uncomment to show track line
          fleet="e48ab3d80a0e2a9bf28930f2dd08800c" 
          fleet_name="Carnival" 
          fleet_timespan="1440" 
        />
      </div>
    </React.Fragment>
  );
};

export default ShipSchedule;