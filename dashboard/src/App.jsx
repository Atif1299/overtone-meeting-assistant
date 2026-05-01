import { useState } from "react";
import { Route, Routes, NavLink, useLocation, useNavigate } from "react-router-dom";
import OverviewPage from "./pages/OverviewPage.jsx";
import UploadPage from "./pages/UploadPage.jsx";
import LaunchPage from "./pages/LaunchPage.jsx";
import SessionPage from "./pages/SessionPage.jsx";
import AgentsPage from "./pages/AgentsPage.jsx";
import AdminPage from "./pages/AdminPage.jsx";
import Testform from "./pages/Testform.jsx";
import { clearAdminSession, hasAdminSession } from "./utils/api";

const navItems = [
  {
    to: "/",
    label: "Overview",
    caption: "System health",
    end: true,
    glyph: "◉",
  },
  {
    to: "/agents",
    label: "Agents",
    caption: "Prompt studio",
    glyph: "◆",
  },
  {
    to: "/presentations",
    label: "Presentations",
    caption: "Knowledge base",
    glyph: "▣",
  },
  {
    to: "/launch",
    label: "Launch",
    caption: "Bot controls",
    glyph: "▶",
  },
  {
    to: "/session",
    label: "Session",
    caption: "Live monitor",
    glyph: "◍",
  },
];

export default function App() {
  const [isAdminAuthenticated, setIsAdminAuthenticated] = useState(hasAdminSession);
  const location = useLocation();
  const navigate = useNavigate();
  const pathname = location.pathname;

  const isAdminPage = pathname === "/admin";
  const isTestFormPage = pathname === "/testform";

  function handleAdminAuthSuccess() {
    setIsAdminAuthenticated(true);
    navigate("/admin");
  }

  function handleAdminLogout() {
    clearAdminSession();
    setIsAdminAuthenticated(false);
    navigate("/admin");
  }

  // Standalone Pages (No Sidebar / Header)
  if (isAdminPage) {
    if (!isAdminAuthenticated) {
      return <Testform onAuthSuccess={handleAdminAuthSuccess} />;
    }
    return <AdminPage onLogout={handleAdminLogout} onAuthExpired={handleAdminLogout} />;
  }

  if (isTestFormPage) {
    return <Testform onAuthSuccess={handleAdminAuthSuccess} />;
  }

  return (
    <div className="app-shell">
      <div className="ambient-layer" aria-hidden="true" />

      <header className="topbar">
        <div className="brand">
          <span className="brand-badge">▲</span>

          <div>
            <p className="brand-title">Overtone</p>
            <p className="brand-subtitle">
              AI presentation operations studio
            </p>
          </div>
        </div>

        <div className="topbar-actions">
          <span className="status-chip">Production</span>
        </div>
      </header>

      <div className="shell-body">
        <aside className="sidebar">
          <p className="nav-heading">Workspace</p>

          <nav className="nav-list" aria-label="Primary">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  isActive
                    ? "nav-link active"
                    : "nav-link"
                }
              >
                <span
                  className="nav-glyph"
                  aria-hidden="true"
                >
                  {item.glyph}
                </span>

                <span className="nav-copy">
                  <span>{item.label}</span>
                  <small>{item.caption}</small>
                </span>
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="content">
          <Routes>
            <Route
              path="/"
              element={<OverviewPage />}
            />

            <Route
              path="/agents"
              element={<AgentsPage />}
            />

            <Route
              path="/presentations"
              element={<UploadPage />}
            />

            <Route
              path="/launch"
              element={<LaunchPage />}
            />

            <Route
              path="/session"
              element={<SessionPage />}
            />
          </Routes>
        </main>
      </div>
    </div>
  );
}