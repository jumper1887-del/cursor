import React, { useState, useEffect, useCallback } from "react";
import { format, setHours, setMinutes, isValid } from "date-fns";
import { de } from "date-fns/locale";
import { Calendar as CalendarIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface DateTimePickerProps {
  value?: Date;
  onChange: (date: Date | undefined) => void;
  minuteInterval?: number;
  placeholder?: string;
}

const DateTimePicker: React.FC<DateTimePickerProps> = ({
  value,
  onChange,
  minuteInterval = 5,
  placeholder = "Datum & Uhrzeit",
}) => {
  const [isPopoverOpen, setIsPopoverOpen] = useState(false);

  // Internal state for selections within the popover, before confirmation
  const [tempSelectedDate, setTempSelectedDate] = useState<Date | undefined>(value);
  const [tempSelectedHour, setTempSelectedHour] = useState<string>(
    value ? format(value, "HH") : "00"
  );
  const [tempSelectedMinute, setTempSelectedMinute] = useState<string>(
    value ? format(value, "mm") : "00"
  );

  // Effect to synchronize internal temp state with external value prop when popover opens or value changes
  useEffect(() => {
    if (isPopoverOpen) {
      if (value) {
        setTempSelectedDate(value);
        setTempSelectedHour(format(value, "HH"));
        setTempSelectedMinute(format(value, "mm"));
      } else {
        // If no value is set, pre-fill with current date and time, rounding minutes
        const now = new Date();
        setTempSelectedDate(now);
        setTempSelectedHour(format(now, "HH"));
        
        const currentMinute = now.getMinutes();
        const roundedMinute = Math.round(currentMinute / minuteInterval) * minuteInterval;
        setTempSelectedMinute((roundedMinute % 60).toString().padStart(2, '0'));
      }
    }
  }, [value, isPopoverOpen, minuteInterval]); // minuteInterval als Abhängigkeit hinzugefügt

  const handleDateSelect = (date: Date | undefined) => {
    setTempSelectedDate(date);
  };

  const handleHourChange = (hour: string) => {
    setTempSelectedHour(hour);
  };

  const handleMinuteChange = (minute: string) => {
    setTempSelectedMinute(minute);
  };

  const handleConfirm = useCallback(() => {
    if (!tempSelectedDate) {
      onChange(undefined);
    } else {
      let newDateTime = setHours(tempSelectedDate, parseInt(tempSelectedHour));
      newDateTime = setMinutes(newDateTime, parseInt(tempSelectedMinute));
      onChange(newDateTime);
    }
    setIsPopoverOpen(false);
  }, [tempSelectedDate, tempSelectedHour, tempSelectedMinute, onChange]);

  const handleCancel = useCallback(() => {
    setIsPopoverOpen(false);
    // Reset temp state to the last committed value when cancelling
    setTempSelectedDate(value);
    if (value) {
      setTempSelectedHour(format(value, "HH"));
      setTempSelectedMinute(format(value, "mm"));
    } else {
      // If value was undefined, reset temp state to default "00:00"
      setTempSelectedHour("00");
      setTempSelectedMinute("00");
    }
  }, [value]);

  const generateTimeOptions = (interval: number) => {
    const options = [];
    for (let i = 0; i < 60; i += interval) {
      options.push(i.toString().padStart(2, '0'));
    }
    return options;
  };

  const hours = Array.from({ length: 24 }, (_, i) => i.toString().padStart(2, '0'));
  const minutes = generateTimeOptions(minuteInterval);

  // Display value should reflect the *committed* value, not the temporary one
  const displayValue = value && isValid(value)
    ? format(value, "dd.MM.yyyy HH:mm", { locale: de })
    : placeholder;

  return (
    <Popover open={isPopoverOpen} onOpenChange={setIsPopoverOpen}>
      <PopoverTrigger asChild>
        <Button
          variant={"outline"}
          className={cn(
            "w-full justify-start text-left font-normal",
            !value && "text-muted-foreground"
          )}
        >
          <CalendarIcon className="mr-2 h-4 w-4" />
          {displayValue}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0">
        <Calendar
          mode="single"
          selected={tempSelectedDate}
          onSelect={handleDateSelect}
          initialFocus
          locale={de}
        />
        <div className="p-3 border-t flex gap-2 justify-center">
          <Select
            value={tempSelectedHour}
            onValueChange={handleHourChange}
          >
            <SelectTrigger className="w-[80px]">
              <SelectValue placeholder="HH" />
            </SelectTrigger>
            <SelectContent>
              {hours.map((h) => (
                <SelectItem key={h} value={h}>
                  {h}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={tempSelectedMinute}
            onValueChange={handleMinuteChange}
          >
            <SelectTrigger className="w-[80px]">
              <SelectValue placeholder="MM" />
            </SelectTrigger>
            <SelectContent>
              {minutes.map((m) => (
                <SelectItem key={m} value={m}>
                  {m}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex justify-end gap-2 p-3 border-t">
          <Button variant="outline" onClick={handleCancel}>Abbrechen</Button>
          <Button onClick={handleConfirm}>Bestätigen</Button>
        </div>
      </PopoverContent>
    </Popover>
  );
};

export default DateTimePicker;