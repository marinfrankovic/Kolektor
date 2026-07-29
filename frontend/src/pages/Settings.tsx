import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError, type AuthMode } from "../api/client";
import { storeLanguage, useRefreshSession, useSession } from "../hooks/useSession";
import { useT } from "../i18n";
import { useTheme, type Theme } from "../lib/theme";
import { ALL_PATHS, FIELD_GROUPS, LOCKED_FIELDS, useFieldVisibility } from "../lib/fields";
import type { Language, TranslationKey } from "../i18n/dictionaries";

const TABS = ["general", "fields", "access", "about"] as const;
type Tab = (typeof TABS)[number];

export default function Settings() {
  const t = useT();
  const refresh = useRefreshSession();
  const { data: session } = useSession();
  const config = useQuery({ queryKey: ["config"], queryFn: api.config, staleTime: Infinity });
  const [theme, setTheme] = useTheme();
  const { hidden, shows, setVisible } = useFieldVisibility();

  const [tab, setTab] = useState<Tab>("general");
  const [displayName, setDisplayName] = useState(session?.user?.display_name ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [modeEmail, setModeEmail] = useState(session?.user?.email ?? "");
  const [modePassword, setModePassword] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const authMode: AuthMode = session?.authMode ?? "password";
  const shownCount = ALL_PATHS.filter((path) => !hidden.has(path)).length;

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
      setNotice(t("settings.saved"));
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

      <div className="tabs" role="tablist" aria-label={t("settings.title")}>
        {TABS.map((name) => (
          <button
            key={name}
            role="tab"
            id={`tab-${name}`}
            aria-selected={tab === name}
            aria-controls={`panel-${name}`}
            onClick={() => setTab(name)}
          >
            {t(`settings.tab.${name}` as TranslationKey)}
          </button>
        ))}
      </div>

      {error && <p className="error">{error}</p>}
      {notice && <p className="notice">{notice}</p>}

      {tab === "general" && (
        <div role="tabpanel" id="panel-general" aria-labelledby="tab-general">
          <div className="card">
            <h3>{t("settings.appearance")}</h3>
            <div className="grid">
              <div>
                <label htmlFor="s-language">{t("settings.language")}</label>
                <select
                  id="s-language"
                  value={session?.language ?? "en"}
                  onChange={(e) => changeLanguage(e.target.value as Language)}
                >
                  <option value="en">{t("settings.language.en")}</option>
                  <option value="hr">{t("settings.language.hr")}</option>
                </select>
              </div>

              <div>
                <label htmlFor="s-theme">{t("settings.theme")}</label>
                <select
                  id="s-theme"
                  value={theme}
                  onChange={(e) => setTheme(e.target.value as Theme)}
                >
                  <option value="system">{t("settings.theme.system")}</option>
                  <option value="light">{t("settings.theme.light")}</option>
                  <option value="dark">{t("settings.theme.dark")}</option>
                </select>
              </div>
            </div>
            <p className="muted small hint">{t("settings.appearance.hint")}</p>
          </div>

          <div className="card">
            <h3>{t("settings.profile")}</h3>
            <label htmlFor="s-name">{t("settings.displayName")}</label>
            <input
              id="s-name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
            <p className="muted small hint">{t("settings.displayName.hint")}</p>
            <div className="row" style={{ marginTop: "0.75rem" }}>
              <button className="primary" onClick={saveProfile}>
                {t("action.save")}
              </button>
            </div>
          </div>
        </div>
      )}

      {tab === "fields" && (
        <div role="tabpanel" id="panel-fields" aria-labelledby="tab-fields">
          <div className="card">
            <div className="spread">
              <h3 style={{ margin: 0 }}>{t("settings.fields")}</h3>
              <span className="muted small">
                {t("settings.fields.shown", { shown: shownCount, total: ALL_PATHS.length })}
              </span>
            </div>
            <p className="muted small hint">{t("settings.fields.hint")}</p>
            <div className="row" style={{ marginTop: "0.75rem" }}>
              <button className="ghost small" onClick={() => setVisible(ALL_PATHS, true)}>
                {t("settings.fields.showAll")}
              </button>
              <button className="ghost small" onClick={() => setVisible(ALL_PATHS, false)}>
                {t("settings.fields.hideAll")}
              </button>
            </div>
          </div>

          <div className="card">
            <h3>{t("settings.fields.always")}</h3>
            <div className="check-grid">
              {LOCKED_FIELDS.map((field) => (
                <span className="check locked" key={field.path}>
                  <input type="checkbox" checked disabled readOnly />
                  {t(field.label)}
                </span>
              ))}
            </div>
            <p className="muted small hint">{t("settings.fields.alwaysHint")}</p>
          </div>

          {FIELD_GROUPS.map((group) => {
            const paths = group.fields.map((field) => field.path);
            const visible = paths.filter((path) => shows(path)).length;
            return (
              <div className="card" key={group.id}>
                <div className="spread">
                  <h3 style={{ margin: 0 }}>{t(group.label)}</h3>
                  <div className="row">
                    <span className="muted small">
                      {t("settings.fields.shown", { shown: visible, total: paths.length })}
                    </span>
                    <button
                      className="ghost small"
                      disabled={visible === paths.length}
                      onClick={() => setVisible(paths, true)}
                    >
                      {t("settings.fields.showAll")}
                    </button>
                    <button
                      className="ghost small"
                      disabled={visible === 0}
                      onClick={() => setVisible(paths, false)}
                    >
                      {t("settings.fields.hideAll")}
                    </button>
                  </div>
                </div>
                <div className="check-grid" style={{ marginTop: "0.75rem" }}>
                  {group.fields.map((field) => (
                    <label className="check" key={field.path}>
                      <input
                        type="checkbox"
                        checked={shows(field.path)}
                        onChange={(e) => setVisible([field.path], e.target.checked)}
                      />
                      {t(field.label)}
                    </label>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {tab === "access" && (
        <div role="tabpanel" id="panel-access" aria-labelledby="tab-access">
          <div className="card">
            <h3>{t("settings.access")}</h3>
            <p className="muted small hint">
              {authMode === "password" ? t("settings.access.password") : t("settings.access.open")}
            </p>

            {authMode === "password" ? (
              <div className="row" style={{ marginTop: "0.75rem" }}>
                <button className="danger" onClick={() => switchMode("open")}>
                  {t("settings.access.switchToOpen")}
                </button>
              </div>
            ) : (
              <div className="stack" style={{ marginTop: "0.75rem" }}>
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
                  <p className="muted small hint">{t("setup.passwordRule")}</p>
                </div>
                <div className="row">
                  <button className="primary" onClick={() => switchMode("password")}>
                    {t("settings.access.switchToPassword")}
                  </button>
                </div>
              </div>
            )}
          </div>

          {authMode === "password" && (
            <div className="card">
              <h3>{t("settings.changePassword")}</h3>
              <div className="grid">
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
                  <p className="muted small hint">{t("setup.passwordRule")}</p>
                </div>
              </div>
              <div className="row" style={{ marginTop: "0.75rem" }}>
                <button
                  className="primary"
                  onClick={changePassword}
                  disabled={!currentPassword || newPassword.length < 10}
                >
                  {t("action.save")}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "about" && (
        <div role="tabpanel" id="panel-about" aria-labelledby="tab-about">
          <div className="card">
            <h3>{t("settings.about")}</h3>
            <dl className="facts">
              <dt>{t("settings.about.signedIn")}</dt>
              <dd>{session?.user?.email ?? t("settings.access.open")}</dd>
              {config.data && (
                <>
                  <dt>{t("settings.about.autocrop")}</dt>
                  <dd>{config.data.autocrop ? t("common.yes") : t("common.no")}</dd>
                  <dt>{t("settings.about.maxUpload")}</dt>
                  <dd>{config.data.max_upload_mb} MB</dd>
                  <dt>{t("settings.about.tls")}</dt>
                  <dd>{config.data.tls_terminated ? t("common.yes") : t("common.no")}</dd>
                </>
              )}
            </dl>
          </div>
        </div>
      )}
    </div>
  );
}
