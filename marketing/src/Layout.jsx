import { Link, NavLink, Outlet } from "react-router-dom";

const dashboardUrl = import.meta.env.VITE_DASHBOARD_URL || "http://127.0.0.1:5176";

export default function Layout() {
  return (
    <div className="site">
      <header className="site-header">
        <Link to="/" className="logo">
          <span className="logo-mark">▲</span> Overtone
        </Link>
        <nav className="site-nav">
          <NavLink to="/features">Features</NavLink>
          <NavLink to="/pricing">Pricing</NavLink>
          <NavLink to="/how-it-works">How it works</NavLink>
        </nav>
        <div className="header-cta">
          <a href={`${dashboardUrl}/login`} className="btn btn-ghost">Sign in</a>
          <a href={`${dashboardUrl}/signup`} className="btn btn-primary">Start free trial</a>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
      <footer className="site-footer">
        <p>© {new Date().getFullYear()} Overtone</p>
        <div>
          <Link to="/privacy">Privacy</Link>
          <Link to="/terms">Terms</Link>
        </div>
      </footer>
    </div>
  );
}
