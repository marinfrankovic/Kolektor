import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api/client";
import { useRefreshSession, useSession } from "./hooks/useSession";
import { I18nProvider, useT } from "./i18n";
import Capture from "./pages/Capture";
import Collection from "./pages/Collection";
import ItemEdit from "./pages/ItemEdit";
import Login from "./pages/Login";
import MapView from "./pages/MapView";
import Settings from "./pages/Settings";
import Setup from "./pages/Setup";
import Stats from "./pages/Stats";

function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);
  return online;
}

function Chrome({ showLogout }: { showLogout: boolean }) {
  const t = useT();
  const refresh = useRefreshSession();
  const online = useOnline();
  const location = useLocation();

  const links = [
    { to: "/", label: t("nav.collection"), icon: "▣", end: true },
    { to: "/capture", label: t("nav.capture"), icon: "＋" },
    { to: "/map", label: t("nav.map"), icon: "◍" },
    { to: "/stats", label: t("nav.stats"), icon: "▤" },
    { to: "/settings", label: t("nav.settings"), icon: "⚙" },
  ];

  const signOut = async () => {
    await api.logout();
    refresh();
  };

  return (
    <>
      <header className="topbar">
        <span className="brand">{t("appName")}</span>
        <nav>
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end}>
              {link.label}
            </NavLink>
          ))}
        </nav>
        {showLogout && (
          <button className="ghost small" onClick={signOut}>
            {t("nav.logout")}
          </button>
        )}
      </header>

      {!online && <div className="offline-bar">{t("common.offline")}</div>}

      <nav className="tabbar" key={location.pathname}>
        {links.map((link) => (
          <NavLink key={link.to} to={link.to} end={link.end}>
            <span aria-hidden>{link.icon}</span>
            {link.label}
          </NavLink>
        ))}
      </nav>
    </>
  );
}

export default function App() {
  const { data: session, isPending, error } = useSession();

  if (isPending) {
    return (
      <I18nProvider language="en">
        <main className="centered muted">Loading…</main>
      </I18nProvider>
    );
  }

  if (error || !session) {
    return (
      <I18nProvider language="en">
        <main className="centered">
          <div className="card">
            <h1>Kolektor</h1>
            <p className="error">The server is not reachable.</p>
            <button onClick={() => window.location.reload()}>Try again</button>
          </div>
        </main>
      </I18nProvider>
    );
  }

  if (session.needsSetup) {
    return (
      <I18nProvider language={session.language}>
        <Setup />
      </I18nProvider>
    );
  }

  if (session.needsLogin) {
    return (
      <I18nProvider language={session.language}>
        <Login />
      </I18nProvider>
    );
  }

  return (
    <I18nProvider language={session.language}>
      <div className="shell">
        <Chrome showLogout={session.authMode === "password"} />
        <main>
          <Routes>
            <Route path="/" element={<Collection />} />
            <Route path="/items/new" element={<ItemEdit />} />
            <Route path="/items/:id" element={<ItemEdit />} />
            <Route path="/capture" element={<Capture />} />
            <Route path="/map" element={<MapView />} />
            <Route path="/stats" element={<Stats />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </I18nProvider>
  );
}
