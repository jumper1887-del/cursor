import { parse, isFuture } from 'date-fns';
import { de } from 'date-fns/locale';

/**
 * Parst einen deutschen Datums- und Uhrzeitstring im Format 'dd.MM.yyyy HH:mm' in ein Date-Objekt.
 * @param dateTimeString Der zu parsende String.
 * @returns Ein Date-Objekt oder null, wenn der String ungültig ist.
 */
export const parseGermanDateTime = (dateTimeString: string): Date | null => {
  try {
    const parsedDate = parse(dateTimeString, 'dd.MM.yyyy HH:mm', new Date(), { locale: de });
    if (isNaN(parsedDate.getTime())) {
      return null;
    }
    return parsedDate;
  } catch (e) {
    console.error("Fehler beim Parsen des Datums- und Uhrzeitstrings:", dateTimeString, e);
    return null;
  }
};

export { isFuture };