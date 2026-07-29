/** The interface shows and takes dates as dd/mm/yyyy; the API speaks ISO yyyy-mm-dd. */

const ISO = /^(\d{4})-(\d{2})-(\d{2})/;
const DISPLAY = /^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$/;

export function toDisplayDate(value: string | null | undefined): string {
  if (!value) return "";
  const match = ISO.exec(value);
  if (!match) return value;
  const [, year, month, day] = match;
  return `${day}/${month}/${year}`;
}

export function toIsoDate(value: string): string | null {
  const match = DISPLAY.exec(value.trim());
  if (!match) return null;
  const [, day, month, year] = match;
  const iso = `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
  const parsed = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime()) || parsed.getUTCDate() !== Number(day)) return null;
  return iso;
}
