import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Separator } from "@/components/ui/separator";
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { parseGermanDateTime } from '@/utils/date-helpers';
import DateTimePicker from './DateTimePicker';
import { format } from 'date-fns';
import { de } from 'date-fns/locale';
import { Input } from "@/components/ui/input";
import { cn } from '@/lib/utils';

interface ShipListProps {
  title: string;
  data: string[][];
  summaryCardsData?: { title: string; value: string }[];
  customHeaders?: string[];
  onCellEdit?: (rowIndex: number, colIndex: number, newValue: string) => void;
  editableColumns?: { [colIndex: number]: 'datetime' | 'text' };
  seagoingVessels?: Set<string>;
}

const ShipList: React.FC<ShipListProps> = ({ title, data, summaryCardsData, customHeaders, onCellEdit, editableColumns, seagoingVessels }) => {
  const [sortColumn, setSortColumn] = useState<number | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  if (!data || data.length === 0) {
    return (
      <Card className="w-full max-w-4xl mx-auto">
        <CardHeader>
          <CardTitle className="text-center">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-center text-muted-foreground">Keine Daten verfügbar.</p>
        </CardContent>
      </Card>
    );
  }

  const headers = customHeaders && customHeaders.length > 0 ? customHeaders : data[0];
  const rawRows = customHeaders && customHeaders.length > 0 ? data : data.slice(1);

  const handleSort = (columnIndex: number) => {
    if (sortColumn === columnIndex) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(columnIndex);
      setSortDirection('asc');
    }
  };

  const sortedRows = useMemo(() => {
    if (sortColumn === null) {
      return rawRows;
    }

    const sortableRows = [...rawRows];
    const isDateColumn = (header: string) => header.includes('Ankunft') || header.includes('Abfahrt');

    sortableRows.sort((a, b) => {
      const aValue = a[sortColumn];
      const bValue = b[sortColumn];

      if (isDateColumn(headers[sortColumn])) {
        const dateA = parseGermanDateTime(aValue);
        const dateB = parseGermanDateTime(bValue);

        if (dateA && dateB) {
          return sortDirection === 'asc' ? dateA.getTime() - dateB.getTime() : dateB.getTime() - dateA.getTime();
        }
        if (dateA === null && dateB === null) return 0;
        if (dateA === null) return sortDirection === 'asc' ? 1 : -1;
        if (dateB === null) return sortDirection === 'asc' ? -1 : 1;
        return 0;
      } else {
        return sortDirection === 'asc' ? aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
      }
    });
    return sortableRows;
  }, [rawRows, sortColumn, sortDirection, headers]);

  return (
    <Card className="w-full max-w-4xl mx-auto">
      <CardHeader>
        <CardTitle className="text-center">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {summaryCardsData && summaryCardsData.length > 0 && (
          <Card className="mb-4 p-0">
            <CardContent className="flex flex-col sm:flex-row justify-around items-stretch p-0">
              {summaryCardsData.map((card, index) => (
                <React.Fragment key={index}>
                  <div className="flex-1 p-2 text-center flex flex-col justify-center">
                    <p className="text-xs font-medium text-muted-foreground">{card.title}</p>
                    <p className={cn(
                      "text-sm font-bold",
                      card.value === 'Keine' ? 'text-green-600 dark:text-green-400' : ''
                    )}>
                      {card.value}
                    </p>
                  </div>
                  {index < summaryCardsData.length - 1 && (
                    <Separator orientation="vertical" className="hidden sm:block h-auto my-2" />
                  )}
                  {index < summaryCardsData.length - 1 && (
                    <Separator orientation="horizontal" className="sm:hidden w-auto mx-2" />
                  )}
                </React.Fragment>
              ))}
            </CardContent>
          </Card>
        )}
        <div className="border rounded-md">
          <Table>
            <TableHeader>
              <TableRow>
                {headers.map((header, index) => (
                  <TableHead key={index} className="cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800" onClick={() => handleSort(index)}>
                    <div className="flex items-center gap-1">
                      {header}
                      {sortColumn === index ? (
                        sortDirection === 'asc' ? (
                          <ArrowUp className="ml-1 h-4 w-4" />
                        ) : (
                          <ArrowDown className="ml-1 h-4 w-4" />
                        )
                      ) : (
                        <ArrowUpDown className="ml-1 h-4 w-4 text-muted-foreground" />
                      )}
                    </div>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedRows.map((row, rowIndex) => (
                <TableRow key={rowIndex}>
                  {headers.map((_, cellIndex) => {
                    const cell = row[cellIndex] || '';
                    const editableType = editableColumns ? editableColumns[cellIndex] : undefined;
                    const isEditable = !!editableType;
                    const originalRowIndex = rawRows.indexOf(row); 

                    // Überprüfen, ob es die erste Spalte (Schiffsname) ist und ob es ein Seeschiff ist
                    const isShipNameColumn = cellIndex === 0;
                    // Konvertiere den Zellwert zu Kleinbuchstaben für konsistenten Vergleich
                    const isSeagoing = isShipNameColumn && seagoingVessels?.has(cell.trim().toLowerCase());
                    console.log(`Checking ship: "${cell.trim().toLowerCase()}", Is seagoing: ${isSeagoing}`); // Debugging-Ausgabe

                    if (isEditable && onCellEdit) {
                      if (editableType === 'datetime') {
                        const currentDateTime = parseGermanDateTime(cell);
                        return (
                          <TableCell key={cellIndex}>
                            <DateTimePicker
                              value={currentDateTime || undefined}
                              onChange={(newDate) => {
                                const newValue = newDate ? format(newDate, 'dd.MM.yyyy HH:mm', { locale: de }) : '';
                                onCellEdit(originalRowIndex, cellIndex, newValue);
                              }}
                              minuteInterval={5}
                            />
                          </TableCell>
                        );
                      } else if (editableType === 'text') {
                        return (
                          <TableCell key={cellIndex}>
                            <Input
                              value={cell}
                              onChange={(e) => onCellEdit(originalRowIndex, cellIndex, e.target.value)}
                              className="w-full"
                            />
                          </TableCell>
                        );
                      }
                    }
                    return (
                      <TableCell key={cellIndex} className={cn(isSeagoing && "text-blue-800 dark:text-blue-300 font-semibold")}>
                        {cell}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
};

export default ShipList;