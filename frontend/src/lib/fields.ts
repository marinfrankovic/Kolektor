import { useCallback, useState } from "react";
import type { TranslationKey } from "../i18n/dictionaries";

export type FieldDef = { path: string; label: TranslationKey };
export type FieldGroup = { id: string; label: TranslationKey; fields: FieldDef[] };

/** An item without these says nothing, so they stay on the page and out of Settings. */
export const LOCKED_FIELDS: FieldDef[] = [
  { path: "kind", label: "item.kind" },
  { path: "status", label: "item.status" },
  { path: "title", label: "item.title" },
  { path: "country_code", label: "item.country" },
  { path: "denomination_value", label: "item.denomination" },
  { path: "currency_unit", label: "item.currency" },
  { path: "year", label: "item.year" },
];

const LOCKED = new Set(LOCKED_FIELDS.map((field) => field.path));

export const FIELD_GROUPS: FieldGroup[] = [
  {
    id: "item",
    label: "item.section",
    fields: [
      { path: "issuing_entity", label: "item.issuer" },
      { path: "region", label: "item.region" },
      { path: "period", label: "item.period" },
      { path: "ruler", label: "item.ruler" },
      { path: "year_text", label: "item.yearText" },
      { path: "series", label: "item.series" },
      { path: "subject", label: "item.subject" },
      { path: "quantity", label: "item.quantity" },
      { path: "grade_value", label: "item.grade" },
      { path: "grade_scale", label: "item.gradeScale" },
      { path: "grader", label: "item.grader" },
      { path: "cert_number", label: "item.certNumber" },
      { path: "rarity", label: "item.rarity" },
      { path: "storage", label: "item.storage" },
      { path: "slot", label: "item.slot" },
      { path: "barcode", label: "item.barcode" },
      { path: "tags", label: "item.tags" },
      { path: "notes", label: "item.notes" },
      { path: "catalog_refs", label: "catalog.section" },
    ],
  },
  {
    id: "coin",
    label: "coin.section",
    fields: [
      { path: "coin.diameter_mm", label: "coin.diameter" },
      { path: "coin.weight_g", label: "coin.weight" },
      { path: "coin.thickness_mm", label: "coin.thickness" },
      { path: "coin.shape", label: "coin.shape" },
      { path: "coin.edge_type", label: "coin.edge" },
      { path: "coin.edge_lettering", label: "coin.edgeLettering" },
      { path: "coin.die_axis", label: "coin.dieAxis" },
      { path: "coin.composition", label: "coin.composition" },
      { path: "coin.material", label: "coin.material" },
      { path: "coin.fineness", label: "coin.fineness" },
      { path: "coin.mint", label: "coin.mint" },
      { path: "coin.mintmark", label: "coin.mintmark" },
      { path: "coin.mintage", label: "coin.mintage" },
      { path: "coin.quality", label: "coin.quality" },
    ],
  },
  {
    id: "banknote",
    label: "note.section",
    fields: [
      { path: "banknote.width_mm", label: "note.width" },
      { path: "banknote.height_mm", label: "note.height" },
      { path: "banknote.substrate", label: "note.substrate" },
      { path: "banknote.pick_number", label: "note.pick" },
      { path: "banknote.serial_number", label: "note.serial" },
      { path: "banknote.serial_prefix", label: "note.serialPrefix" },
      { path: "banknote.serial_suffix", label: "note.serialSuffix" },
      { path: "banknote.block", label: "note.block" },
      { path: "banknote.plate", label: "note.plate" },
      { path: "banknote.signature_combination", label: "note.signatures" },
      { path: "banknote.signatories", label: "note.signatories" },
      { path: "banknote.printer", label: "note.printer" },
      { path: "banknote.watermark", label: "note.watermark" },
      { path: "banknote.security_thread", label: "note.thread" },
      { path: "banknote.overprint", label: "note.overprint" },
      { path: "banknote.series_year", label: "note.seriesYear" },
      { path: "banknote.is_replacement", label: "note.replacement" },
    ],
  },
  {
    id: "acquisition",
    label: "money.acquisition",
    fields: [
      { path: "acquisition.date", label: "money.date" },
      { path: "acquisition.price", label: "money.price" },
      { path: "acquisition.currency", label: "money.currency" },
      { path: "acquisition.counterparty", label: "money.counterparty" },
      { path: "acquisition.place", label: "money.place" },
    ],
  },
  {
    id: "disposal",
    label: "money.disposal",
    fields: [
      { path: "disposal.date", label: "money.date" },
      { path: "disposal.price", label: "money.price" },
      { path: "disposal.currency", label: "money.currency" },
      { path: "disposal.counterparty", label: "money.counterparty" },
    ],
  },
];

export const ALL_PATHS = FIELD_GROUPS.flatMap((group) =>
  group.fields.map((field) => field.path),
);

const KEY = "kolektor.hiddenFields";

function read(): Set<string> {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((value): value is string => typeof value === "string"));
  } catch {
    return new Set();
  }
}

/** Only hidden paths are stored, so a field added in a later version shows up on its own. */
export function useFieldVisibility() {
  const [hidden, setHidden] = useState<Set<string>>(read);

  const shows = useCallback(
    (path: string) => LOCKED.has(path) || !hidden.has(path),
    [hidden],
  );

  const setVisible = useCallback((paths: string[], visible: boolean) => {
    setHidden((current) => {
      const next = new Set(current);
      for (const path of paths) {
        if (visible || LOCKED.has(path)) next.delete(path);
        else next.add(path);
      }
      localStorage.setItem(KEY, JSON.stringify([...next]));
      return next;
    });
  }, []);

  const groupShows = useCallback(
    (id: string) =>
      (FIELD_GROUPS.find((group) => group.id === id)?.fields ?? []).some((field) =>
        shows(field.path),
      ),
    [shows],
  );

  return { hidden, shows, groupShows, setVisible };
}
