import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError, type AuthMode } from "../api/client";
import { storeLanguage, useRefreshSession, useSession } from "../hooks/useSession";
import { useT } from "../i18n";
import type { Language } from "../i18n/dictionaries";

export default function Settings() {
  const t = useT();
  const refresh = useRefreshSession();
  const { data: session } = useSession();
  const config = useQuery({ queryKey: ["config"], queryFn: api.config, staleTime: Infinity });

  const [displayName, setDisplayName] = useState(session?.user?.display_name ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [modeEmail, setModeEmail] = useState(session?.user?.email ?? "");
  const [modePassword, setModePassword] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const authMode: AuthMode = session?.authMode ?? "password";

  const report = (err: unknown) =>
    setError(err instanceof ApiError ? String(err.detail ?? err.message) : t("common.error"));

  const changeLanguage = async (language: Language) => {
    storeLanguage(language);
    try {
      await api.updateMe({ language });
    } finally {
      refresh();
    }
  };

  const saveProfile = async () => {
    setError("");
    setNotice("");
    try {
      await api.updateMe({ display_name: displayName || null });
      setNotice(t("action.save"));
      refresh();
    } catch (err) {
      report(err);
    }
  };

  const changePassword = async () => {
    setError("");
    setNotice("");
    try {
      await api.changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setNotice(t("settings.passwordChanged"));
    } catch (err) {
      report(err);
    }
  };

  const switchMode = async (next: AuthMode) => {
    setError("");
    setNotice("");
    if (next === "open" && !window.confirm(t("settings.access.openWarning"))) return;
    try {
      await api.changeAuthMode(
        next === "password"
          ? { auth_mode: "password", email: modeEmail, password: modePassword }
          : { auth_mode: "open" },
      );
      setModePassword("");
      refresh();
    } catch (err) {
      report(err);
    }
  };

  return (
    <div className="stack">
      <h1>{t("settings.title")}</h1>

      {error && <p className="error">{error}</p>}
      {notice && <p className="notice">{notice}</p>}

      <div className="card stack">
        <h3>{t("settings.language")}</h3>
        <select
          value={session?.language ?? "en"}
          onChange={(e) => changeLanguage(e.target.value as Language)}
        >
          <option value="en">{t("settings.language.en")}</option>
          <option value="hr">{t("settings.language.hr")}</option>
        </select>

        <div>
          <label htmlFor="s-name">{t("settings.displayName")}</label>
          <input id="s-name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </div>
        <div>
          <button onClick={saveProfile}>{t("action.save")}</button>
        </div>
      </div>

      <div className="card stack">
        <h3>{t("settings.access")}</h3>
        <p className="muted small">
          {authMode === "password" ? t("settings.access.password") : t("settings.access.open")}
        </p>

        {authMode === "password" ? (
          <button className="danger" onClick={() => switchMode("open")}>
            {t("settings.access.switchToOpen")}
          </button>
        ) : (
          <>
            <div>
              <label htmlFor="s-mode-email">{t("setup.email")}</label>
              <input
                id="s-mode-email"
                type="email"
                autoComplete="username"
                value={modeEmail}
                onChange={(e) => setModeEmail(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="s-mode-password">{t("setup.password")}</label>
              <input
                id="s-mode-password"
                type="password"
                autoComplete="new-password"
                minLength={10}
                value={modePassword}
                onChange={(e) => setModePassword(e.target.value)}
              />
              <p className="muted small">{t("setup.passwordRule")}</p>
            </div>
            <button className="primary" onClick={() => switchMode("password")}>
              {t("settings.access.switchToPassword")}
            </button>
          </>
        )}
      </div>

      {authMode === "password" && (
        <div className="card stack">
          <h3>{t("settings.changePassword")}</h3>
          <div>
            <label htmlFor="s-current">{t("settings.currentPassword")}</label>
            <input
              id="s-current"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="s-new">{t("settings.newPassword")}</label>
            <input
              id="s-new"
              type="password"
              autoComplete="new-password"
              minLength={10}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
            <p className="muted small">{t("setup.passwordRule")}</p>
          </div>
          <div>
            <button onClick={changePassword} disabled={!currentPassword || newPassword.length < 10}>
              {t("action.save")}
            </button>
          </div>
        </div>
      )}

      <div className="card small muted">
        <h3>{t("settings.about")}</h3>
        <div>Kolektor</div>
        {config.data && (
          <div>
            OCR: {config.data.ocr_enabled ? t("common.yes") : t("common.no")} · auto-crop:{" "}
            {config.data.autocrop ? t("common.yes") : t("common.no")} · max upload:{" "}
            {config.data.max_upload_mb} MB · TLS:{" "}
            {config.data.tls_terminated ? t("common.yes") : t("common.no")}
          </div>
        )}
      </div>
    </div>
  );
}
