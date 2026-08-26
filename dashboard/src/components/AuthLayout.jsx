import { Link, useLocation } from "react-router-dom";
import { Check } from "lucide-react";
import { marketingUrl, marketingNav } from "../config.js";
import BrandLogo from "./BrandLogo.jsx";
import { integrations } from "./integrations.js";

const highlights = [
  "Deck-grounded Q&A in Meet, Zoom, Teams",
  "Recall bot joins as your presenter",
  "Free trial — 1 upload, 1 launch",
];

const platformLogos = integrations.filter((i) =>
  ["googlemeet", "zoom", "microsoftteams", "recall"].includes(i.id)
);

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
        <div className="auth-shell__visual">
          <p className="auth-shell__visual-eyebrow">Live presentation agent</p>
          <h2 className="auth-shell__visual-title">Upload. Launch. Present. Answer.</h2>
          <p className="auth-shell__visual-lede">Grounded in your deck — not generic chat.</p>
          <ul className="auth-shell__visual-list">
            {highlights.map((line) => (
              <li key={line}>
                <Check size={16} strokeWidth={2.5} aria-hidden="true" />
                {line}
              </li>
            ))}
          </ul>
          <div className="auth-shell__platforms">
            {platformLogos.map((brand) => (
              <div key={brand.id} className="auth-shell__platform-tile" title={brand.label}>
                <BrandLogo brand={brand} size={24} />
              </div>
            ))}
          </div>
        </div>
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
