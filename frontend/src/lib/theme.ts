import { useCallback, useEffect, useState } from "react";

export type Theme = "system" | "light" | "dark";

const KEY = "kolektor.theme";

function stored(): Theme {
  const value = localStorage.getItem(KEY);
  return value === "light" || value === "dark" ? value : "system";
}

function apply(theme: Theme): void {
  const dark =
    theme === "dark" ||
    (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

/** Runs before React mounts so the first paint is already in the chosen theme. */
export function initTheme(): void {
  apply(stored());
  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", () => apply(stored()));
}

export function useTheme(): [Theme, (next: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(stored);

  useEffect(() => apply(theme), [theme]);

  const change = useCallback((next: Theme) => {
    localStorage.setItem(KEY, next);
    setTheme(next);
  }, []);

  return [theme, change];
}
