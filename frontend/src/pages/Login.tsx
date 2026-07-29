import { useState, type FormEvent } from "react";
import { api, ApiError } from "../api/client";
import { useRefreshSession, storeLanguage } from "../hooks/useSession";
import { useI18n, useT } from "../i18n";
import type { Language } from "../i18n/dictionaries";

export default function Login() {
  const t = useT();
  const { language } = useI18n();
  const refresh = useRefreshSession();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.login(email, password);
      refresh();
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) setError(t("login.throttled"));
      else setError(t("login.failed"));
    } finally {
      setBusy(false);
    }
  };

  const pickLanguage = (next: Language) => {
    storeLanguage(next);
    refresh();
  };

  return (
    <main className="centered">
      <form className="card stack" onSubmit={submit}>
        <h1>{t("login.title")}</h1>

        <div>
          <label htmlFor="login-email">{t("login.email")}</label>
          <input
            id="login-email"
            type="email"
            autoComplete="username"
            required
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div>
          <label htmlFor="login-password">{t("login.password")}</label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        {error && <p className="error">{error}</p>}

        <button className="primary" type="submit" disabled={busy}>
          {busy ? t("action.saving") : t("login.submit")}
        </button>

        <div>
          <label htmlFor="login-language">{t("settings.language")}</label>
          <select
            id="login-language"
            value={language}
            onChange={(e) => pickLanguage(e.target.value as Language)}
          >
            <option value="en">{t("settings.language.en")}</option>
            <option value="hr">{t("settings.language.hr")}</option>
          </select>
        </div>
      </form>
    </main>
  );
}
