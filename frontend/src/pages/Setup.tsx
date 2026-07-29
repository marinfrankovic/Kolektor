import { useState, type FormEvent } from "react";
import { api, ApiError, type AuthMode } from "../api/client";
import { useRefreshSession, storeLanguage } from "../hooks/useSession";
import { useI18n, useT } from "../i18n";
import type { Language } from "../i18n/dictionaries";

export default function Setup() {
  const t = useT();
  const { language } = useI18n();
  const refresh = useRefreshSession();

  const [mode, setMode] = useState<AuthMode>("password");
  const [chosenLanguage, setChosenLanguage] = useState<Language>(language);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const pickLanguage = (next: Language) => {
    setChosenLanguage(next);
    storeLanguage(next);
    refresh();
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");

    if (mode === "open" && !window.confirm(t("setup.openWarning"))) return;

    setBusy(true);
    try {
      await api.completeSetup({
        auth_mode: mode,
        language: chosenLanguage,
        ...(mode === "password" ? { email, password } : {}),
      });
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail ?? err.message) : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="centered">
      <form className="card stack" onSubmit={submit}>
        <div>
          <h1>{t("setup.title")}</h1>
          <p className="muted small">{t("setup.intro")}</p>
        </div>

        <div>
          <label htmlFor="setup-language">{t("setup.language")}</label>
          <select
            id="setup-language"
            value={chosenLanguage}
            onChange={(e) => pickLanguage(e.target.value as Language)}
          >
            <option value="en">{t("settings.language.en")}</option>
            <option value="hr">{t("settings.language.hr")}</option>
          </select>
        </div>

        <div className="stack">
          <button
            type="button"
            className={`choice${mode === "password" ? " selected" : ""}`}
            aria-pressed={mode === "password"}
            onClick={() => setMode("password")}
          >
            <strong>{t("setup.password.title")}</strong>
            <span className="muted small">{t("setup.password.hint")}</span>
          </button>

          <button
            type="button"
            className={`choice${mode === "open" ? " selected" : ""}`}
            aria-pressed={mode === "open"}
            onClick={() => setMode("open")}
          >
            <strong>{t("setup.open.title")}</strong>
            <span className="muted small">{t("setup.open.hint")}</span>
          </button>
        </div>

        {mode === "password" && (
          <>
            <div>
              <label htmlFor="setup-email">{t("setup.email")}</label>
              <input
                id="setup-email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="setup-password">{t("setup.password")}</label>
              <input
                id="setup-password"
                type="password"
                autoComplete="new-password"
                minLength={10}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <p className="muted small">{t("setup.passwordRule")}</p>
            </div>
          </>
        )}

        {error && <p className="error">{error}</p>}

        <button className="primary" type="submit" disabled={busy}>
          {busy ? t("action.saving") : t("setup.submit")}
        </button>
      </form>
    </main>
  );
}
