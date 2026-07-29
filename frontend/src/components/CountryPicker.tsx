import { useEffect, useMemo, useRef, useState } from "react";
import type { Country } from "../api/client";
import { useI18n, useT } from "../i18n";

export default function CountryPicker({
  id,
  value,
  countries,
  onChange,
}: {
  id: string;
  value: string;
  countries: Country[];
  onChange: (code2: string) => void;
}) {
  const t = useT();
  const { countryName } = useI18n();

  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const box = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLUListElement>(null);

  const labelled = useMemo(
    () => countries.map((c) => ({ ...c, label: countryName(c.code2) || c.name })),
    [countries, countryName],
  );

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return labelled;
    return labelled.filter(
      (c) => c.label.toLowerCase().includes(needle) || c.code2.toLowerCase() === needle,
    );
  }, [labelled, query]);

  const selected = labelled.find((c) => c.code2 === value);

  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [open]);

  useEffect(() => {
    list.current?.querySelector('[data-active="true"]')?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  const pick = (code2: string) => {
    onChange(code2);
    setQuery("");
    setOpen(false);
  };

  return (
    <div className="combo" ref={box}>
      <input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={`${id}-list`}
        aria-autocomplete="list"
        autoComplete="off"
        placeholder={t("country.search")}
        value={open ? query : (selected?.label ?? "")}
        onFocus={() => {
          setQuery("");
          setActive(0);
          setOpen(true);
        }}
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
          setOpen(true);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            if (!open) return setOpen(true);
            const step = e.key === "ArrowDown" ? 1 : -1;
            setActive((n) => (matches.length ? (n + step + matches.length) % matches.length : 0));
          } else if (e.key === "Enter") {
            if (open && matches[active]) {
              e.preventDefault();
              pick(matches[active].code2);
            }
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
      />

      {open && (
        <ul id={`${id}-list`} className="combo-list" role="listbox" ref={list}>
          {matches.length === 0 && <li className="muted small empty">{t("common.unknown")}</li>}
          {matches.map((c, i) => (
            <li
              key={c.code2}
              role="option"
              aria-selected={c.code2 === value}
              data-active={i === active}
              className={i === active ? "active" : undefined}
              onMouseEnter={() => setActive(i)}
              onPointerDown={(e) => {
                e.preventDefault();
                pick(c.code2);
              }}
            >
              <span>{c.label}</span>
              <span className="muted small">{c.code2}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
