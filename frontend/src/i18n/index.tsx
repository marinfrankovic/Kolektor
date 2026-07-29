import { createContext, useContext, useMemo, type ReactNode } from "react";
import { dictionaries, type Language, type TranslationKey } from "./dictionaries";

type Translate = (key: TranslationKey, vars?: Record<string, string | number>) => string;

type I18nValue = {
  language: Language;
  t: Translate;
  countryName: (code2: string) => string;
  formatNumber: (value: number) => string;
  formatDate: (value: string | Date) => string;
};

const I18nContext = createContext<I18nValue | null>(null);

const LOCALES: Record<Language, string> = { en: "en-GB", hr: "hr-HR" };

export function I18nProvider({
  language,
  children,
}: {
  language: Language;
  children: ReactNode;
}) {
  const value = useMemo<I18nValue>(() => {
    const locale = LOCALES[language];
    const dictionary = dictionaries[language];

    // Country names come from the browser, so no translated name table is shipped.
    let displayNames: Intl.DisplayNames | null = null;
    try {
      displayNames = new Intl.DisplayNames([locale], { type: "region" });
    } catch {
      displayNames = null;
    }

    return {
      language,
      t: (key, vars) => {
        let text = dictionary[key] ?? key;
        if (vars) {
          for (const [name, replacement] of Object.entries(vars)) {
            text = text.replaceAll(`{${name}}`, String(replacement));
          }
        }
        return text;
      },
      countryName: (code2) => {
        if (!code2) return "";
        try {
          return displayNames?.of(code2.toUpperCase()) ?? code2;
        } catch {
          return code2;
        }
      },
      formatNumber: (value) => new Intl.NumberFormat(locale).format(value),
      formatDate: (value) =>
        new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(value)),
    };
  }, [language]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used inside I18nProvider");
  return value;
}

export function useT(): Translate {
  return useI18n().t;
}

export type { Language, TranslationKey };
