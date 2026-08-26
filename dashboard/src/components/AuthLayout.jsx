import { Link, useLocation } from "react-router-dom";
import { marketingUrl, marketingNav } from "../config.js";
import { authPlatforms } from "../platforms.js";
import PlatformLogo from "./PlatformLogo.jsx";

export default function AuthLayout({ children }) {
  const { pathname } = useLocation();
  const isSignup = pathname === "/signup";

  return (
    <div className="auth-shell">
      <header className="auth-shell__header">
        <a href={marketingUrl} className="auth-shell__logo">
          <span className="auth-shell__mark">▲</span> Overtone
        </a>
        <nav className="auth-shell__nav" aria-label="Marketing">
          {marketingNav.map((item) => (
            <a key={item.href} href={item.href}>{item.label}</a>
          ))}
        </nav>
        <div className="auth-shell__cta">
          {!isSignup ? (
            <Link to="/signup" className="auth-shell__btn auth-shell__btn--primary">Start free trial</Link>
          ) : (
            <Link to="/login" className="auth-shell__btn auth-shell__btn--ghost">Sign in</Link>
          )}
        </div>
      </header>

      <main className="auth-shell__main">
        <aside className="auth-shell__aside">
          <p className="auth-shell__eyebrow">Live presentation agent</p>
          <h2 className="auth-shell__headline">Upload. Launch. Present. Answer — grounded in your deck.</h2>
          <ul className="auth-shell__list">
            <li>Deck-grounded Q&amp;A in live meetings</li>
            <li>Recall bot joins as your presenter</li>
            <li>Free trial — 1 upload, 1 launch</li>
          </ul>
          <div className="auth-shell__platforms">
            {authPlatforms.map((p) => (
              <PlatformLogo key={p.id} platform={p} size="sm" />
            ))}
          </div>
        </aside>
        <div className="auth-shell__form">{children}</div>
      </main>

      <footer className="auth-shell__footer">
        <p>© {new Date().getFullYear()} Overtone</p>
        <div className="auth-shell__footer-links">
          <a href={`${marketingUrl}/privacy`}>Privacy</a>
          <a href={`${marketingUrl}/terms`}>Terms</a>
          <a href={`${marketingUrl}/pricing`}>Pricing</a>
        </div>
      </footer>
    </div>
  );
}
